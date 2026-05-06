import logging
import json
import uuid
import threading
from typing import Generator, List, Tuple, Optional

from langchain.schema import Document

from app.config import settings
from app.core.retriever import hybrid_retriever
from app.core.query_enhancer import query_enhancer
from app.core.memory_manager import memory_manager
from app.core.knowledge_graph import legal_kg
from app.core.llm_client import llm_client, LLMConfig
from app.core.reranker import reranker
from app.core.web_searcher import web_searcher
from app.core.lccp import lccp_confidence, LCCP_SYSTEM_PROMPT
from app.models.schemas import AnswerResponse, SourceDocument

logger = logging.getLogger(__name__)

# ── 系统提示词 ────────────────────────────────────────────────────────────────
LEGAL_SYSTEM_PROMPT = """你是一名中国法律咨询助手。根据以下法律文档回答用户问题，能引用原文条款的就引用，不知道的不编造。

回答要求：
1. 分析法律关系和各方利弊，不要简单列举条款条目
2. 用自然流畅的语言解释法律后果和风险
3. 明确告知用户有哪些选择以及各自的利弊
4. 如果知识文档中**没有明确写明**"第X条"或"第X款"，就**不要说**具体条款编号，只能说"根据法律规定"或"依据相关法规"
5. 不知道的不要编造，如实说明

{history_section}

{context}
"""

HISTORY_SECTION_TEMPLATE = """
【对话历史】
{history}

请结合以上对话历史理解用户当前问题的上下文。
"""


class RAGPipeline:
    """
    RAG 推理流水线（升级版）

    完整流程：
    1. 查询增强（HyDE / Multi-Query）
    2. 混合检索（BM25 + 向量）
    3. 知识图谱扩展（条文引用关系补充）
    4. 上下文构建（带历史摘要）
    5. DeepSeek-R1 推理
    6. 对话记忆更新
    """

    def __init__(self):
        pass  # 所有状态由各子模块单例管理

    # ── 联网文档暂存到待审核池 ───────────────────────────────────────────────
    def _stage_web_docs_to_pending_pool(self, docs: List, query: str) -> None:
        """
        将联网搜索到的文档先存入暂存池，等待评估后再决定是否入库。
        - 入库前先做主题过滤，非法律内容直接丢弃
        - 存入暂存池，等待人工或自动评估
        - 失败不影响主流程（异步线程，静默记录日志）
        """
        from app.core.web_searcher import _is_legal_relevant
        from app.rag.pending_pool import get_pending_pool, PendingDocument

        try:
            pending_pool = get_pending_pool()

            # ── Step 0: 主题过滤，非法律内容直接丢弃 ────────────────────────
            topic_filtered = []
            for doc in docs:
                if _is_legal_relevant(doc.page_content):
                    topic_filtered.append(doc)
                else:
                    logger.info(
                        f"[暂存池] 主题过滤拒绝（非法律内容）: {doc.page_content[:60]}"
                    )
            if not topic_filtered:
                logger.info("[暂存池] 全部文档被主题过滤拦截，无内容存入暂存池")
                return

            # ── Step 1: 存入暂存池 ──────────────────────────────────────────
            staged_count = 0
            for doc in topic_filtered:
                try:
                    pending_doc = PendingDocument(
                        query=query,
                        content=doc.page_content,
                        source_url=doc.metadata.get("url", ""),
                        source_type="web",
                        relevance_score=doc.metadata.get("relevance_score", 0.5),
                        metadata={
                            "source": doc.metadata.get("source", "联网检索"),
                            "web_source": doc.metadata.get("web_source", "unknown"),
                            "crawl_time": doc.metadata.get("crawl_time"),
                        }
                    )
                    if pending_pool.add_document(pending_doc):
                        staged_count += 1
                except Exception as e:
                    logger.warning(f"[暂存池] 添加文档失败: {e}")

            if staged_count > 0:
                logger.info(f"[暂存池] 已暂存 {staged_count} 条网络文档，等待评估")
            else:
                logger.debug("[暂存池] 无新内容需要暂存")

        except Exception as e:
            logger.warning(f"[暂存池] 存入失败（不影响回答）: {e}")


    def _build_context(self, retrieved_docs: List[Tuple[Document, float]]) -> str:
        """将检索结果构建为上下文字符串"""
        context_parts = []
        for i, (doc, score) in enumerate(retrieved_docs, 1):
            source = doc.metadata.get("source", "未知来源")
            article = doc.metadata.get("article_ref", "")
            ref = f"{source} {article}".strip()
            # 标注来源标签
            tags = []
            if doc.metadata.get("from_kg"):
                tags.append("图谱扩展")
            if doc.metadata.get("from_web"):
                web_src = doc.metadata.get("web_source", "网络")
                tags.append(f"联网-{web_src}")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            context_parts.append(
                f"【文档{i}】（来源：{ref}，相关度：{score:.2f}{tag_str}）\n{doc.page_content}"
            )
        return "\n\n---\n\n".join(context_parts)

    def _build_system_prompt(self, context: str, session_id: str) -> str:
        """构建带历史记忆的系统提示词"""
        history_context = memory_manager.build_history_context(session_id)
        if history_context:
            history_section = HISTORY_SECTION_TEMPLATE.format(history=history_context)
        else:
            history_section = ""
        return LEGAL_SYSTEM_PROMPT.format(
            history_section=history_section,
            context=context,
        )

    # ── LLM 调用 ──────────────────────────────────────────────────────────────
    def _call_llm(
        self,
        prompt: str,
        system: str,
        llm_config_override: Optional[LLMConfig] = None,
    ) -> Tuple[str, Optional[str]]:
        """通过 llm_client 统一调用，支持本地/远程动态切换"""
        return llm_client.chat(prompt, system, config_override=llm_config_override)

    # ── 主查询入口 ────────────────────────────────────────────────────────────
    def query(
        self,
        question: str,
        session_id: str = None,
        top_k: int = None,
        enhance_mode_override: str = None,
        enable_kg_override: bool = None,
        llm_config_override: Optional[LLMConfig] = None,
        enable_rerank: bool = True,
        enable_web_search_override: Optional[bool] = None,
    ) -> AnswerResponse:
        """主查询入口

        Args:
            enhance_mode_override:      覆盖全局增强模式，"hyde" | "multi_query" | "off" | None
            enable_kg_override:         覆盖全局知识图谱开关，True | False | None
            llm_config_override:        单次请求级 LLM 配置覆盖
            enable_rerank:              是否启用 Rerank（默认 True，不可用时自动降级）
            enable_web_search_override: True=强制联网，False=强制关闭，None=按置信度自动判断
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        top_k = top_k or settings.top_k_retrieval
        # Rerank 时多取候选，重排后再截断
        fetch_k = top_k * 3 if enable_rerank and reranker.available else top_k

        # ── Step 1: 查询增强 ──────────────────────────────────────────────────
        search_queries, enhance_mode = query_enhancer.get_search_queries(
            question, mode_override=enhance_mode_override
        )
        logger.info(f"[{session_id}] 查询增强模式: {enhance_mode}, 查询数: {len(search_queries)}")

        # ── Step 2: 混合检索（多取候选供 Rerank 使用）────────────────────────
        retrieval_input = search_queries[0] if enhance_mode == "hyde" else search_queries
        logger.info(f"[{session_id}] 开始检索，原始问题: {question}，fetch_k={fetch_k}")
        retrieved = hybrid_retriever.retrieve(retrieval_input, k=fetch_k)

        # ── Step 2.5: Rerank ─────────────────────────────────────────────────
        if enable_rerank:
            retrieved = reranker.rerank(question, retrieved, top_k=top_k)
            logger.info(f"[{session_id}] Rerank 后保留 {len(retrieved)} 条")
        else:
            retrieved = retrieved[:top_k]

        # ── Step 3: 知识图谱扩展 ──────────────────────────────────────────────
        use_kg = enable_kg_override if enable_kg_override is not None else settings.enable_knowledge_graph
        if use_kg:
            kg_docs = legal_kg.expand_neighbors(
                retrieved,
                max_hops=settings.kg_max_hops,
                max_expand=settings.kg_max_expand,
            )
            for doc, score in kg_docs:
                doc.metadata["from_kg"] = True
            existing_keys = {doc.page_content[:100] for doc, _ in retrieved}
            new_kg = [(d, s) for d, s in kg_docs if d.page_content[:100] not in existing_keys]
            combined = retrieved + new_kg
            logger.info(f"[{session_id}] 知识图谱补充 {len(new_kg)} 条条文")
        else:
            combined = retrieved

        # ── Step 4: 联网检索补充 ──────────────────────────────────────────────
        should_web, web_reason = web_searcher.should_trigger(
            combined, force_enable=(enable_web_search_override is True)
        )
        if enable_web_search_override is False:
            should_web = False

        web_docs_added = 0
        if should_web:
            logger.info(f"[{session_id}] 触发联网检索，原因: {web_reason}")
            web_docs = web_searcher.search(question)
            if web_docs:
                existing_keys = {doc.page_content[:80] for doc, _ in combined}
                new_web = [
                    (doc, 0.5)
                    for doc in web_docs
                    if doc.page_content[:80] not in existing_keys
                ]
                combined = combined + new_web
                web_docs_added = len(new_web)
                logger.info(f"[{session_id}] 联网检索补充 {web_docs_added} 条文档")

                # ── 暂存到待审核池：后台线程异步写入，不阻塞当前回答 ─────────
                if new_web:
                    docs_to_stage = [doc for doc, _ in new_web]
                    threading.Thread(
                        target=self._stage_web_docs_to_pending_pool,
                        args=(docs_to_stage, question),
                        daemon=True,
                    ).start()

        if not combined:
            return AnswerResponse(
                answer="抱歉，知识库和网络均未找到相关法律条文，建议您咨询专业律师获取准确的法律意见。",
                sources=[],
                session_id=session_id,
            )

        # ── Step 5: 构建上下文（含历史摘要） ─────────────────────────────────
        memory_manager.add_turn(session_id, "user", question)

        context = self._build_context(combined)
        if settings.enable_lccp:
            # LCCP 模式：用四步结构化推理提示词替换普通提示词
            system_prompt = LCCP_SYSTEM_PROMPT + f"\n\n【参考法律文档】\n{context}"
        else:
            system_prompt = self._build_system_prompt(context, session_id)

        # ── Step 6: 调用 LLM ─────────────────────────────────────────────────
        logger.info(f"[{session_id}] 调用模型推理...")
        answer, thinking = self._call_llm(question, system_prompt, llm_config_override)

        # ── Step 6.5: LCCP 置信度评估 ─────────────────────────────────────────
        lccp_result = None
        if settings.enable_lccp:
            lccp_eval = lccp_confidence.evaluate_answer(answer, combined)
            lccp_conf, lccp_steps = lccp_confidence.compute_confidence(answer)
            lccp_result = {
                "confidence": round(lccp_conf, 3),
                "label": lccp_confidence.get_confidence_label(lccp_conf),
                "citation_check": lccp_eval["citation_check"],
                "warnings": lccp_eval["warnings"],
                "step_confidences": lccp_steps,
            }
            logger.info(f"[{session_id}] LCCP 置信度: {lccp_result['confidence']} ({lccp_result['label']})")

        # ── Step 7: 更新对话记忆 ──────────────────────────────────────────────
        memory_manager.add_turn(session_id, "assistant", answer)

        # ── Step 8: 构建响应 ──────────────────────────────────────────────────
        sources = [
            SourceDocument(
                content=doc.page_content[:300],
                source=doc.metadata.get("source", "未知"),
                page=doc.metadata.get("page"),
                score=round(score, 4),
                from_kg=doc.metadata.get("from_kg", False),
                from_web=doc.metadata.get("from_web", False),
                url=doc.metadata.get("url", ""),
            )
            for doc, score in combined
        ]

        # 构建 web_results 用于暂存池
        web_results = None
        if web_docs_added > 0:
            web_results = [
                {
                    "url": doc.metadata.get("url", ""),
                    "title": doc.metadata.get("source", "网络检索"),
                    "snippet": doc.page_content[:200],
                    "content": doc.page_content,
                    "score": 0.5,  # 网络检索文档默认分数
                }
                for doc, score in combined
                if doc.metadata.get("from_web", False)
            ]

        return AnswerResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,
            thinking=thinking,
            enhance_mode=enhance_mode,
            web_search_triggered=should_web,
            web_docs_count=web_docs_added,
            web_results=web_results,
            memory_info=memory_manager.get_session_info(session_id),
            lccp_result=lccp_result,
        )


    def query_stream(
        self,
        question: str,
        session_id: str = None,
        top_k: int = None,
        enhance_mode_override: str = None,
        enable_kg_override: bool = None,
        llm_config_override: Optional[LLMConfig] = None,
        enable_rerank: bool = True,
        enable_web_search_override: Optional[bool] = None,
    ) -> Generator[str, None, None]:
        """
        流式查询：先做检索/增强，再流式调用 LLM。
        先 yield 一条 JSON 元数据帧（sources/meta），再逐 token yield 答案文本。
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        top_k = top_k or settings.top_k_retrieval
        fetch_k = top_k * 3 if enable_rerank and reranker.available else top_k

        # Step 1-4: 同非流式，检索+增强+rerank+KG+联网（全部同步完成）
        search_queries, enhance_mode = query_enhancer.get_search_queries(
            question, mode_override=enhance_mode_override
        )
        retrieval_input = search_queries[0] if enhance_mode == "hyde" else search_queries
        retrieved = hybrid_retriever.retrieve(retrieval_input, k=fetch_k)

        if enable_rerank:
            retrieved = reranker.rerank(question, retrieved, top_k=top_k)
        else:
            retrieved = retrieved[:top_k]

        use_kg = enable_kg_override if enable_kg_override is not None else settings.enable_knowledge_graph
        if use_kg:
            kg_docs = legal_kg.expand_neighbors(retrieved, max_hops=settings.kg_max_hops, max_expand=settings.kg_max_expand)
            for doc, score in kg_docs:
                doc.metadata["from_kg"] = True
            existing_keys = {doc.page_content[:100] for doc, _ in retrieved}
            new_kg = [(d, s) for d, s in kg_docs if d.page_content[:100] not in existing_keys]
            combined = retrieved + new_kg
        else:
            combined = retrieved

        should_web, web_reason = web_searcher.should_trigger(combined, force_enable=(enable_web_search_override is True))
        if enable_web_search_override is False:
            should_web = False

        web_docs_added = 0
        if should_web:
            web_docs = web_searcher.search(question)
            if web_docs:
                existing_keys = {doc.page_content[:80] for doc, _ in combined}
                new_web = [(doc, 0.5) for doc in web_docs if doc.page_content[:80] not in existing_keys]
                combined = combined + new_web
                web_docs_added = len(new_web)
                if new_web:
                    docs_to_stage = [doc for doc, _ in new_web]
                    threading.Thread(target=self._stage_web_docs_to_pending_pool, args=(docs_to_stage, question), daemon=True).start()

        if not combined:
            # 无结果，直接返回提示
            yield "data:" + json.dumps({"type": "meta", "session_id": session_id, "sources": [], "enhance_mode": enhance_mode, "web_search_triggered": False, "web_docs_count": 0, "memory_info": {}}) + "\n\n"
            yield "data:" + json.dumps({"type": "text", "content": "抱歉，知识库和网络均未找到相关法律条文，建议您咨询专业律师获取准确的法律意见。"}) + "\n\n"
            yield "data:" + json.dumps({"type": "done"}) + "\n\n"
            return

        # Step 5: 构建上下文
        memory_manager.add_turn(session_id, "user", question)
        context = self._build_context(combined)
        if settings.enable_lccp:
            system_prompt = LCCP_SYSTEM_PROMPT + f"\n\n【参考法律文档】\n{context}"
        else:
            system_prompt = self._build_system_prompt(context, session_id)

        # 先发元数据帧（sources + meta）
        sources = [
            {
                "content": doc.page_content[:300],
                "source": doc.metadata.get("source", "未知"),
                "page": doc.metadata.get("page"),
                "score": round(score, 4),
                "from_kg": doc.metadata.get("from_kg", False),
                "from_web": doc.metadata.get("from_web", False),
                "url": doc.metadata.get("url", ""),
            }
            for doc, score in combined
        ]
        yield "data:" + json.dumps({
            "type": "meta",
            "session_id": session_id,
            "sources": sources,
            "enhance_mode": enhance_mode,
            "web_search_triggered": should_web,
            "web_docs_count": web_docs_added,
            "memory_info": memory_manager.get_session_info(session_id),
        }, ensure_ascii=False) + "\n\n"

        # Step 6: 流式输出 LLM 回答
        full_answer = []
        try:
            for chunk, chunk_type in llm_client.chat_stream(question, system_prompt, llm_config_override):
                if chunk_type == "thinking":
                    yield "data:" + json.dumps({"type": "thinking", "content": chunk}, ensure_ascii=False) + "\n\n"
                else:
                    full_answer.append(chunk)
                    yield "data:" + json.dumps({"type": "text", "content": chunk}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            logger.error(f"[stream] LLM 调用失败: {e}")
            yield "data:" + json.dumps({"type": "error", "content": str(e)}) + "\n\n"
            return

        # Step 7: 更新记忆
        full_answer_text = "".join(full_answer)
        memory_manager.add_turn(session_id, "assistant", full_answer_text)

        # Step 7.5: LCCP 置信度评估（附在 done 帧）
        lccp_result = None
        if settings.enable_lccp:
            lccp_eval = lccp_confidence.evaluate_answer(full_answer_text, combined)
            lccp_conf, lccp_steps = lccp_confidence.compute_confidence(full_answer_text)
            lccp_result = {
                "confidence": round(lccp_conf, 3),
                "label": lccp_confidence.get_confidence_label(lccp_conf),
                "citation_check": lccp_eval["citation_check"],
                "warnings": lccp_eval["warnings"],
                "step_confidences": lccp_steps,
            }

        yield "data:" + json.dumps({"type": "done", "lccp_result": lccp_result}, ensure_ascii=False) + "\n\n"


# 全局单例
rag_pipeline = RAGPipeline()
