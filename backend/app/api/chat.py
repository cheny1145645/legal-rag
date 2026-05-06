import logging
import copy
import asyncio
import json
import threading
import time

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.rag_pipeline import rag_pipeline
from app.core.llm_client import llm_client, LLMConfig
from app.core.vector_store import vector_store_manager
from app.models.schemas import QuestionRequest, AnswerResponse
from app.rag.pending_pool import get_pending_pool, PendingDocument
from app.rag.async_evaluator import get_async_evaluator

router = APIRouter(prefix="/api/chat", tags=["问答"])
logger = logging.getLogger(__name__)

# ── 中断标志注册表 ──────────────────────────────────────────────────────────
_abort_flags: dict[str, threading.Event] = {}
_session_last_used: dict[str, float] = {}


# ── 请求模型 ────────────────────────────────────────────────────────────────
class AbortRequest(BaseModel):
    session_key: str = Field(alias="sessionKey")
    model_config = {"populate_by_name": True}


def set_abort_flag(session_key: str) -> bool:
    """设置会话的中断标志，返回是否成功设置"""
    if session_key in _abort_flags:
        _abort_flags[session_key].set()
        return True
    return False


# ── 中断端点 ────────────────────────────────────────────────────────────────
@router.post("/abort")
async def chat_abort(body: AbortRequest):
    """中断指定会话的流式输出"""
    conv_id = body.session_key
    if conv_id in _abort_flags:
        _abort_flags[conv_id].set()
        return {"success": True, "message": "中断信号已发送"}
    return {"success": False, "message": "会话不存在或已完成"}


@router.post("/query", response_model=AnswerResponse)
async def query(request: QuestionRequest, background_tasks: BackgroundTasks):
    """法律问答主接口"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        llm_override = None
        if request.llm_provider or request.llm_ollama_model or request.llm_remote_model:
            base_cfg = llm_client.get_config()
            llm_override = copy.copy(base_cfg)
            if request.llm_provider:
                llm_override.provider = request.llm_provider
            if request.llm_ollama_model:
                llm_override.ollama_model = request.llm_ollama_model
            if request.llm_remote_base_url:
                llm_override.remote_base_url = request.llm_remote_base_url
            if request.llm_remote_api_key:
                llm_override.remote_api_key = request.llm_remote_api_key
            if request.llm_remote_model:
                llm_override.remote_model = request.llm_remote_model

        response = rag_pipeline.query(
            question=request.question,
            session_id=request.session_id,
            top_k=request.top_k,
            enhance_mode_override=request.enhance_mode,
            enable_kg_override=request.enable_kg,
            llm_config_override=llm_override,
            enable_rerank=request.enable_rerank if request.enable_rerank is not None else True,
            enable_web_search_override=request.enable_web_search,
        )
        
        # 异步评估网络搜索结果（利用用户阅读的空挡时间）
        if hasattr(response, 'web_results') and response.web_results:
            _schedule_web_evaluation(
                request.question,
                response.answer,
                response.web_results,
                background_tasks
            )
        
        return response
    except Exception as e:
        logger.error(f"问答失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def query_stream(request: QuestionRequest, background_tasks: BackgroundTasks):
    """流式法律问答接口（SSE）"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        llm_override = None
        if request.llm_provider or request.llm_ollama_model or request.llm_remote_model:
            base_cfg = llm_client.get_config()
            llm_override = copy.copy(base_cfg)
            if request.llm_provider:
                llm_override.provider = request.llm_provider
            if request.llm_ollama_model:
                llm_override.ollama_model = request.llm_ollama_model
            if request.llm_remote_base_url:
                llm_override.remote_base_url = request.llm_remote_base_url
            if request.llm_remote_api_key:
                llm_override.remote_api_key = request.llm_remote_api_key
            if request.llm_remote_model:
                llm_override.remote_model = request.llm_remote_model

        # 为会话创建中断标志
        conv_id = str(request.session_id) if request.session_id else f"anon_{time.time()}"
        abort_event = threading.Event()
        _abort_flags[conv_id] = abort_event

        # 收集流式输出以用于后续评估
        full_answer = []

        def generate():
            try:
                for chunk in rag_pipeline.query_stream(
                    question=request.question,
                    session_id=request.session_id,
                    top_k=request.top_k,
                    enhance_mode_override=request.enhance_mode,
                    enable_kg_override=request.enable_kg,
                    llm_config_override=llm_override,
                    enable_rerank=request.enable_rerank if request.enable_rerank is not None else True,
                    enable_web_search_override=request.enable_web_search,
                ):
                    # 每次迭代检查中断标志
                    if abort_event.is_set():
                        yield "data:" + json.dumps({"type": "aborted"}) + "\n\n"
                        return
                    yield chunk
                    # 收集答案内容
                    if chunk.startswith("data:"):
                        try:
                            data = json.loads(chunk[5:])
                            if data.get("type") == "text":
                                full_answer.append(data.get("content", ""))
                        except:
                            pass
            finally:
                # 流结束后清理标志
                _abort_flags.pop(conv_id, None)

        response = StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

        # 调度异步评估（流式结束后执行）
        if request.enable_web_search is None or request.enable_web_search:
            # 使用后台任务调度评估
            background_tasks.add_task(
                _schedule_stream_evaluation,
                request.question,
                "".join(full_answer),
                background_tasks
            )

        return response
    except Exception as e:
        logger.error(f"流式问答失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _schedule_web_evaluation(question: str, answer: str, web_results: list, background_tasks: BackgroundTasks):
    """
    调度网络搜索结果的异步评估

    Args:
        question: 用户问题
        answer: AI答案
        web_results: 网络搜索结果
        background_tasks: 后台任务
    """
    try:
        pending_pool = get_pending_pool()
        async_evaluator = get_async_evaluator()

        # 1. 获取暂存池中待评估的文档（由 rag_pipeline 已经写入）
        all_docs = pending_pool.get_by_status(should_keep=None, limit=50)
        # 筛选出与当前查询相关的文档
        relevant_doc_ids = [
            doc.id for doc in all_docs
            if doc.query == question and doc.source_type == 'web'
        ]

        if not relevant_doc_ids:
            logger.info(f"暂存池中没有与当前查询相关的待评估文档: {question[:30]}")
            return

        # 2. 异步评估（后台任务，不阻塞用户响应）
        async def evaluate_all():
            try:
                await async_evaluator.batch_evaluate(relevant_doc_ids, question, answer)
                logger.info(f"✅ 网络搜索结果评估完成：{len(relevant_doc_ids)} 个文档")
            except Exception as e:
                logger.error(f"网络搜索结果评估失败: {e}")

        background_tasks.add_task(evaluate_all)

        logger.info(f"📝 开始异步评估 {len(relevant_doc_ids)} 个网络搜索结果")

    except Exception as e:
        logger.error(f"调度网络搜索评估失败: {e}")


def _schedule_stream_evaluation(question: str, answer: str, background_tasks: BackgroundTasks):
    """
    流式接口的评估调度（不需要 web_results，从暂存池获取）

    Args:
        question: 用户问题
        answer: AI答案
        background_tasks: 后台任务
    """
    _schedule_web_evaluation(question, answer, [], background_tasks)

