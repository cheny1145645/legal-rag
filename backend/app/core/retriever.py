import logging
from typing import List, Tuple, Dict, Optional

import jieba
from langchain.schema import Document
from rank_bm25 import BM25Okapi

from app.config import settings
from app.core.knowledge_graph import legal_kg
from app.core.vector_store import vector_store_manager

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    混合检索器 + GLVR图谱增强 + QAWRF动态权重融合
    
    融合BM25关键词检索、向量语义检索、图谱权威度重排（S_GLRF），
    通过加权融合策略提升法律专业术语的召回率。
    
    支持懒加载：BM25索引首次调用时初始化（从向量库文档构建）。
    """

    _bm25_initialized = False  # 类级别的懒加载标志

    def __init__(self):
        self._bm25_corpus: List[str] = []
        self._bm25_docs: List[Document] = []
        self._bm25: BM25Okapi = None
        self._pagerank_cache: Dict[str, float] = {}  # GLVR: PageRank缓存
        logger.info("[Retriever] HybridRetriever 实例已创建（懒加载模式）")

    # ── 懒加载初始化 ─────────────────────────────────────────────────────
    def _ensure_bm25_initialized(self):
        """
        懒加载：确保 BM25 索引已构建。
        首次调用时从向量库加载文档构建 BM25 索引。
        """
        if HybridRetriever._bm25_initialized and self._bm25 is not None:
            return
        
        logger.info("[Retriever] 懒加载 BM25 索引...")
        try:
            # 从向量库获取全部文档构建 BM25
            vs = vector_store_manager.get_vectorstore()
            # 获取全部文档（使用 get() 而非 similarity_search 避免分数排序）
            col = vector_store_manager._get_client().get_or_create_collection(
                vector_store_manager.COLLECTION_NAME
            )
            result = col.get(include=["metadatas", "documents"])
            
            docs = []
            for metadata, content in zip(result.get("metadatas", []), result.get("documents", [])):
                if content:
                    docs.append(Document(
                        page_content=content,
                        metadata=metadata or {}
                    ))
            
            if docs:
                self.build_bm25_index(docs)
                HybridRetriever._bm25_initialized = True
                logger.info(f"[Retriever] BM25 索引懒加载完成，共 {len(docs)} 条文档")
            else:
                logger.warning("[Retriever] 向量库为空，跳过 BM25 索引构建")
        except Exception as e:
            logger.error(f"[Retriever] BM25 懒加载失败: {e}")
            raise

    def build_bm25_index(self, documents: List[Document]):
        self._bm25_docs = documents
        tokenized = [list(jieba.cut(doc.page_content)) for doc in documents]
        self._bm25 = BM25Okapi(tokenized)
        logger.info(f"BM25索引构建完成（jieba分词），共 {len(documents)} 条文档")
    
    def _compute_pagerank(self):
        """GLVR: 计算PageRank权威度（只在首次调用时计算，结果缓存）"""
        if not self._pagerank_cache:
            self._pagerank_cache = legal_kg.compute_pagerank()
            logger.info(f"[GLVR] PageRank计算完成，{len(self._pagerank_cache)}个节点")
        return self._pagerank_cache

    def _glvr_rerank(
        self,
        results: List[Tuple[Document, float]],
        gamma: float = 0.3,
    ) -> List[Tuple[Document, float]]:
        """
        GLVR: 图谱引导的向量重排序
        
        公式: S_GLVR(d,q) = (1-γ)*cos(e_q,e_d) + γ*Auth(d)
        
        Args:
            results: 原始检索结果
            gamma: 图权重系数（默认0.3）
        
        Returns:
            重排后的结果
        """
        if not results:
            return results
        
        # 首次调用时计算PageRank
        if not self._pagerank_cache:
            self._compute_pagerank()
        
        reranked = []
        for doc, vector_score in results:
            source = doc.metadata.get("source", "unknown")
            article_ref = doc.metadata.get("article_ref", "")
            
            # 获取权威度分数
            auth_score = legal_kg.get_authority_score(
                source, article_ref, self._pagerank_cache
            )
            
            # GLVR融合分数：归一化向量分数 + 权威度
            # 假设vector_score已归一化到[0,1]，直接线性融合
            final_score = (1 - gamma) * vector_score + gamma * auth_score
            reranked.append((doc, final_score))
        
        # 按新分数排序
        reranked = sorted(reranked, key=lambda x: x[1], reverse=True)
        return reranked

    # ── QAWRF: 查询类型判别器 ────────────────────────────────────────────────
    def _classify_query_type(self, query: str) -> float:
        """
        QAWRF: 判别查询的精确检索倾向得分 τ(q)
        
        公式：τ(q) = sigmoid(w1*条文标识 + w2*专有名词比例 + w3*TF-IDF峰值)
        
        返回 τ ∈ (0,1)，越接近1表示越偏精确匹配（BM25优先）
        越接近0表示越偏语义理解（向量优先）
        """
        import math
        
        # 权重参数
        w1, w2, w3 = 2.0, 1.5, 1.0
        
        # 特征1: 是否包含条文编号（"第X条"、"第X条第Y款"等）
        import re
        article_pattern = re.compile(r"第[一二三四五六七八九十百千\d]+条")
        has_article = 1.0 if article_pattern.search(query) else 0.0
        
        # 特征2: 专有名词比例（法律术语）
        from app.core.vector_store import vector_store_manager
        legal_terms = {"劳动法","劳动合同法","民法典","刑法","诉讼法","司法解释",
                     "工伤","违约","侵权","赔偿","补偿","责任","义务","权利",
                     "用人单位","劳动者","第三人","法定代表人","代理人"}
        query_terms = set(jieba.cut(query))
        term_ratio = len(query_terms & legal_terms) / max(len(query_terms), 1)
        
        # 特征3: 查询长度（短查询通常更精确）
        query_len = len(query)
        length_score = min(query_len / 20.0, 1.0)  # 20字为界
        
        # 计算 τ
        z = w1 * has_article + w2 * term_ratio + w3 * (1 - length_score)
        tau = 1.0 / (1.0 + math.exp(-z))  # sigmoid
        
        logger.info(f"[QAWRF] 查询类型判别: τ={tau:.3f} (article={has_article}, term_ratio={term_ratio:.3f})")
        return tau

    def _qawrf_retrieve(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """
        QAWRF: 查询感知动态权重融合检索
        
        公式: S_QAWRF = τ(q)*S_BM25 + (1-τ(q))*S_vec
        """
        fetch_k = k * 2
        
        # 动态计算查询类型权重
        tau = self._classify_query_type(query)
        
        # 向量检索
        vector_results = vector_store_manager.similarity_search_with_score(query, k=fetch_k)
        
        # BM25检索
        bm25_results = self._bm25_search(query, k=fetch_k)
        
        # 合并结果，去重
        rrf_k = 60
        score_map: dict = {}
        
        # 向量结果
        for rank, (doc, _) in enumerate(vector_results, start=1):
            key = doc.page_content[:100]
            rrf_score = 1.0 / (rrf_k + rank)
            score_map[key] = (doc, (1 - tau) * rrf_score)
        
        # BM25结果
        for rank, (doc, _) in enumerate(bm25_results, start=1):
            key = doc.page_content[:100]
            rrf_score = 1.0 / (rrf_k + rank)
            if key in score_map:
                d, s = score_map[key]
                score_map[key] = (d, s + tau * rrf_score * (settings.bm25_weight / settings.vector_weight))
            else:
                score_map[key] = (doc, tau * rrf_score)
        
        merged = sorted(score_map.values(), key=lambda x: x[1], reverse=True)[:k]
        return merged

    def _bm25_search(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """BM25关键词检索"""
        if self._bm25 is None or not self._bm25_docs:
            return []
        tokenized_query = list(jieba.cut(query))
        scores = self._bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = [(self._bm25_docs[i], float(scores[i])) for i in top_indices if scores[i] > 0]
        return results

    def _single_retrieve(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """对单个查询执行混合检索，返回融合后的 top-k 结果"""
        fetch_k = k * 2  # 多取一些再融合

        # 向量检索
        vector_results = vector_store_manager.similarity_search_with_score(query, k=fetch_k)

        # BM25检索
        bm25_results = self._bm25_search(query, k=fetch_k)

        # RRF（Reciprocal Rank Fusion）融合
        # 公式：score = 1 / (k + rank)，其中 k 常取 60
        rrf_k = 60
        score_map: dict[str, Tuple[Document, float]] = {}

        # 向量结果按排名计算 RRF 分数
        for rank, (doc, _) in enumerate(vector_results, start=1):
            key = doc.page_content[:100]
            rrf_score = 1.0 / (rrf_k + rank)
            score_map[key] = (doc, settings.vector_weight * rrf_score)

        # BM25 结果按排名计算 RRF 分数并累加
        for rank, (doc, _) in enumerate(bm25_results, start=1):
            key = doc.page_content[:100]
            rrf_score = 1.0 / (rrf_k + rank)
            if key in score_map:
                d, s = score_map[key]
                score_map[key] = (d, s + settings.bm25_weight * rrf_score)
            else:
                score_map[key] = (doc, settings.bm25_weight * rrf_score)

        merged = sorted(score_map.values(), key=lambda x: x[1], reverse=True)[:k]
        return merged

    def _merge_multi_results(
        self,
        multi_results: List[List[Tuple[Document, float]]],
        k: int,
    ) -> List[Tuple[Document, float]]:
        """
        合并多路查询的检索结果，去重后取最高分。
        以文档内容前100字作为去重 key。
        """
        best_map: dict[str, Tuple[Document, float]] = {}
        for results in multi_results:
            for doc, score in results:
                key = doc.page_content[:100]
                if key not in best_map or score > best_map[key][1]:
                    best_map[key] = (doc, score)

        merged = sorted(best_map.values(), key=lambda x: x[1], reverse=True)[:k]
        return merged

    def retrieve(self, query: str, k: int = None, enable_glvr: bool = True, enable_qawrf: bool = None) -> List[Tuple[Document, float]]:
        """
        混合检索主入口 + QAWRF + GLVR
        
        若 query 为列表（Multi-Query 模式），对每个子查询分别检索后合并；
        否则直接对单个查询检索。
        
        Args:
            k: 返回结果数量
            enable_glvr: 是否启用GLVR图谱重排（默认开启，可通过settings.enable_glvr控制）
            enable_qawrf: 是否启用QAWRF动态权重（默认跟随settings）
        """
        # 懒加载：确保 BM25 已初始化
        if settings.lazy_load_enabled:
            self._ensure_bm25_initialized()
        
        k = k or settings.top_k_retrieval
        enable_glvr = enable_glvr and settings.enable_glvr  # 合并配置
        enable_qawrf = enable_qawrf if enable_qawrf is not None else settings.enable_qawrf

        logger.info(f"[Retriever] 收到检索请求: query='{query[:30]}...' k={k} GLVR={enable_glvr} QAWRF={enable_qawrf}")
        
        if isinstance(query, list):
            # Multi-Query：并行检索多个子查询
            multi_results = [self._single_retrieve(q, k) for q in query]
            merged = self._merge_multi_results(multi_results, k)
            logger.info(f"[Retriever] Multi-Query 检索完成（{len(query)} 路），返回 {len(merged)} 条结果")
        else:
            # QAWRF 或 标准 RRF
            if enable_qawrf:
                merged = self._qawrf_retrieve(query, k)
                logger.info(f"[QAWRF] 检索完成，返回 {len(merged)} 条结果")
            else:
                merged = self._single_retrieve(query, k)
                logger.info(f"[Retriever] 混合检索完成，返回 {len(merged)} 条结果")

        # GLVR图谱增强重排
        if enable_glvr:
            merged = self._glvr_rerank(merged, gamma=settings.glvr_gamma)
            logger.info(f"[GLVR] 重排完成，返回 {len(merged)} 条结果")

        return merged


# 全局单例
hybrid_retriever = HybridRetriever()
