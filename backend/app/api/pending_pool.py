"""
暂存池管理API
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.rag.pending_pool import get_pending_pool

router = APIRouter(prefix="/api/pending", tags=["暂存池管理"])
logger = logging.getLogger(__name__)


class PendingDocResponse(BaseModel):
    """暂存文档响应"""
    id: str
    query: str
    content: str
    source_url: str
    source_type: str
    crawl_time: str
    relevance_score: float
    quality_score: Optional[float] = None
    should_keep: Optional[bool] = None
    evaluation_time: Optional[str] = None


class PendingStatsResponse(BaseModel):
    """暂存池统计响应"""
    total: int
    pending: int
    keep: int
    discard: int


class ManualActionRequest(BaseModel):
    """手动操作请求"""
    action: str = Field(..., description="操作类型：keep 或 discard")
    reason: str = Field("", description="操作原因")


@router.get("/stats", response_model=PendingStatsResponse)
async def get_stats():
    """
    获取暂存池统计信息
    
    Returns:
        统计信息
    """
    try:
        pending_pool = get_pending_pool()
        stats = pending_pool.get_stats()
        return PendingStatsResponse(**stats)
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=List[PendingDocResponse])
async def list_documents(
    status: Optional[str] = None,
    limit: int = 50
):
    """
    获取暂存文档列表
    
    Args:
        status: 状态过滤（pending=待评估，keep=保留，discard=丢弃）
        limit: 最大返回数量
        
    Returns:
        文档列表
    """
    try:
        pending_pool = get_pending_pool()
        
        # 解析状态
        should_keep = None
        if status == 'pending':
            should_keep = None
        elif status == 'keep':
            should_keep = True
        elif status == 'discard':
            should_keep = False
        
        # 获取文档
        docs = pending_pool.get_by_status(should_keep=should_keep, limit=limit)
        
        # 转换为响应格式
        response_docs = []
        for doc in docs:
            response_docs.append(PendingDocResponse(
                id=doc.id,
                query=doc.query,
                content=doc.content,
                source_url=doc.source_url,
                source_type=doc.source_type,
                crawl_time=doc.crawl_time.isoformat(),
                relevance_score=doc.relevance_score,
                quality_score=doc.quality_score,
                should_keep=doc.should_keep,
                evaluation_time=doc.evaluation_time.isoformat() if doc.evaluation_time else None
            ))
        
        return response_docs
        
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}", response_model=PendingDocResponse)
async def get_document(doc_id: str):
    """
    获取文档详情
    
    Args:
        doc_id: 文档ID
        
    Returns:
        文档详情
    """
    try:
        pending_pool = get_pending_pool()
        doc = pending_pool.get_document(doc_id)
        
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        return PendingDocResponse(
            id=doc.id,
            query=doc.query,
            content=doc.content,
            source_url=doc.source_url,
            source_type=doc.source_type,
            crawl_time=doc.crawl_time.isoformat(),
            relevance_score=doc.relevance_score,
            quality_score=doc.quality_score,
            should_keep=doc.should_keep,
            evaluation_time=doc.evaluation_time.isoformat() if doc.evaluation_time else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/action")
async def manual_action(doc_id: str, request: ManualActionRequest):
    """
    手动操作文档
    
    Args:
        doc_id: 文档ID
        request: 操作请求
        
    Returns:
        操作结果
    """
    try:
        if request.action not in ['keep', 'discard']:
            raise HTTPException(status_code=400, detail="操作类型必须是 keep 或 discard")
        
        pending_pool = get_pending_pool()
        doc = pending_pool.get_document(doc_id)
        
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 执行操作
        if request.action == 'keep':
            # 手动保留：标记为保留，并实际写入向量库
            pending_pool.mark_evaluated(doc_id, 1.0, True, f"手动保留：{request.reason}")

            # 将文档写入向量库
            try:
                from langchain.schema import Document as LCDocument
                from app.core.vector_store import vector_store_manager
                from app.core.retriever import hybrid_retriever
                from app.api.ingest import _get_all_docs_from_vectorstore

                ingest_doc = LCDocument(
                    page_content=doc.content,
                    metadata={
                        "source": doc.metadata.get("source", f"网络检索 - {doc.source_url[:60]}"),
                        "url": doc.source_url,
                        "from_web": True,
                        "web_auto_ingest": True,
                        "web_source": doc.metadata.get("web_source", "pending_pool"),
                    },
                )
                vector_store_manager.add_documents([ingest_doc])

                # 重建 BM25 索引
                all_docs = _get_all_docs_from_vectorstore()
                hybrid_retriever.build_bm25_index(all_docs)

                logger.info(f"[暂存池] 文档 {doc_id} 已入库向量库并重建 BM25 索引")
            except Exception as e:
                logger.error(f"[暂存池] 文档 {doc_id} 入库失败: {e}")
                raise HTTPException(status_code=500, detail=f"标记成功但入库失败: {e}")
            
        else:
            # 手动丢弃：标记为丢弃
            pending_pool.mark_evaluated(doc_id, 0.0, False, f"手动丢弃：{request.reason}")
            logger.info(f"文档 {doc_id} 已手动丢弃")
        
        return {
            'success': True,
            'message': f"已{'保留' if request.action == 'keep' else '丢弃'}文档 {doc_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手动操作失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """
    删除文档
    
    Args:
        doc_id: 文档ID
        
    Returns:
        删除结果
    """
    try:
        pending_pool = get_pending_pool()
        success = pending_pool.delete_document(doc_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="文档不存在或删除失败")
        
        return {'success': True, 'message': f"文档 {doc_id} 已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_pool():
    """
    清空暂存池
    
    Returns:
        清空结果
    """
    try:
        pending_pool = get_pending_pool()
        count = pending_pool.clear_all()
        
        return {
            'success': True,
            'message': f"已清空 {count} 个文档"
        }
        
    except Exception as e:
        logger.error(f"清空暂存池失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class EvaluateRequest(BaseModel):
    """开始鉴别请求"""
    limit: int = Field(10, description="最多鉴别几条文档", ge=1, le=50)


@router.post("/evaluate")
async def trigger_evaluate(request: EvaluateRequest = EvaluateRequest()):
    """
    触发对暂存池中待评估文档的 AI 鉴别
    
    Returns:
        触发结果
    """
    import asyncio
    try:
        pending_pool = get_pending_pool()
        pending_docs = pending_pool.get_by_status(should_keep=None, limit=request.limit)
        
        if not pending_docs:
            return {'success': True, 'message': '没有待鉴别的文档', 'count': 0}
        
        doc_count = len(pending_docs)
        
        # 在后台异步执行评估，不阻塞响应
        from app.rag.async_evaluator import get_async_evaluator
        
        evaluator = get_async_evaluator()
        
        async def _run_evaluate():
            for doc in pending_docs:
                query = doc.query or "法律咨询"
                await evaluator.evaluate_and_process(doc.id, query, "暂无答案（手动触发评估）")
        
        # 创建后台任务
        asyncio.create_task(_run_evaluate())
        
        logger.info(f"已触发对 {doc_count} 条文档的 AI 鉴别（后台执行）")
        return {
            'success': True,
            'message': f'已触发对 {doc_count} 条文档的 AI 鉴别，请稍后刷新查看结果',
            'count': doc_count
        }
        
    except Exception as e:
        logger.error(f"触发鉴别失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
