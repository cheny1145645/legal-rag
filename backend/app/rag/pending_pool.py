"""
暂存池模块 - 用于暂存网络爬取的文档，等待评估后决定是否入库
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid

# 尝试导入 Redis，如果失败则使用 Mock
try:
    import redis
except ImportError:
    redis = None

from .redis_mock import get_redis_client

logger = logging.getLogger(__name__)


class PendingDocument(BaseModel):
    """暂存文档模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str  # 用户查询
    content: str  # 文档内容
    source_url: str  # 来源URL
    source_type: str = 'web'  # 'web' | 'api'
    crawl_time: datetime = Field(default_factory=datetime.now)
    relevance_score: float = 0.0  # 检索相关度评分
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # 评估字段
    quality_score: Optional[float] = None  # 质量评分（模型评估）
    should_keep: Optional[bool] = None  # 是否应该入库
    evaluation_time: Optional[datetime] = None  # 评估时间
    user_feedback: Optional[Dict[str, Any]] = None  # 用户反馈
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PendingPool:
    """暂存池 - 使用 Redis 或 Mock 存储"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1", ttl: int = 3600):
        """
        初始化暂存池
        
        Args:
            redis_url: Redis 连接URL
            ttl: 文档默认过期时间（秒）
        """
        # 使用统一的 Redis 客户端获取函数
        self.redis = get_redis_client()
        self.key_prefix = "pending_doc:"
        self.ttl = ttl
        self.default_ttl = ttl
        logger.info(f"暂存池初始化完成，Redis: {redis_url}, TTL: {ttl}秒")
    
    def add_document(self, doc: PendingDocument, ttl: Optional[int] = None) -> bool:
        """
        添加文档到暂存池
        
        Args:
            doc: 待暂存文档
            ttl: 过期时间（秒），默认使用初始化时的值
            
        Returns:
            是否添加成功
        """
        try:
            key = f"{self.key_prefix}{doc.id}"
            data = doc.model_dump_json()
            self.redis.setex(key, ttl or self.default_ttl, data)
            logger.debug(f"文档 {doc.id} 已添加到暂存池")
            return True
        except Exception as e:
            logger.error(f"添加文档到暂存池失败: {e}")
            return False
    
    def get_document(self, doc_id: str) -> Optional[PendingDocument]:
        """
        获取文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档对象，如果不存在返回 None
        """
        try:
            key = f"{self.key_prefix}{doc_id}"
            data = self.redis.get(key)
            if data:
                return PendingDocument.model_validate_json(data)
            return None
        except Exception as e:
            logger.error(f"获取文档 {doc_id} 失败: {e}")
            return None
    
    def update_document(self, doc_id: str, **kwargs) -> bool:
        """
        更新文档
        
        Args:
            doc_id: 文档ID
            **kwargs: 要更新的字段
            
        Returns:
            是否更新成功
        """
        try:
            doc = self.get_document(doc_id)
            if not doc:
                logger.warning(f"文档 {doc_id} 不存在，无法更新")
                return False
            
            # 更新字段
            for key, value in kwargs.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)
            
            # 重新保存
            return self.add_document(doc, ttl=self.redis.ttl(f"{self.key_prefix}{doc_id}"))
        except Exception as e:
            logger.error(f"更新文档 {doc_id} 失败: {e}")
            return False
    
    def mark_evaluated(self, doc_id: str, quality_score: float, should_keep: bool, reason: str = "") -> bool:
        """
        标记为已评估
        
        Args:
            doc_id: 文档ID
            quality_score: 质量评分
            should_keep: 是否应该入库
            reason: 决策原因
            
        Returns:
            是否标记成功
        """
        return self.update_document(
            doc_id,
            quality_score=quality_score,
            should_keep=should_keep,
            evaluation_time=datetime.now(),
            metadata={"evaluation_reason": reason}
        )
    
    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否删除成功
        """
        try:
            key = f"{self.key_prefix}{doc_id}"
            self.redis.delete(key)
            logger.debug(f"文档 {doc_id} 已从暂存池删除")
            return True
        except Exception as e:
            logger.error(f"删除文档 {doc_id} 失败: {e}")
            return False
    
    def get_all_pending(self, limit: int = 100) -> List[PendingDocument]:
        """
        获取所有待处理文档
        
        Args:
            limit: 最大返回数量
            
        Returns:
            文档列表
        """
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis.keys(pattern)
            docs = []
            
            for key in keys[:limit]:
                data = self.redis.get(key)
                if data:
                    try:
                        doc = PendingDocument.model_validate_json(data)
                        docs.append(doc)
                    except Exception as e:
                        logger.warning(f"解析文档 {key} 失败: {e}")
            
            return docs
        except Exception as e:
            logger.error(f"获取待处理文档失败: {e}")
            return []
    
    def get_by_status(self, should_keep: Optional[bool] = None, limit: int = 100) -> List[PendingDocument]:
        """
        按状态获取文档
        
        Args:
            should_keep: 评估结果（None=待评估，True=保留，False=丢弃）
            limit: 最大返回数量
            
        Returns:
            文档列表
        """
        all_docs = self.get_all_pending(limit)
        
        if should_keep is None:
            return [doc for doc in all_docs if doc.should_keep is None]
        elif should_keep:
            return [doc for doc in all_docs if doc.should_keep is True]
        else:
            return [doc for doc in all_docs if doc.should_keep is False]
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis.keys(pattern)
            
            stats = {
                'total': len(keys),
                'pending': 0,  # 待评估
                'keep': 0,  # 应该保留
                'discard': 0  # 应该丢弃
            }
            
            for key in keys:
                data = self.redis.get(key)
                if data:
                    try:
                        doc = PendingDocument.model_validate_json(data)
                        if doc.should_keep is None:
                            stats['pending'] += 1
                        elif doc.should_keep:
                            stats['keep'] += 1
                        else:
                            stats['discard'] += 1
                    except Exception:
                        pass
            
            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {'total': 0, 'pending': 0, 'keep': 0, 'discard': 0}
    
    def clear_expired(self) -> int:
        """
        清理过期文档
        
        Returns:
            清理的文档数量
        """
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis.keys(pattern)
            
            cleared = 0
            for key in keys:
                ttl = self.redis.ttl(key)
                if ttl == -1:  # 没有过期时间
                    self.redis.expire(key, self.default_ttl)
                    cleared += 1
            
            logger.info(f"清理了 {cleared} 个文档")
            return cleared
        except Exception as e:
            logger.error(f"清理过期文档失败: {e}")
            return 0
    
    def clear_all(self) -> int:
        """
        清空所有文档
        
        Returns:
            清理的文档数量
        """
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis.keys(pattern)
            
            if keys:
                self.redis.delete(*keys)
                logger.info(f"清空了 {len(keys)} 个文档")
                return len(keys)
            
            return 0
        except Exception as e:
            logger.error(f"清空文档失败: {e}")
            return 0


# 全局单例
_pending_pool: Optional[PendingPool] = None


def get_pending_pool() -> PendingPool:
    """
    获取暂存池单例
    
    Returns:
        暂存池实例
    """
    global _pending_pool
    if _pending_pool is None:
        from app.config import settings
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/1')
        ttl = getattr(settings, 'PENDING_POOL_TTL', 3600)
        _pending_pool = PendingPool(redis_url=redis_url, ttl=ttl)
    return _pending_pool
