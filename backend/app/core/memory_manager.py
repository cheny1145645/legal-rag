import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)

# ── 压缩提示词 ───────────────────────────────────────────────────────────────
COMPRESS_SYSTEM_PROMPT = """你是一名对话历史压缩助手。请将以下法律咨询对话历史压缩为简洁的摘要。
要求：
1. 保留所有关键法律问题、当事人描述的核心事实、已给出的法律结论
2. 去除冗余内容、客套话、重复信息
3. 摘要不超过300字
4. 使用第三方视角描述（"用户询问…""助手回答…"）
只输出摘要文本，不要有任何前缀。"""


@dataclass
class Turn:
    """单轮对话"""
    role: str   # "user" | "assistant"
    content: str


@dataclass
class SessionMemory:
    """单个会话的记忆状态"""
    turns: List[Turn] = field(default_factory=list)
    summary: str = ""           # 已压缩的历史摘要
    total_turns: int = 0        # 历史总轮数（含已压缩部分）


class ConversationMemoryManager:
    """
    对话记忆管理器

    策略：
    - 每个 session 保留最近 N 轮（settings.memory_recent_turns，默认6轮）
    - 当总轮数超过阈值（settings.memory_compress_threshold，默认10轮）时，
      将最早的一批轮次压缩为文字摘要
    - 构建 prompt 时：摘要（如有）+ 最近 N 轮 → 完整上下文
    """

    def __init__(self):
        self._sessions: Dict[str, SessionMemory] = {}

    # ── 会话管理 ─────────────────────────────────────────────────────────────
    def get_or_create(self, session_id: str) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory()
        return self._sessions[session_id]

    def delete_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def session_count(self) -> int:
        return len(self._sessions)

    # ── 添加对话轮次 ─────────────────────────────────────────────────────────
    def add_turn(self, session_id: str, role: str, content: str):
        mem = self.get_or_create(session_id)
        mem.turns.append(Turn(role=role, content=content))
        mem.total_turns += 1

        # 超过阈值则触发压缩
        threshold = settings.memory_compress_threshold
        recent = settings.memory_recent_turns
        if len(mem.turns) > threshold:
            self._compress(mem, keep_recent=recent)

    # ── 压缩历史 ─────────────────────────────────────────────────────────────
    def _compress(self, mem: SessionMemory, keep_recent: int):
        """将最早的 (len-keep_recent) 轮压缩为摘要，保留最近 keep_recent 轮"""
        to_compress = mem.turns[:-keep_recent]
        mem.turns = mem.turns[-keep_recent:]

        if not to_compress:
            return

        # 构建待压缩文本
        history_text = "\n".join(
            f"{'用户' if t.role == 'user' else '助手'}: {t.content}"
            for t in to_compress
        )

        # 如果已有摘要，把旧摘要也一起压缩进去
        if mem.summary:
            history_text = f"[之前摘要]\n{mem.summary}\n\n[新增对话]\n{history_text}"

        new_summary = self._call_compress(history_text)
        if new_summary:
            mem.summary = new_summary
            logger.info(
                f"[Memory] 压缩 {len(to_compress)} 轮 → 摘要 {len(new_summary)} 字"
            )
        else:
            # 压缩失败时，把旧摘要和要压缩的内容拼接（兜底）
            fallback = "\n".join(
                f"{'用户' if t.role == 'user' else '助手'}: {t.content[:100]}"
                for t in to_compress
            )
            mem.summary = (mem.summary + "\n" + fallback).strip()
            logger.warning("[Memory] 压缩调用失败，使用截断拼接作为兜底")

    def _call_compress(self, history_text: str) -> str:
        from app.core.llm_client import llm_client, LLMConfig
        import copy
        cfg = copy.copy(llm_client.get_config())
        cfg.temperature = 0.0
        try:
            content, _ = llm_client.chat(history_text, COMPRESS_SYSTEM_PROMPT, config_override=cfg)
            return content.strip()
        except Exception as e:
            logger.warning(f"[Memory] 压缩 LLM 调用失败: {e}")
            return ""

    # ── 构建历史上下文字符串（注入 prompt） ──────────────────────────────────
    def build_history_context(self, session_id: str) -> str:
        """
        返回可直接插入系统 prompt 的历史上下文字符串。
        格式：
          [历史对话摘要]
          ...摘要内容...

          [最近对话记录]
          用户: ...
          助手: ...
        """
        mem = self._sessions.get(session_id)
        if not mem:
            return ""

        parts = []
        if mem.summary:
            parts.append(f"[历史对话摘要]\n{mem.summary}")

        if mem.turns:
            recent_lines = []
            for t in mem.turns[:-1]:  # 排除最后一条（当前问题由 query 传入）
                label = "用户" if t.role == "user" else "助手"
                # 历史内容截断避免 prompt 过长
                content_preview = t.content[:400] + ("..." if len(t.content) > 400 else "")
                recent_lines.append(f"{label}: {content_preview}")
            if recent_lines:
                parts.append("[最近对话记录]\n" + "\n".join(recent_lines))

        return "\n\n".join(parts)

    # ── 获取摘要信息（供 API 返回） ───────────────────────────────────────────
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        mem = self._sessions.get(session_id)
        if not mem:
            return None
        return {
            "total_turns": mem.total_turns,
            "recent_turns": len(mem.turns),
            "has_summary": bool(mem.summary),
            "summary_preview": mem.summary[:80] + "..." if len(mem.summary) > 80 else mem.summary,
        }


# 全局单例
memory_manager = ConversationMemoryManager()
