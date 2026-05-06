# 法律咨询智能问答系统

基于 RAG（检索增强生成）与 Agent 智能体技术的法律咨询系统，支持本地部署，实现专业、准确、隐私安全的法律问答服务。

---

## 系统特色

- **混合检索**：BM25 关键词 + BGE-M3 向量语义 + GLVR 图谱重排 + QAWRF 动态权重，融合提升法律术语召回率
- **法律文本专项处理**：章/节/条/款层级结构智能切割，保留条文完整性
- **置信度传播 LCCP**：Label Consistency Confidence Propagation，多轮检索结果一致性校验
- **知识图谱**：法律实体（主体/行为/关系）抽取与图谱构建，扩展检索召回
- **查询增强**：支持 HyDE 假设文档检索、Multi-Query 多视角查询
- **Reranker 重排**：BGE-Reranker-v2-m3 本地离线重排序，精排 Top-K 结果
- **Agent 智能体**：Plan-Execute 循环，7 个工具自主规划，支持联网检索生成
- **思维链可视化**：展示 LLM 推理过程，增强答案可信度
- **人机协作**：暂存池 + 异步评估，支持专家审核与批量处理
- **本地推理**：全程本地运行，数据不出本机，保护隐私

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 Vue 3 + Element Plus                  │
│         ChatView · AgentView · KnowledgeView · AnalyticsView      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP REST / SSE 流式
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    后端 FastAPI (端口 8001)                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │ RAG 管线  │  │ Agent 智能体│ │ 知识图谱  │  │  暂存池系统     │ │
│  │ retriever│  │ 7工具+规划  │  │ Neo4j    │  │ pending_pool   │ │
│  │ reranker │  │ web_search │  │ 实体抽取  │  │ async_evaluator│ │
│  │ rag_pipe │  │ llm_client │  │ 图查询扩展│  │ doc_evaluator  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────────┘ │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │ 对话记忆  │  │ 查询增强  │  │ 文档处理  │  │  LCCP 置信度    │ │
│  │ memory   │  │ HyDE/MQ  │  │ 法律切割  │  │  传播校验       │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    ┌──────────┐     ┌─────────────┐   ┌─────────────┐
    │ ChromaDB │     │ BGE-M3 嵌入  │   │ Ollama LLM │
    │  向量库   │     │ (本地离线)    │   │ qwen2.5    │
    │ BM25 索引 │     │ BGE-Reranker│   │ deepseek   │
    └──────────┘     └─────────────┘   └─────────────┘
```

---

## 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+（仅开发前端时需要，前端已内置构建产物） |
| GPU | NVIDIA，建议 ≥ 8GB 显存 |
| Ollama | 已安装并拉取模型（如 `qwen2.5:7b` 或 `deepseek-r1`） |
| 内存 | ≥ 16GB |

---

## 快速部署

### 一键启动（推荐）

直接双击运行 `start.bat`，自动启动后端 + 前端。

### 手动部署

**1. 克隆项目**
```bash
git clone https://github.com/cheny1145645/legal-rag.git
cd legal-rag
```

**2. 安装后端依赖**
```bash
cd backend
pip install -r requirements.txt
```

**3. 下载本地模型**（约 2GB）
```bash
pip install huggingface_hub
huggingface-cli download --local-dir=models/bge-m3 BAAI/bge-m3
huggingface-cli download --local-dir=models/bge-reranker-v2-m3 BAAI/bge-reranker-v2-m3
```

**4. 启动 Ollama**（确保本地已安装 Ollama）
```bash
ollama run qwen2.5:7b
# 或
ollama run deepseek-r1
```

**5. 启动后端**
```bash
cd backend
python run.py
```

**6. 访问系统**
- 前端：http://localhost:5173
- 后端 API：http://localhost:8001/docs
- API 文档（Swagger）：http://localhost:8001/docs

---

## 功能模块

###  法律问答（ChatView）

标准 RAG 问答流程：
1. 用户输入法律问题
2. 查询增强（可选 HyDE / Multi-Query）
3. 混合检索（BM25 + BGE-M3 向量 + LCCP 校验）
4. Reranker 重排
5. 调用 LLM 生成回答
6. 流式输出思维链和答案

###  Agent 自主模式（AgentView）

基于 Plan-Execute 循环的智能体，支持：

| 模式 | 说明 |
|------|------|
|     对话模式 | 自由提问，Agent 自主选择工具链 |
|     文件分析 | 上传文件后自动读取并分析内容 |
|   目录批处理 | 批量分析目录下所有文件，生成摘要报告 |
|     文书生成 | 填写标题和当事人信息，生成标准 Word 文书 |

**内置 7 个工具：**

| 工具 | 功能 |
|------|------|
| `read_file` | 读取本地文件（.txt/.md/.docx/.pdf） |
| `list_dir` | 列出目录文件树 |
| `write_file` | 写入或追加文件 |
| `search_kb` | 检索本地法律知识库（混合检索） |
| `web_search` | 联网检索（OpenLaw → 北大法宝 → DuckDuckGo 三级级联） |
| `analyze_dir` | 批量分析目录内文件，返回摘要报告 |
| `generate_legal_doc` | 生成格式化 Word 文书或纯文本 |

**SSE 事件流：** `thinking` → `tool_call` → `tool_result` → `text` → `done`

###  知识库管理（KnowledgeView）

- 目录批量入库：指定 `data/raw/` 目录，一键加载所有文档
- 单文件上传：支持 PDF / Word / TXT 直接上传
- 法律文本专项切割：章/节/条/款层级感知切块
- 向量入库：自动嵌入 + 建立 BM25 索引

###  数据统计（AnalyticsView）

- 检索命中率分析
- 知识库规模统计
- 使用热度排行

###  开发者监控（DeveloperView）

- 实时 LLM 调用日志
- 检索中间结果查看
- 性能指标监控

###  暂存池（PendingPoolView）

人机协作审核流水线：
- 待审核队列展示
- 异步评估结果查看
- 批量确认/拒绝操作

---

## 配置说明

`.env` 关键参数说明：

```env
# LLM 配置
OLLAMA_BASE_URL=http://localhost:11434      # Ollama 服务地址
OLLAMA_MODEL=qwen2.5:7b                     # LLM 模型（支持任意 Ollama 模型）
OLLAMA_KEEP_ALIVE=120                       # 模型保持时间（秒）

# 模型路径（相对路径，相对于 backend/ 目录）
EMBEDDING_MODEL=../models/bge-m3
RERANKER_MODEL=../models/bge-reranker-v2-m3

# 检索配置
TOP_K_RETRIEVAL=5           # 初始检索条数
BM25_WEIGHT=0.4             # BM25 权重（0~1）
VECTOR_WEIGHT=0.6           # 向量检索权重（0~1）

# 查询增强模式: hyde | multi_query | off
QUERY_ENHANCE_MODE=off

# 知识图谱开关
ENABLE_KNOWLEDGE_GRAPH=true

# 置信度传播
LCCP_THRESHOLD=0.6          # LCCP 置信度阈值

# 端口
PORT=8001                   # 后端端口
```

---

## 项目结构

```
legal-rag/
├── backend/
│   ├── app/
│   │   ├── api/                      # FastAPI 路由
│   │   │   ├── chat.py               # 问答接口
│   │   │   ├── agent.py              # Agent 接口
│   │   │   ├── ingest.py             # 文档入库
│   │   │   ├── system.py             # 系统状态
│   │   │   ├── model.py              # 模型管理
│   │   │   ├── developer.py          # 开发者监控
│   │   │   └── pending_pool.py      # 暂存池
│   │   ├── core/                     # 核心逻辑
│   │   │   ├── retriever.py          # 混合检索（BM25+向量+GLVR+QAWRF）
│   │   │   ├── reranker.py           # BGE-Reranker 重排序
│   │   │   ├── rag_pipeline.py       # RAG 推理流水线
│   │   │   ├── agent.py              # Agent 智能体（Plan-Execute 循环）
│   │   │   ├── web_searcher.py       # 联网搜索（OpenLaw/北大法宝/DDG）
│   │   │   ├── knowledge_graph.py    # 知识图谱（Neo4j）
│   │   │   ├── lccp.py               # 置信度传播
│   │   │   ├── query_enhancer.py     # 查询增强（HyDE/Multi-Query）
│   │   │   ├── document_processor.py # 文档加载与法律文本切割
│   │   │   ├── vector_store.py       # ChromaDB 管理
│   │   │   ├── llm_client.py         # LLM 客户端
│   │   │   └── memory_manager.py     # 对话记忆
│   │   ├── rag/                      # RAG 增强模块
│   │   │   ├── pending_pool.py       # 暂存池
│   │   │   ├── async_evaluator.py    # 异步评估器
│   │   │   ├── document_evaluator.py # 文档评估器
│   │   │   └── redis_mock.py         # Redis 模拟
│   │   ├── models/schemas.py          # Pydantic 数据模型
│   │   ├── config.py                 # 配置管理
│   │   └── main.py                   # FastAPI 入口
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── views/                     # 页面组件
│   │   │   ├── ChatView.vue          # 法律问答
│   │   │   ├── AgentView.vue         # Agent 自主模式
│   │   │   ├── KnowledgeView.vue     # 知识库管理
│   │   │   ├── AnalyticsView.vue     # 数据统计
│   │   │   ├── DeveloperView.vue     # 开发者监控
│   │   │   ├── PendingPoolView.vue   # 暂存池
│   │   │   └── AboutView.vue         # 关于
│   │   ├── components/               # 公共组件
│   │   ├── stores/chat.js            # Pinia 状态管理
│   │   └── api/                     # 接口封装
│   └── index.html                    # 前端入口
├── models/                           # 本地模型（需下载）
│   ├── bge-m3/                      # 嵌入模型
│   └── bge-reranker-v2-m3/          # 重排模型
├── data/
│   ├── raw/                         # 原始法律文档
│   └── vectordb/                    # ChromaDB 向量库（自动生成）
├── scripts/
│   ├── install_deps.py              # 依赖安装脚本
│   └── prepare_data.py              # 数据准备脚本
└── start.bat                        # 一键启动脚本
```

---

## 扩展指南

### 新增 Agent 工具

在 `backend/app/core/agent.py` 中新增处理函数并注册：

```python
def _my_tool_handler(param1: str, param2: int = 10) -> str:
    """工具描述（LLM 会读取此文档决定是否调用）"""
    return f"结果: {param1}, {param2}"

# 在 ToolRegistry._register_default_tools() 中注册：
self.register(Tool(
    name="my_tool",
    description="自然语言描述工具用途",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "参数说明"},
            "param2": {"type": "integer", "description": "参数说明", "default": 10}
        },
        "required": ["param1"]
    },
    handler=_my_tool_handler
))
```

### 接入新数据源

在 `backend/app/core/document_processor.py` 的 `LegalDocumentProcessor` 中添加加载器：

```python
# 支持的文件类型通过 suffix 识别
# 在 `load_document()` 方法中新增 elif 分支即可
```

### 切换 LLM

修改 `.env` 中的 `OLLAMA_MODEL` 即可，无需改动代码：

```env
OLLAMA_MODEL=qwen2.5:7b     # 通义千问
OLLAMA_MODEL=deepseek-r1     # DeepSeek 推理模型
OLLAMA_MODEL=mistral         # Mistral
```

---

## License

MIT License

---

## 推荐数据来源

- 中国法律法规数据库：https://flk.npc.gov.cn
- 北大法宝：https://www.pkulaw.com
- 国家法律法规数据库：https://flk.npc.gov.cn
