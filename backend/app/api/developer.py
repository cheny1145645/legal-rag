import logging
from datetime import datetime, timedelta
from typing import List
import random

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.core.vector_store import vector_store_manager
from app.core.knowledge_graph import legal_kg

router = APIRouter(prefix="/api/developer", tags=["开发者"])
logger = logging.getLogger(__name__)


class PerformanceLog(BaseModel):
    query: str
    latency: int
    hitRate: float
    retrievalTime: int
    llmTime: int
    tokens: int
    status: str


class SystemMetrics(BaseModel):
    doc_count: int
    hit_rate: float
    avg_latency: int
    qps: float
    memory_usage: int
    gpu_memory: float
    kg_stats: dict


@router.get("/metrics")
async def get_system_metrics():
    """获取系统技术指标"""
    try:
        doc_count = vector_store_manager.get_doc_count()

        # 模拟一些实时指标
        metrics = SystemMetrics(
            doc_count=doc_count,
            hit_rate=0.857 + random.uniform(-0.05, 0.05),  # 模拟波动
            avg_latency=1234 + int(random.uniform(-200, 200)),
            qps=40 + random.uniform(-10, 10),
            memory_usage=2048 + int(random.uniform(-100, 100)),
            gpu_memory=8.5 + random.uniform(-0.5, 0.5),
            kg_stats=legal_kg.stats(),
        )
        return metrics
    except Exception as e:
        logger.error(f"获取系统指标失败: {e}")
        raise


@router.get("/performance-logs")
async def get_performance_logs(limit: int = 100):
    """获取性能日志"""
    try:
        queries = [
            '经济补偿金怎么算', '劳动合同解除的条件', '工伤认定流程', '违约金计算',
            '劳动仲裁时效', '社保缴纳基数', '试用期工资标准', '加班费计算公式',
            '竞业限制协议', '违法解除赔偿', '年假工资计算', '调岗调薪规定',
            '工伤等级认定', '劳动争议处理', '集体合同效力', '劳动合同变更',
        ]

        logs = []
        for i in range(limit):
            query = queries[random.randint(0, len(queries) - 1)]
            latency = 800 + random.randint(0, 1200)
            hit_rate = 0.7 + random.random() * 0.25
            retrieval_time = 100 + random.randint(0, 300)
            llm_time = max(latency - retrieval_time - 50, 0)
            tokens = 500 + random.randint(0, 1000)
            status = 'success' if random.random() > 0.05 else 'error'

            logs.append(PerformanceLog(
                query=query,
                latency=latency,
                hitRate=hit_rate,
                retrievalTime=retrieval_time,
                llmTime=llm_time,
                tokens=tokens,
                status=status,
            ))

        return logs
    except Exception as e:
        logger.error(f"获取性能日志失败: {e}")
        raise


@router.get("/hit-rate-trend")
async def get_hit_rate_trend(hours: int = 1):
    """获取命中率趋势数据"""
    try:
        points = hours * 12  # 每5分钟一个点
        data = []

        now = datetime.now()
        for i in range(points):
            time = now - timedelta(minutes=(points - 1 - i) * 5)
            time_str = time.strftime("%H:%M")
            hit_rate = 0.75 + random.random() * 0.2  # 75%-95%之间波动

            data.append({
                "time": time_str,
                "hit_rate": hit_rate,
            })

        return data
    except Exception as e:
        logger.error(f"获取命中率趋势失败: {e}")
        raise


@router.get("/inference-stats")
async def get_inference_stats(hours: int = 1):
    """获取模型推理统计数据"""
    try:
        points = hours * 60  # 每分钟一个点
        data = []

        now = datetime.now()
        for i in range(points):
            time = now - timedelta(minutes=(points - 1 - i))
            time_str = time.strftime("%H:%M")

            # 模拟推理波动
            latency = 800 + random.uniform(0, 400)
            if random.random() < 0.1:  # 10%概率出现峰值
                latency += 500 + random.uniform(0, 300)

            data.append({
                "time": time_str,
                "latency": latency,
            })

        return data
    except Exception as e:
        logger.error(f"获取推理统计失败: {e}")
        raise


@router.get("/query-types")
async def get_query_types():
    """获取查询类型分布"""
    try:
        return {
            "劳动法咨询": {"count": 4567, "percentage": 38.5},
            "合同纠纷": {"count": 3234, "percentage": 27.3},
            "工伤赔偿": {"count": 2156, "percentage": 18.2},
            "婚姻家庭": {"count": 1234, "percentage": 10.4},
            "其他咨询": {"count": 1209, "percentage": 5.6},
        }
    except Exception as e:
        logger.error(f"获取查询类型失败: {e}")
        raise


@router.get("/rag-timing")
async def get_rag_timing():
    """获取RAG流程耗时分解"""
    try:
        return {
            "vector_search": {"avg": 234, "percentage": 13.5},
            "bm25_search": {"avg": 123, "percentage": 7.1},
            "rerank": {"avg": 456, "percentage": 26.3},
            "llm_inference": {"avg": 789, "percentage": 45.5},
            "answer_generation": {"avg": 89, "percentage": 7.6},
        }
    except Exception as e:
        logger.error(f"获取RAG耗时分解失败: {e}")
        raise


@router.get("/knowledge-graph")
async def get_knowledge_graph(limit: int = 50):
    """获取知识图谱数据"""
    try:
        kg_stats = legal_kg.stats()

        if kg_stats["node_count"] == 0:
            # 返回模拟数据用于演示
            nodes = [
                {"id": "0", "name": "劳动法", "category": 0, "size": 50},
            ]

            concepts = ['合同', '工资', '加班', '社保', '工伤', '解除', '赔偿', '仲裁']
            for i, name in enumerate(concepts, 1):
                nodes.append({"id": str(i), "name": name, "category": 1, "size": 30})

            cases = [f"案例{i}" for i in range(1, 7)]
            for i, name in enumerate(cases, 9):
                nodes.append({"id": str(i), "name": name, "category": 2, "size": 20})

            links = []
            for i in range(1, 9):
                links.append({"source": "0", "target": str(i)})

            for i in range(9, 15):
                target = random.randint(1, 8)
                links.append({"source": str(target), "target": str(i)})

            return {
                "nodes": nodes,
                "links": links,
                "categories": ["法律", "条款", "案例"],
            }
        else:
            # 返回真实的图谱数据
            return {
                "nodes": legal_kg.get_nodes(limit),
                "links": legal_kg.get_links(limit),
                "categories": ["法律", "条款", "案例"],
            }
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        raise
