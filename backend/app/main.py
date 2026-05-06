import logging
import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, ingest, system, model, developer, pending_pool, agent

# 增强日志配置
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="法律咨询智能问答系统",
        description="基于RAG技术的法律咨询智能问答系统，采用混合检索策略与DeepSeek-R1本地推理",
        version="1.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS 配置（允许前端跨域）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(chat.router)
    app.include_router(ingest.router)
    app.include_router(system.router)
    app.include_router(model.router)
    app.include_router(developer.router)
    app.include_router(pending_pool.router)
    app.include_router(agent.router)

    @app.on_event("startup")
    async def startup_event():
        from app.config import settings

        # 输出启动信息
        logger.info("=" * 50)
        logger.info(" 法律咨询智能问答系统 v1.1.0 启动")
        logger.info("=" * 50)
        logger.info(f" API文档: http://{settings.host}:{settings.port}/docs")
        logger.info(f" 懒加载模式: {settings.lazy_load_enabled}")

        # 模块开关状态
        logger.info(" ── 核心算法模块状态 ──")
        logger.info(f"   GLVR (图谱重排序): {'启用' if settings.enable_glvr else '禁用'}")
        logger.info(f"   QAWRF (动态权重):  {'启用' if settings.enable_qawrf else '禁用'}")
        logger.info(f"   LCCP (置信度传播): {'启用' if settings.enable_lccp else '禁用'}")

        if settings.lazy_load_enabled:
            logger.info(" ── 懒加载：首次请求时加载以下组件 ──")
            logger.info("   • BM25 索引（从向量库文档构建）")
            logger.info("   • 知识图谱 PageRank（如已构建）")
            logger.info("   • 嵌入模型（如未预加载）")
        else:
            logger.info(" ── 预加载：启动时加载所有组件 ──")

        logger.info("=" * 50)
        logger.info("系统启动完成，等待请求...")

    return app


app = create_app()
