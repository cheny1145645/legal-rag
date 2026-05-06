"""
异步评估器 - 异步评估文档并决定是否入库
"""
import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter

from .pending_pool import PendingPool, PendingDocument, get_pending_pool
from .document_evaluator import DocumentEvaluator, get_document_evaluator

logger = logging.getLogger(__name__)


class AsyncEvaluator:
    """异步评估器"""
    
    def __init__(
        self,
        pending_pool: Optional[PendingPool] = None,
        evaluator: Optional[DocumentEvaluator] = None
    ):
        """
        初始化异步评估器
        
        Args:
            pending_pool: 暂存池实例
            evaluator: 文档评估器
        """
        self.pending_pool = pending_pool or get_pending_pool()
        self.evaluator = evaluator or get_document_evaluator()
        
        # 文档分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len
        )
        
        logger.info("异步评估器初始化完成")
    
    async def evaluate_and_process(self, doc_id: str, query: str, answer: str):
        """
        评估并处理文档（异步）
        
        Args:
            doc_id: 文档ID
            query: 用户查询
            answer: AI答案
        """
        try:
            logger.info(f"开始异步评估文档 {doc_id}")
            
            # 1. 获取文档
            doc = self.pending_pool.get_document(doc_id)
            if not doc:
                logger.warning(f"文档 {doc_id} 不存在")
                return
            
            # 2. 异步评估（不阻塞用户响应）
            evaluation = await self._async_evaluate(doc, query, answer)
            
            # 3. 更新暂存池
            self.pending_pool.mark_evaluated(
                doc_id,
                evaluation['quality_score'],
                evaluation['should_keep'],
                evaluation['reason']
            )
            
            # 4. 如果应该入库，添加到向量库
            if evaluation['should_keep']:
                await self._add_to_vector_store(doc, evaluation)
                logger.info(f"✅ 文档 {doc_id} 已入库（质量评分：{evaluation['quality_score']:.2f}）")
            else:
                logger.info(f"❌ 文档 {doc_id} 已丢弃（原因：{evaluation['reason']}）")
            
        except Exception as e:
            logger.error(f"评估文档 {doc_id} 失败: {e}", exc_info=True)
            # 标记为评估失败
            try:
                self.pending_pool.mark_evaluated(
                    doc_id,
                    0.0,
                    False,
                    f"评估失败: {str(e)}"
                )
            except:
                pass
    
    async def batch_evaluate(self, doc_ids: List[str], query: str, answer: str):
        """
        批量评估文档
        
        Args:
            doc_ids: 文档ID列表
            query: 用户查询
            answer: AI答案
        """
        tasks = [
            self.evaluate_and_process(doc_id, query, answer)
            for doc_id in doc_ids
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"批量评估完成：{len(doc_ids)} 个文档")
    
    async def _async_evaluate(self, doc: PendingDocument, query: str, answer: str) -> dict:
        """
        异步评估
        
        Args:
            doc: 待评估文档
            query: 用户查询
            answer: AI答案
            
        Returns:
            评估结果
        """
        # 在线程池中执行 LLM 调用（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self.evaluator.evaluate,
            doc,
            query,
            answer
        )
        return result
    
    async def _add_to_vector_store(self, doc: PendingDocument, evaluation: dict):
        """
        添加到向量库
        
        Args:
            doc: 待添加文档
            evaluation: 评估结果
        """
        try:
            from langchain.schema import Document as LCDocument
            from app.core.vector_store import vector_store_manager
            from app.core.retriever import hybrid_retriever
            from app.api.ingest import _get_all_docs_from_vectorstore
            
            # 1. 生成文档块
            chunks = self.text_splitter.split_text(doc.content)
            
            if not chunks:
                logger.warning(f"文档 {doc.id} 生成文档块失败")
                return
            
            # 2. 准备元数据
            base_metadata = {
                'source': doc.metadata.get('source', f'网络检索 - {doc.source_url[:60]}'),
                'url': doc.source_url,
                'from_web': True,
                'web_auto_ingest': True,
                'quality_score': evaluation['quality_score'],
                'evaluation_time': datetime.now().isoformat(),
                'pending_doc_id': doc.id
            }
            
            # 3. 构建 LangChain Document 并添加到向量库
            ingest_doc = LCDocument(
                page_content=doc.content,
                metadata=base_metadata
            )
            vector_store_manager.add_documents([ingest_doc])
            
            # 4. 重建 BM25 索引
            all_docs = _get_all_docs_from_vectorstore()
            hybrid_retriever.build_bm25_index(all_docs)
            
            logger.info(f"文档 {doc.id} 已入库向量库并重建 BM25 索引")
            
        except Exception as e:
            logger.error(f"文档 {doc.id} 入库失败: {e}", exc_info=True)
            raise
    
    async def process_pending_pool(self, limit: int = 10):
        """
        处理暂存池中的待评估文档
        
        Args:
            limit: 最大处理数量
        """
        try:
            # 获取待评估文档
            pending_docs = self.pending_pool.get_by_status(should_keep=None, limit=limit)
            
            if not pending_docs:
                logger.info("暂存池中没有待评估文档")
                return
            
            logger.info(f"开始处理暂存池：{len(pending_docs)} 个待评估文档")
            
            # 批量评估
            for doc in pending_docs:
                # 使用文档中的查询信息（如果没有，使用通用查询）
                query = doc.query or "法律咨询"
                answer = "暂无答案（后台评估）"
                
                await self.evaluate_and_process(doc.id, query, answer)
            
            logger.info(f"暂存池处理完成：{len(pending_docs)} 个文档")
            
        except Exception as e:
            logger.error(f"处理暂存池失败: {e}", exc_info=True)


# 全局单例
_async_evaluator: Optional[AsyncEvaluator] = None


def get_async_evaluator() -> AsyncEvaluator:
    """
    获取异步评估器单例
    
    Returns:
        异步评估器实例
    """
    global _async_evaluator
    if _async_evaluator is None:
        _async_evaluator = AsyncEvaluator()
    return _async_evaluator
