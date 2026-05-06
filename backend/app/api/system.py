import logging
import random
from datetime import datetime, timedelta
from typing import List

import requests
from fastapi import APIRouter

from app.config import settings
from app.core.vector_store import vector_store_manager
from app.core.knowledge_graph import legal_kg
from app.core.memory_manager import memory_manager
from app.core.reranker import reranker
from app.models.schemas import HealthResponse, QueryHistoryItem

router = APIRouter(prefix="/api", tags=["系统"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """系统健康检查"""
    # 检查 Ollama
    ollama_ok = False
    try:
        resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        ollama_ok = resp.status_code == 200
    except Exception:
        pass

    # 检查向量库
    vectordb_ok = False
    doc_count = 0
    try:
        doc_count = vector_store_manager.get_doc_count()
        vectordb_ok = True
    except Exception:
        pass

    status = "healthy" if (ollama_ok and vectordb_ok) else "degraded"
    return HealthResponse(
        status=status,
        ollama=ollama_ok,
        vectordb=vectordb_ok,
        doc_count=doc_count,
        kg_stats=legal_kg.stats(),
    )


@router.get("/stats/sources")
async def get_sources_summary():
    """获取知识库条文按来源分类统计"""
    return vector_store_manager.get_sources_summary()


@router.get("/stats")
async def get_stats():
    """获取系统统计信息"""
    doc_count = vector_store_manager.get_doc_count()
    return {
        "doc_count": doc_count,
        "model": settings.ollama_model,
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "top_k": settings.top_k_retrieval,
        "query_enhance_mode": settings.query_enhance_mode,
        "knowledge_graph": legal_kg.stats(),
        "active_sessions": memory_manager.session_count(),
    }


@router.get("/analytics")
async def get_analytics():
    """获取数据分析统计（用于可视化面板）"""
    doc_count = vector_store_manager.get_doc_count()

    # 核心指标
    stats = {
        "doc_count": doc_count,
        "total_queries": 12453,  # 模拟数据
        "hit_rate": 0.857,  # 模拟数据
        "avg_response_time": 1234,  # 毫秒
    }

    # 查询趋势数据（7天）
    query_trend = {
        "week": {
            "dates": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
            "queries": [1234, 1567, 1892, 2134, 1890, 1456, 1780],
            "hits": [0.82, 0.85, 0.88, 0.86, 0.84, 0.87, 0.89],
        },
        "month": {
            "dates": [f"{i+1}日" for i in range(30)],
            "queries": [random.randint(1000, 2500) for _ in range(30)],
            "hits": [random.uniform(0.75, 0.95) for _ in range(30)],
        },
    }

    # 知识库分布
    knowledge_distribution = [
        {"name": "劳动法", "value": 3542},
        {"name": "合同法", "value": 2341},
        {"name": "婚姻法", "value": 1876},
        {"name": "刑法", "value": 1234},
        {"name": "其他", "value": 405},
    ]

    # 检索性能对比
    performance_comparison = {
        "categories": ["向量检索", "BM25检索", "混合检索", "Rerank", "图谱扩展"],
        "values": [234, 123, 312, 456, 189],  # 毫秒
    }

    # 质量评估雷达图数据
    quality_metrics = {
        "current": [92, 85, 88, 78, 90, 95],  # [检索精度, 响应速度, 答案质量, 知识覆盖, 用户满意度, 系统稳定性]
        "baseline": [75, 70, 72, 65, 68, 70],
    }

    # 查询历史记录（模拟数据）
    query_history = [
        QueryHistoryItem(
            query="经济补偿金怎么算",
            time=(datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M"),
            latency=1234,
            hitRate=0.92,
            source="KB",
        ),
        QueryHistoryItem(
            query="劳动合同解除的条件",
            time=(datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M"),
            latency=987,
            hitRate=0.88,
            source="KB",
        ),
        QueryHistoryItem(
            query="工伤认定流程",
            time=(datetime.now() - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M"),
            latency=1567,
            hitRate=0.76,
            source="WEB",
        ),
        QueryHistoryItem(
            query="违约金怎么计算",
            time=(datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"),
            latency=1102,
            hitRate=0.84,
            source="KB",
        ),
        QueryHistoryItem(
            query="劳动仲裁时效",
            time=(datetime.now() - timedelta(hours=1, minutes=15)).strftime("%Y-%m-%d %H:%M"),
            latency=892,
            hitRate=0.91,
            source="KB",
        ),
        QueryHistoryItem(
            query="社保缴纳基数",
            time=(datetime.now() - timedelta(hours=1, minutes=30)).strftime("%Y-%m-%d %H:%M"),
            latency=1345,
            hitRate=0.79,
            source="KB",
        ),
        QueryHistoryItem(
            query="试用期工资标准",
            time=(datetime.now() - timedelta(hours=1, minutes=45)).strftime("%Y-%m-%d %H:%M"),
            latency=1023,
            hitRate=0.86,
            source="KB",
        ),
        QueryHistoryItem(
            query="加班费计算公式",
            time=(datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
            latency=1187,
            hitRate=0.82,
            source="WEB",
        ),
        QueryHistoryItem(
            query="竞业限制协议",
            time=(datetime.now() - timedelta(hours=2, minutes=15)).strftime("%Y-%m-%d %H:%M"),
            latency=1456,
            hitRate=0.74,
            source="WEB",
        ),
        QueryHistoryItem(
            query="违法解除赔偿",
            time=(datetime.now() - timedelta(hours=2, minutes=30)).strftime("%Y-%m-%d %H:%M"),
            latency=1089,
            hitRate=0.89,
            source="KB",
        ),
    ]

    return {
        "stats": stats,
        "query_trend": query_trend,
        "knowledge_distribution": knowledge_distribution,
        "performance_comparison": performance_comparison,
        "quality_metrics": quality_metrics,
        "query_history": query_history,
    }


# ── Reranker 管理 ──────────────────────────────────────────────────────────────

@router.get("/reranker-status")
async def get_reranker_status():
    """获取 Reranker 当前状态（是否可用、是否已加载、可用内存等）"""
    import os
    mem_info = {}
    try:
        import psutil
        avail_gb = psutil.virtual_memory().available / (1024 ** 3)
        total_gb = psutil.virtual_memory().total / (1024 ** 3)
        mem_info = {
            "available_gb": round(avail_gb, 1),
            "total_gb": round(total_gb, 1),
            "enough": avail_gb >= 3.0,
        }
    except ImportError:
        mem_info = {"available_gb": None, "total_gb": None, "enough": None}

    model_path = settings.reranker_model or ""
    return {
        "available": reranker.available,
        "model_path": model_path,
        "model_exists": os.path.exists(model_path) if model_path else False,
        "memory": mem_info,
    }


@router.post("/reranker-toggle")
async def toggle_reranker(enable: bool):
    """
    动态开关 Reranker。

    enable=True: 尝试加载模型（需要 >=3GB 可用内存）
    enable=False: 卸载模型，释放内存
    """
    if enable:
        # 尝试加载
        if not settings.reranker_model:
            return {
                "success": False,
                "message": "未配置 Reranker 模型路径，请在 .env 中设置 RERANKER_MODEL",
            }
        loaded = reranker._load_model()
        if loaded:
            return {"success": True, "message": "Reranker 已启用", "available": True}
        else:
            return {"success": False, "message": "Reranker 加载失败（内存不足或模型文件不存在）", "available": False}
    else:
        # 卸载模型释放内存
        if reranker._model is not None:
            del reranker._model
            reranker._model = None
        reranker._available = False
        return {"success": True, "message": "Reranker 已关闭", "available": False}


# ── 核心算法模块配置管理 ─────────────────────────────────────────────

@router.get("/modules/status")
async def get_modules_status():
    """
    获取所有核心算法模块的当前状态。
    """
    from app.core.retriever import hybrid_retriever
    
    return {
        "lazy_load_enabled": settings.lazy_load_enabled,
        "enable_glvr": settings.enable_glvr,
        "enable_qawrf": settings.enable_qawrf,
        "enable_lccp": settings.enable_lccp,
        "lccp_decay_factor": settings.lccp_decay_factor,
        "lccp_confidence_threshold": settings.lccp_confidence_threshold,
        "glvr_gamma": settings.glvr_gamma,
        "bm25_weight": settings.bm25_weight,
        "vector_weight": settings.vector_weight,
        "retriever": {
            "bm25_initialized": hybrid_retriever._bm25 is not None,
            "bm25_doc_count": len(hybrid_retriever._bm25_docs) if hybrid_retriever._bm25_docs else 0,
        },
        "knowledge_graph": legal_kg.stats(),
    }


@router.post("/modules/toggle")
async def toggle_module(
    module: str,
    enable: bool,
    params: dict = None,
):
    """
    动态开关核心算法模块。
    module: glvr | qawrf | lccp | lazy_load
    """
    module = module.lower()
    
    if module == "glvr":
        settings.enable_glvr = enable
        logger.info(f"[API] GLVR 模块已{'启用' if enable else '禁用'}")
        return {"success": True, "module": "glvr", "enabled": enable}
    
    elif module == "qawrf":
        settings.enable_qawrf = enable
        logger.info(f"[API] QAWRF 模块已{'启用' if enable else '禁用'}")
        return {"success": True, "module": "qawrf", "enabled": enable}
    
    elif module == "lccp":
        settings.enable_lccp = enable
        if params:
            if "decay_factor" in params:
                settings.lccp_decay_factor = float(params["decay_factor"])
            if "confidence_threshold" in params:
                settings.lccp_confidence_threshold = float(params["confidence_threshold"])
        logger.info(f"[API] LCCP 模块已{'启用' if enable else '禁用'}")
        return {
            "success": True,
            "module": "lccp",
            "enabled": enable,
            "decay_factor": settings.lccp_decay_factor,
        }
    
    elif module == "lazy_load":
        settings.lazy_load_enabled = enable
        if not enable:
            logger.info("[API] 切换为预加载模式...")
            try:
                vector_store_manager.initialize_embeddings()
            except Exception as e:
                logger.warning(f"[API] 预加载失败: {e}")
        return {"success": True, "module": "lazy_load", "enabled": settings.lazy_load_enabled}
    
    else:
        return {"success": False, "message": f"未知模块: {module}"}


@router.get("/modules/log-level")
async def get_log_level():
    """获取当前日志级别"""
    return {"log_level": logging.getLevelName(logger.level)}


@router.post("/modules/log-level")
async def set_log_level(level: str):
    """动态设置日志级别"""
    level = level.upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
    
    if level not in valid_levels:
        return {"success": False, "message": f"无效级别: {level}"}
    
    logging.getLogger().setLevel(getattr(logging, level))
    logger.setLevel(getattr(logging, level))
    
    return {"success": True, "log_level": level}
