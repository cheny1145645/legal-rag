import logging
from typing import List, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain.schema import Document

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """
    向量数据库管理器（ChromaDB）
    
    使用BGE-M3嵌入模型，支持中英文混合法律文本检索。
    """

    COLLECTION_NAME = "legal_docs"

    def __init__(self):
        self._embeddings = None
        self._vectorstore = None
        self._client = None

    def initialize_embeddings(self):
        """
        应用启动时主动初始化嵌入模型，避免首次调用时反复加载导致显存累积溢出。

        调用时机：FastAPI 的 startup 事件中调用一次。
        """
        _ = self._get_embeddings()
        logger.info("嵌入模型预加载完成")

    def _get_embeddings(self):
        if self._embeddings is None:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"加载嵌入模型: {settings.embedding_model}，设备: {device}")

            # model_kwargs 只传 device，torch_dtype 在此版本 sentence-transformers 不被支持
            model_kwargs = {
                "device": device,
            }

            self._embeddings = HuggingFaceBgeEmbeddings(
                model_name=settings.embedding_model,
                model_kwargs=model_kwargs,
                encode_kwargs={
                    "normalize_embeddings": True,
                    "batch_size": 32,  # 限制批处理大小，避免显存溢出
                },
                query_instruction="为这个句子生成表示以用于检索相关文章：",
            )

            # CUDA 下手动转半精度，减少显存占用
            if device == "cuda":
                try:
                    self._embeddings.client = self._embeddings.client.half()
                    logger.info("嵌入模型已转换为 float16 半精度")
                except Exception as e:
                    logger.warning(f"float16 转换失败，保持 float32: {e}")

        return self._embeddings

    def _get_client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=settings.chroma_db_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def get_vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                client=self._get_client(),
                collection_name=self.COLLECTION_NAME,
                embedding_function=self._get_embeddings(),
            )
        return self._vectorstore

    def add_documents(self, documents: List[Document]) -> int:
        """
        将文档块分批添加到向量数据库

        批处理大小设为 10（极端保守），避免 CUDA OOM。
        模型在应用启动时已预加载，此处不再重复加载。
        """
        BATCH_SIZE = 10  # 极度保守的批大小，防止显存累积溢出
        vs = self.get_vectorstore()

        total = len(documents)
        logger.info(f"开始入库，共 {total} 个文档块，分批大小: {BATCH_SIZE}")

        for i in range(0, total, BATCH_SIZE):
            batch = documents[i: i + BATCH_SIZE]
            try:
                logger.info(f"  批次 {i // BATCH_SIZE + 1}: 正在向量化 {len(batch)} 条...")
                vs.add_documents(batch)
                logger.info(f"  批次 {i // BATCH_SIZE + 1}: 入库完成 {len(batch)} 条 "
                            f"({i + len(batch)}/{total})")
            except Exception as e:
                logger.error(f"  批次 {i // BATCH_SIZE + 1} 入库失败: {e}")
                # 继续处理下一批次，不中断整个流程
                continue

        count = self.get_doc_count()
        logger.info(f"全部入库完成，当前总文档块数: {count}")
        return count

    def get_doc_count(self) -> int:
        """获取向量库中文档总数"""
        try:
            client = self._get_client()
            col = client.get_or_create_collection(self.COLLECTION_NAME)
            return col.count()
        except Exception:
            return 0

    def similarity_search_with_score(
        self, query: str, k: int = 5
    ) -> List[Tuple[Document, float]]:
        """向量相似度检索，返回文档和分数"""
        vs = self.get_vectorstore()
        results = vs.similarity_search_with_relevance_scores(query, k=k)
        return results

    @staticmethod
    def _clean_text(text: str) -> str:
        """清除字间多余空格（PDF 解析残留），保留段落换行"""
        import re
        # 把被单个空格分隔的单字中文合并（如"劳 动 合 同" → "劳动合同"）
        # 规则：单个汉字 + 空格 + 单个汉字 → 合并，连续处理
        cleaned = re.sub(r'(?<=[\u4e00-\u9fff])\s(?=[\u4e00-\u9fff])', '', text)
        # 多个连续空白压成一个
        cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
        return cleaned.strip()

    def get_sources_summary(self) -> dict:
        """
        返回知识库条文分组统计，结构：
        {
          "categories": {
            "法律文档": { "total": n, "sources": { name: {"count":n, "samples":[...]} } },
            "网络检索": { "total": n, "sources": { name: {"count":n, "samples":[...]} } }
          },
          "total": n
        }
        """
        import re
        try:
            client = self._get_client()
            col = client.get_or_create_collection(self.COLLECTION_NAME)
            total = col.count()
            if total == 0:
                return {"categories": {}, "total": 0}

            result = col.get(include=["metadatas", "documents"])
            metadatas = result.get("metadatas") or []
            documents = result.get("documents") or []

            law_sources = {}   # 法律文档
            web_sources = {}   # 网络检索

            for meta, doc in zip(metadatas, documents):
                raw_src = (meta.get("source", "未知来源") if meta else "未知来源") or "未知来源"
                is_web = raw_src.startswith("网络检索")

                # 清理 source 名称
                if is_web:
                    # "网络检索 - 标题文字" → 只保留标题部分，清洗空格
                    title = re.sub(r'^网络检索\s*[-–]\s*', '', raw_src)
                    title = self._clean_text(title)
                    if not title:
                        title = "未知网页"
                    display_src = title
                    bucket = web_sources
                else:
                    display_src = self._clean_text(raw_src)
                    if not display_src:
                        display_src = "未知来源"
                    bucket = law_sources

                if display_src not in bucket:
                    bucket[display_src] = {"count": 0, "samples": []}
                bucket[display_src]["count"] += 1
                if len(bucket[display_src]["samples"]) < 4:
                    snippet = self._clean_text((doc or "").replace("\n", " "))[:120]
                    if snippet:
                        bucket[display_src]["samples"].append(snippet)

            categories = {}
            if law_sources:
                categories["法律文档"] = {
                    "total": sum(v["count"] for v in law_sources.values()),
                    "sources": law_sources,
                }
            if web_sources:
                categories["网络检索"] = {
                    "total": sum(v["count"] for v in web_sources.values()),
                    "sources": web_sources,
                }

            return {"categories": categories, "total": total}
        except Exception as e:
            logger.warning(f"get_sources_summary 失败: {e}")
            return {}

    def delete_by_source(self, source_name: str) -> int:
        """
        按来源名删除所有匹配的 chunk。

        匹配规则：
        - 法律文档：metadata['source'] == source_name（经过 _clean_text 清洗后比较）
        - 联网检索：metadata['source'] 以 '网络检索' 开头且标题部分匹配 source_name

        Returns:
            实际删除的 chunk 数量
        """
        import re
        try:
            client = self._get_client()
            col = client.get_or_create_collection(self.COLLECTION_NAME)
            result = col.get(include=["metadatas"])
            metadatas = result.get("metadatas") or []
            ids = result.get("ids") or []

            to_delete = []
            for doc_id, meta in zip(ids, metadatas):
                raw_src = (meta.get("source", "") if meta else "") or ""
                is_web = raw_src.startswith("网络检索")

                if is_web:
                    title = re.sub(r'^网络检索\s*[-–]\s*', '', raw_src)
                    display = self._clean_text(title) or "未知网页"
                else:
                    display = self._clean_text(raw_src) or "未知来源"

                if display == source_name:
                    to_delete.append(doc_id)

            if to_delete:
                col.delete(ids=to_delete)
                # 向量库缓存失效，下次 get_vectorstore() 会重新绑定
                self._vectorstore = None
                logger.info(f"按来源删除完成：source='{source_name}'，共删除 {len(to_delete)} 条")

            return len(to_delete)
        except Exception as e:
            logger.error(f"delete_by_source 失败: {e}")
            raise

    def delete_by_raw_source(self, raw_source: str) -> int:
        """
        按原始 metadata['source'] 值精确删除所有匹配 chunk（无需 display 转换）。
        比 delete_by_source 更可靠，适合审核自动删除场景。
        """
        try:
            client = self._get_client()
            col = client.get_or_create_collection(self.COLLECTION_NAME)
            result = col.get(include=["metadatas"])
            metadatas = result.get("metadatas") or []
            ids = result.get("ids") or []

            to_delete = [
                doc_id for doc_id, meta in zip(ids, metadatas)
                if (meta or {}).get("source", "") == raw_source
            ]

            if to_delete:
                col.delete(ids=to_delete)
                self._vectorstore = None
                logger.info(f"按原始source删除：raw='{raw_source}'，共删除 {len(to_delete)} 条")

            return len(to_delete)
        except Exception as e:
            logger.error(f"delete_by_raw_source 失败: {e}")
            raise

    def clear_collection(self):
        """清空向量库"""
        client = self._get_client()
        client.delete_collection(self.COLLECTION_NAME)
        self._vectorstore = None
        logger.info("向量库已清空")


# 全局单例
vector_store_manager = VectorStoreManager()
