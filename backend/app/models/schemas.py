from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class QueryHistoryItem(BaseModel):
    """查询历史记录项"""
    query: str
    time: str
    latency: int  # 毫秒
    hitRate: float  # 0-1
    source: str  # "KB" | "WEB"


class QuestionRequest(BaseModel):
    """用户提问请求"""
    question: str
    session_id: Optional[str] = None
    top_k: Optional[int] = None
    # 前端运行时配置（优先级高于 .env 全局配置）
    enhance_mode: Optional[str] = None          # "hyde" | "multi_query" | "off" | None(跟随全局)
    enable_kg: Optional[bool] = None            # True | False | None(跟随全局)
    enable_rerank: Optional[bool] = None        # True | False | None(默认开启，不可用时降级)
    enable_web_search: Optional[bool] = None    # True=强制联网, False=强制关闭, None=自动判断
    # LLM 运行时覆盖（不填则用全局 llm_client 配置）
    llm_provider: Optional[str] = None          # "ollama" | "remote"
    llm_ollama_model: Optional[str] = None       # 指定 Ollama 模型名
    llm_remote_base_url: Optional[str] = None
    llm_remote_api_key: Optional[str] = None
    llm_remote_model: Optional[str] = None


class SourceDocument(BaseModel):
    """引用的源文档"""
    content: str
    source: str
    page: Optional[int] = None
    score: float
    from_kg: bool = False    # 是否来自知识图谱扩展
    from_web: bool = False   # 是否来自联网检索
    url: Optional[str] = None  # 联网来源 URL


class AnswerResponse(BaseModel):
    """问答响应"""
    answer: str
    sources: List[SourceDocument]
    session_id: str
    thinking: Optional[str] = None
    enhance_mode: Optional[str] = None              # 本次使用的查询增强模式
    memory_info: Optional[Dict[str, Any]] = None    # 会话记忆状态信息
    web_search_triggered: bool = False               # 本次是否触发了联网检索
    web_docs_count: int = 0                          # 联网检索补充的文档数
    web_results: Optional[List[Dict[str, Any]]] = None  # 网络搜索结果（用于暂存池）
    lccp_result: Optional[Dict[str, Any]] = None        # LCCP 推理链置信度评估结果


class IngestRequest(BaseModel):
    """文档入库请求"""
    file_path: Optional[str] = None
    collection_name: str = "legal_docs"


class IngestResponse(BaseModel):
    """文档入库响应"""
    success: bool
    message: str
    doc_count: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    ollama: bool
    vectordb: bool
    doc_count: int
    kg_stats: Optional[Dict] = None   # 知识图谱统计信息




# ── Agent 请求 ──────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    """Agent 对话请求"""
    prompt: str
    session_id: Optional[str] = None
    max_iterations: Optional[int] = 10  # 最大迭代次数
    # LLM 运行时覆盖
    llm_provider: Optional[str] = None
    llm_ollama_model: Optional[str] = None
    llm_remote_base_url: Optional[str] = None
    llm_remote_api_key: Optional[str] = None
    llm_remote_model: Optional[str] = None


class AgentResponse(BaseModel):
    """Agent 对话响应"""
    success: bool
    message: str


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    parameters: dict


class ToolsListResponse(BaseModel):
    """工具列表响应"""
    tools: List[ToolInfo]


class UploadAnalyzeRequest(BaseModel):
    """上传并分析请求"""
    question: Optional[str] = ""
    session_id: Optional[str] = None


# ── 知识库批量审核 ──────────────────────────────────────────────────────────

class AuditRequest(BaseModel):
    """批量审核请求"""
    # web_only=True 只审核联网自动入库的内容，False 审核全部
    web_only: bool = True
    # 每个来源最多取几条样本送 LLM 判断（越多越准，越慢）
    sample_size: int = 3
    # 审核完后是否自动删除不合格内容（False=只返回报告，True=同步删除）
    auto_delete: bool = False


class AuditSourceResult(BaseModel):
    """单个来源的审核结果"""
    source_name: str
    chunk_count: int           # 该来源的 chunk 总数
    verdict: str               # "pass" | "fail" | "uncertain"
    reason: str                # 判断理由（一句话）
    samples: List[str]         # 送审的样本片段
    raw_sources: List[str] = []  # 原始 metadata['source'] 值，用于精确删除


class AuditResponse(BaseModel):
    """批量审核响应"""
    total_sources: int
    audited: int               # 实际审核数（跳过空来源等）
    passed: int
    failed: int
    uncertain: int
    results: List[AuditSourceResult]
    deleted_sources: List[str] = []   # auto_delete=True 时已删除的来源名
    message: str
