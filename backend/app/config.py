from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama 配置
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-r1:latest"

    # 嵌入模型（本地路径，避免 HuggingFace 下载）
    embedding_model: str = "D:/legal-rag -1.0.0/models/bge-m3"

    # 路径配置
    chroma_db_path: str = "../data/vectordb"
    legal_docs_path: str = "../data/raw"

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8001

    # RAG 参数
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k_retrieval: int = 5
    
    # 本地知识库检索权重（向量 + BM25）
    # 调高可让本地法律文档更优先，网络补充内容的固定分数为 0.5（见 rag_pipeline.py）
    bm25_weight: float = 0.45
    vector_weight: float = 0.70
    
    # GLVR: 图权重系数（0.3表示30%权威度，70%向量相似度）
    glvr_gamma: float = 0.3

    # ── 查询增强配置 ──────────────────────────────────────────────────────────
    # 可选值: "hyde" | "multi_query" | "off"
    # hyde       : 生成假设性文档后做向量检索，适合口语化问题
    # multi_query: 扩写3个子查询并行检索，适合表述模糊的问题
    # off        : 不增强，直接使用原始问题检索
    query_enhance_mode: str = "hyde"

    # ── 对话记忆配置 ──────────────────────────────────────────────────────────
    # 超过该轮数时触发历史压缩
    memory_compress_threshold: int = 10
    # 压缩后保留的最近轮数
    memory_recent_turns: int = 6

    # ── 知识图谱配置 ──────────────────────────────────────────────────────────
    # 是否启用知识图谱扩展检索
    enable_knowledge_graph: bool = True
    # 图扩展最大跳数
    kg_max_hops: int = 2
    # 图扩展最多补充条文数
    kg_max_expand: int = 5

    # ── Reranker 配置 ─────────────────────────────────────────────────────────
    # Reranker 本地模型路径，留空则尝试从 HuggingFace 拉取
    reranker_model: str = "D:/legal-rag -1.0.0/models/bge-reranker-v2-m3"
    # Rerank 相关性阈值（0~1），低于此分数的 chunk 过滤掉，默认 0.15
    # 调高（如 0.3）→ 更严格，减少无关/反向内容，但可能丢失边缘相关内容
    # 调低（如 0.05）→ 更宽松，保留更多候选
    rerank_score_threshold: float = 0.15

    # ── 离线模式（由 run.py 在启动时写入 os.environ，此处仅作配置记录）────────
    transformers_offline: str = "1"
    hf_datasets_offline: str = "1"

    # ── 懒加载模式配置 ─────────────────────────────────────────────────────
    # 启动时是否预加载组件（True=预加载，False=懒加载，首次调用时加载）
    # 懒加载可大幅减少启动时间，但首次响应会略慢
    lazy_load_enabled: bool = True

    # ── 核心算法模块开关 ─────────────────────────────────────────────────────
    # 是否启用 GLVR（���谱引导的向量重排序）
    enable_glvr: bool = True

    # 是否启用 QAWRF（查询感知动态权重融合）
    enable_qawrf: bool = False

    # 是否启用 LCCP（法律推理链置信度传播）
    enable_lccp: bool = False
    # LCCP 置信度衰减因子（0~1），越大约保守
    lccp_decay_factor: float = 0.7
    # LCCP 置信度阈值，低于此值给出警告
    lccp_confidence_threshold: float = 0.5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()