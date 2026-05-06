"""
Reranker 模块

使用 BGE-Reranker-v2-m3（FlagEmbedding）对混合检索候选进行交叉编码器重排，
显著提升 top-k 精度，尤其在法律专业术语和长文本匹配场景下效果明显。

工作流程：
  混合检索取 top_k * rerank_factor 候选
  → Cross-Encoder 打分
  → 取重排后前 top_k 条送入 LLM
"""
import logging
import os
from typing import List, Tuple, Optional

from langchain.schema import Document

from app.config import settings

logger = logging.getLogger(__name__)

def _get_reranker_model_path() -> str:
    """优先从 settings 读取，其次环境变量，最后用默认路径"""
    if settings.reranker_model:
        return settings.reranker_model
    return os.environ.get("RERANKER_MODEL", "D:/legal-rag/models/bge-reranker-v2-m3")


class Reranker:
    """
    BGE-Reranker-v2-m3 重排器。

    首次调用时懒加载模型（避免启动时占用显存/内存）。
    不可用时自动降级，返回原始排序结果，不影响主流程。
    """

    def __init__(self):
        self._model = None
        self._available = None  # None=未检测, True/False=检测结果

    # ── 懒加载 ───────────────────────────────────────────────────────────────
    def _check_memory(self, required_gb: float = 3.0) -> bool:
        """检查可用内存是否足够加载模型"""
        try:
            import psutil
            avail_gb = psutil.virtual_memory().available / (1024 ** 3)
            if avail_gb < required_gb:
                logger.warning(
                    f"Reranker 需要约 {required_gb:.1f} GB 内存，当前可用 {avail_gb:.1f} GB，跳过加载"
                )
                return False
        except ImportError:
            pass  # psutil 不可用时不检查，继续尝试加载
        return True

    def _load_model(self) -> bool:
        """尝试加载模型，返回是否成功"""
        if self._available is not None:
            return self._available

        model_path = _get_reranker_model_path()
        if not model_path or not os.path.exists(model_path):
            logger.info("Reranker 模型路径未配置或不存在，Rerank 功能已禁用")
            self._available = False
            return False

        # 内存预检查：CPU 上加载模型峰值需要约 5 GB（模型本身 2GB + 推理计算图 2-3GB）
        if not self._check_memory(required_gb=5.5):
            self._available = False
            return False

        try:
            from FlagEmbedding import FlagReranker
            import torch

            logger.info(f"加载 Reranker 模型: {model_path}")
            # 强制离线，避免尝试联网更新
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

            # CPU 模式下 use_fp16=False（CPU 不支持 fp16 推理，设 True 反而会转回 float32 并额外消耗内存）
            use_fp16 = torch.cuda.is_available()
            self._model = FlagReranker(model_path, use_fp16=use_fp16)
            self._available = True
            logger.info(f"BGE-Reranker-v2-m3 加载成功（fp16={use_fp16}）")
        except ImportError:
            logger.warning(
                "FlagEmbedding 未安装，Rerank 功能不可用。"
                "可运行 pip install FlagEmbedding 启用。"
            )
            self._available = False
        except Exception as e:
            logger.warning(f"Reranker 加载失败: {e}，将使用原始排序")
            self._available = False
        return self._available

    @property
    def available(self) -> bool:
        return self._load_model()

    # ── 重排主方法 ────────────────────────────────────────────────────────────
    def rerank(
        self,
        query: str,
        candidates: List[Tuple[Document, float]],
        top_k: int,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[Document, float]]:
        """
        对候选文档列表重排，返回重排后的 top_k 条。

        Args:
            query:           用户原始问题（不用增强后的查询）
            candidates:      混合检索返回的候选列表（文档, 原始分数）
            top_k:           最终保留条数
            score_threshold: Rerank 分数阈值（0~1），低于此值的 chunk 直接过滤。
                             默认 0.15，用于去除语义方向相反或完全不相关的段落。
                             至少保留 1 条（全部低于阈值时保留最高分一条）。

        Returns:
            重排后的 (Document, rerank_score) 列表，已截断为 top_k
        """
        if not candidates:
            return candidates

        if not self._load_model():
            # 降级：直接返回原始 top_k
            return candidates[:top_k]

        # 阈值：优先用传入参数，其次读配置
        if score_threshold is None:
            score_threshold = settings.rerank_score_threshold

        try:
            pairs = [(query, doc.page_content) for doc, _ in candidates]
            # batch_size=4：每次推理4对，避免内存峰值过高导致进程被 kill
            # max_length=512：截断超长法律文本，减少显存/内存压力
            scores = self._model.compute_score(pairs, normalize=True, batch_size=4, max_length=512)

            # scores 可能是 float（单条）或 list
            if isinstance(scores, float):
                scores = [scores]

            ranked = sorted(
                zip(candidates, scores),
                key=lambda x: x[1],
                reverse=True,
            )

            # ── 阈值过滤：低相关性 chunk 直接丢弃 ──────────────────────────
            filtered = [
                (doc, float(score))
                for (doc, _orig), score in ranked
                if float(score) >= score_threshold
            ]

            # 保底：至少保留最高分一条，避免空上下文
            if not filtered and ranked:
                (doc, _orig), score = ranked[0]
                filtered = [(doc, float(score))]
                logger.info(
                    f"Rerank 阈值过滤后无结果，保留最高分一条（score={float(score):.3f}）"
                )

            result = filtered[:top_k]
            filtered_out = len(candidates) - len(filtered)
            logger.info(
                f"Rerank 完成：{len(candidates)} 候选 → 阈值过滤掉 {filtered_out} 条"
                f"（threshold={score_threshold}） → top-{len(result)}，"
                f"最高分={result[0][1]:.3f}，最低分={result[-1][1]:.3f}"
            )
            return result

        except Exception as e:
            logger.warning(f"Rerank 执行失败: {e}，降级使用原始排序")
            return candidates[:top_k]


# 全局单例
reranker = Reranker()
