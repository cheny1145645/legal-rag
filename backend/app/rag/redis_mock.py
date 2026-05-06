"""
Redis Mock - 用于暂存池的内存存储模拟
用于快速测试和演示，不需要安装 Redis 服务
"""
import json
import time
import threading
from typing import List, Dict, Optional, Any
from collections import defaultdict


class MockRedis:
    """Redis Mock 实现 - 使用内存存储"""
    
    def __init__(self):
        self.data = {}
        self.expiry = {}
        self.lock = threading.Lock()
    
    def set(self, key: str, value: str, ex: int = None):
        """设置键值，支持过期时间"""
        with self.lock:
            self.data[key] = value
            if ex:
                self.expiry[key] = time.time() + ex
        return True

    def setex(self, key: str, time: int, value: str):
        """设置键值并指定过期时间（秒）"""
        return self.set(key, value, ex=time)

    def ttl(self, key: str) -> int:
        """获取键的剩余生存时间（秒）"""
        with self.lock:
            if key not in self.data:
                return -2  # 键不存在

            if key in self.expiry:
                remaining = int(self.expiry[key] - time.time())
                return remaining if remaining > 0 else -2  # 已过期视为不存在

            return -1  # 键存在但没有设置过期时间
    
    def get(self, key: str) -> Optional[str]:
        """获取键值"""
        with self.lock:
            if key in self.data:
                # 检查是否过期
                if key in self.expiry and time.time() > self.expiry[key]:
                    del self.data[key]
                    del self.expiry[key]
                    return None
                return self.data[key]
        return None
    
    def expire(self, key: str, seconds: int) -> int:
        """设置键的过期时间（秒）"""
        with self.lock:
            if key not in self.data:
                return 0
            self.expiry[key] = time.time() + seconds
            return 1

    def delete(self, *keys) -> int:
        """删除一个或多个键"""
        count = 0
        with self.lock:
            for key in keys:
                if key in self.data:
                    del self.data[key]
                    if key in self.expiry:
                        del self.expiry[key]
                    count += 1
        return count
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.get(key) is not None
    
    def keys(self, pattern: str) -> List[str]:
        """获取匹配模式的所有键"""
        with self.lock:
            # 清理过期键
            current_time = time.time()
            for key in list(self.expiry.keys()):
                if current_time > self.expiry[key]:
                    if key in self.data:
                        del self.data[key]
                    del self.expiry[key]
            
            # 简单的通配符匹配
            import fnmatch
            all_keys = list(self.data.keys())
            return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]
    
    def hset(self, name: str, key: str, value: str) -> int:
        """哈希表设置字段"""
        hash_key = f"hash:{name}"
        with self.lock:
            if hash_key not in self.data:
                self.data[hash_key] = {}
            elif isinstance(self.data[hash_key], str):
                self.data[hash_key] = json.loads(self.data[hash_key])
            
            self.data[hash_key][key] = value
            self.data[hash_key] = json.dumps(self.data[hash_key])
        return 1
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """哈希表获取字段"""
        hash_key = f"hash:{name}"
        value = self.get(hash_key)
        if value:
            try:
                hash_data = json.loads(value)
                return hash_data.get(key)
            except:
                pass
        return None
    
    def hgetall(self, name: str) -> Dict[str, str]:
        """哈希表获取所有字段"""
        hash_key = f"hash:{name}"
        value = self.get(hash_key)
        if value:
            try:
                return json.loads(value)
            except:
                pass
        return {}
    
    def hdel(self, name: str, *keys) -> int:
        """哈希表删除字段"""
        hash_key = f"hash:{name}"
        with self.lock:
            if hash_key in self.data:
                hash_data = json.loads(self.data[hash_key])
                count = 0
                for key in keys:
                    if key in hash_data:
                        del hash_data[key]
                        count += 1
                self.data[hash_key] = json.dumps(hash_data)
                return count
        return 0
    
    def hkeys(self, name: str) -> List[str]:
        """哈希表获取所有字段名"""
        return list(self.hgetall(name).keys())
    
    def hlen(self, name: str) -> int:
        """哈希表获取字段数量"""
        return len(self.hgetall(name))
    
    def zadd(self, name: str, mapping: Dict[str, float]) -> int:
        """有序集合添加成员"""
        sorted_key = f"zset:{name}"
        with self.lock:
            if sorted_key not in self.data:
                self.data[sorted_key] = {}
            elif isinstance(self.data[sorted_key], str):
                self.data[sorted_key] = json.loads(self.data[sorted_key])
            
            self.data[sorted_key].update(mapping)
            self.data[sorted_key] = json.dumps(self.data[sorted_key])
        return len(mapping)
    
    def zrange(self, name: str, start: int, end: int) -> List[str]:
        """有序集合获取范围内的成员"""
        sorted_key = f"zset:{name}"
        value = self.get(sorted_key)
        if value:
            try:
                sorted_data = json.loads(value)
                items = sorted(sorted_data.items(), key=lambda x: x[1])
                keys = [k for k, v in items[start:end+1 if end >= 0 else end]]
                return keys
            except:
                pass
        return []
    
    def zremrangebyrank(self, name: str, start: int, end: int) -> int:
        """有序集合删除排名范围内的成员"""
        sorted_key = f"zset:{name}"
        with self.lock:
            if sorted_key in self.data:
                sorted_data = json.loads(self.data[sorted_key])
                items = sorted(sorted_data.items(), key=lambda x: x[1])
                to_remove = [k for k, v in items[start:end+1 if end >= 0 else end]]
                count = len(to_remove)
                for key in to_remove:
                    del sorted_data[key]
                self.data[sorted_key] = json.dumps(sorted_data)
                return count
        return 0


# 全局 Mock Redis 实例
_mock_redis_instance = None
# 只打印一次 Mock 模式提示（避免每次 get_redis_client() 调用都打日志）
_mock_warned = False


def get_mock_redis() -> MockRedis:
    """获取全局 Mock Redis 实例"""
    global _mock_redis_instance
    if _mock_redis_instance is None:
        _mock_redis_instance = MockRedis()
    return _mock_redis_instance


def is_mock_enabled() -> bool:
    """检查是否启用 Mock 模式"""
    import os
    return os.getenv("REDIS_MOCK_ENABLED", "true").lower() == "true"


def get_redis_client():
    """获取 Redis 客户端（Mock 或真实）"""
    global _mock_warned
    if is_mock_enabled():
        if not _mock_warned:
            import logging
            # INFO 级别：Mock 模式是本地开发的正常状态，不是错误
            logging.getLogger(__name__).info(
                "Redis 使用 Mock 模式（内存存储），如需持久化请安装 Redis 并设置 REDIS_MOCK_ENABLED=false"
            )
            _mock_warned = True
        return get_mock_redis()
    else:
        try:
            import redis
            return redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=True
            )
        except Exception as e:
            import logging
            logging.error(f"Redis 连接失败: {e}")
            logging.warning("降级到 Mock Redis 模式")
            return get_mock_redis()
