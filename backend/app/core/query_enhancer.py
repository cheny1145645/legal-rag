import logging
from typing import List, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# ── HyDE 系统提示词 ──────────────────────────────────────────────────────────
HYDE_SYSTEM_PROMPT = """你是一名中国法律专家。请根据用户的法律问题，生成一段简短的假设性法律条文回答（100字以内）。
要求：
1. 使用正式的法律条文语言和术语
2. 直接给出法律依据和结论，不要解释
3. 包含可能相关的法律概念（如违约责任、侵权责任等）
4. 不需要引用具体条文编号
只输出假设性答案文本，不要有任何前缀或说明。"""

# ── Multi-Query 系统提示词 ───────────────────────────────────────────────────
MULTI_QUERY_SYSTEM_PROMPT = """你是一名中国法律检索专家。请将用户的问题改写为3个不同角度的法律检索子查询。
要求：
1. 每个子查询独占一行
2. 使用正式法律术语（口语转书面语）
3. 从不同角度表达同一法律问题（当事人角度/法律关系角度/救济途径角度）
4. 每个子查询不超过30字
只输出3行子查询，不要编号或其他内容。"""


class QueryEnhancer:
    """
    查询增强器

    支持两种策略（通过 settings.query_enhance_mode 切换）：
    - hyde      : 生成假设性文档嵌入（HyDE），用生成的"假设答案"做向量检索
    - multi_query: 将问题扩写为3个子查询，多路并行检索后去重合并
    - off       : 不增强，直接透传原始问题
    """

    def __init__(self):
        pass  # llm_client 延迟导入，避免循环依赖

    # ── 内部：调用 LLM ────────────────────────────────────────────────────────
    def _call_llm(self, user_content: str, system_prompt: str) -> str:
        """通过全局 llm_client 调用，temperature=0 保证输出稳定"""
        from app.core.llm_client import llm_client, LLMConfig
        import copy
        # 克隆当前配置，覆盖 temperature
        cfg = copy.copy(llm_client.get_config())
        cfg.temperature = 0.0
        try:
            content, _ = llm_client.chat(user_content, system_prompt, config_override=cfg)
            return content.strip()
        except Exception as e:
            logger.warning(f"QueryEnhancer LLM 调用失败: {e}")
            return ""

    # ── HyDE ─────────────────────────────────────────────────────────────────
    def generate_hyde_doc(self, question: str) -> str:
        """
        生成假设性文档（Hypothetical Document Embedding）。
        返回生成的假设答案文本；失败时返回空字符串（降级到原始问题）。
        """
        logger.info(f"[HyDE] 生成假设文档: {question[:30]}...")
        result = self._call_llm(question, HYDE_SYSTEM_PROMPT)
        if result:
            logger.info(f"[HyDE] 假设文档: {result[:60]}...")
        return result

    # ── Multi-Query ──────────────────────────────────────────────────────────
    def generate_sub_queries(self, question: str) -> List[str]:
        """
        将问题扩写为多个子查询。
        返回子查询列表；失败时返回 [question]（降级到原始问题）。
        """
        logger.info(f"[MultiQuery] 扩写子查询: {question[:30]}...")
        result = self._call_llm(question, MULTI_QUERY_SYSTEM_PROMPT)
        if not result:
            return [question]

        queries = [q.strip() for q in result.splitlines() if q.strip()]
        # 过滤掉太短/明显无效的行
        queries = [q for q in queries if len(q) >= 5][:3]

        if not queries:
            return [question]

        # 始终把原始问题也加入，保证召回不遗漏
        all_queries = [question] + queries
        logger.info(f"[MultiQuery] 子查询列表: {all_queries}")
        return all_queries

    # ── 主入口 ───────────────────────────────────────────────────────────────
    def get_search_queries(
        self, question: str, mode_override: str = None
    ) -> Tuple[List[str], str]:
        """
        根据配置返回用于检索的查询列表和增强模式名称。

        Args:
            mode_override: 前端运行时覆盖值，"hyde" | "multi_query" | "off" | None。
                           None 时跟随 settings.query_enhance_mode 全局配置。

        Returns:
            (queries, mode)
            - queries: 用于检索的字符串列表，HyDE 返回 [hyde_doc]，
                       Multi-Query 返回 [original, sub1, sub2, sub3]，
                       off 返回 [original]
            - mode:    实际使用的模式名称（用于日志/前端展示）
        """
        mode = (mode_override or settings.query_enhance_mode).lower()

        if mode == "hyde":
            hyde_doc = self.generate_hyde_doc(question)
            if hyde_doc:
                return [hyde_doc], "hyde"
            # 降级
            logger.warning("[HyDE] 生成失败，降级为原始问题检索")
            return [question], "off"

        elif mode == "multi_query":
            queries = self.generate_sub_queries(question)
            return queries, "multi_query"

        else:
            return [question], "off"


# 全局单例
query_enhancer = QueryEnhancer()
