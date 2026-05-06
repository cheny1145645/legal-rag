# 法律咨询智能问答系统

基于 RAG（检索增强生成）技术的法律咨询智能问答系统，采用本地部署的 DeepSeek-R1 大模型，实现专业、准确、隐私安全的法律问答服务。

---

## 系统特色

- **混合检索策略**：融合 BM25 关键词检索与 BGE-M3 向量语义检索，通过加权融合显著提升法律专业术语召回率
- **法律文本专项处理**：针对法律条文层级结构（章、节、条、款）进行智能切割，保留条文完整性
- **DeepSeek-R1 本地推理**：全程本地运行，数据不出本机，保护咨询隐私
- **思维链可视化**：展示 DeepSeek-R1 的推理过程，增强答案可信度

---

## 技术架构

```
前端 (Vue3 + Element Plus)
    ↓  HTTP/REST
后端 (FastAPI)
    ├── 混合检索器 (BM25 + ChromaDB)
    │       ↑
    │   BGE-M3 嵌入模型
    └── DeepSeek-R1 (Ollama 本地推理)
```

---

## 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+（仅开发前端时需要，前端已内置构建产物） |
| GPU | NVIDIA，建议 ≥ 8GB 显存 |
| Ollama | 已安装并拉取 qwen2.5:7b 或 deepseek-r1 模型 |
| 内存 | ≥ 16GB |

## 模型下载

首次部署需要下载两个本地模型（约 2GB），项目提供了离线包和下载脚本：

```bash
# 方式一：用脚本自动下载（推荐）
python scripts/download_models.py

# 方式二：用 Ollama 管理（需联网）
ollama pull bge-m3
ollama pull bge-reranker-v2-m3
```

> 如果 `scripts/download_models.py` 不存在，可以用 HuggingFace CLI：
> ```bash
> pip install huggingface_hub
> huggingface-cli download --local-dir=models/bge-m3 BAAI/bge-m3
> huggingface-cli download --local-dir=models/bge-reranker-v2-m3 BAAI/bge-reranker-v2-m3
> ```

---

## 快速启动

### 方式一：一键启动（推荐）

双击运行 `start.bat`

### 方式二：手动启动

**1. 安装后端依赖**
```bash
cd backend
pip install -r requirements.txt
```

**2. 启动后端**
```bash
cd backend
python run.py
```

**3. 安装并启动前端**
```bash
cd frontend
npm install
npm run dev
```

**4. 访问系统**
- 前端：http://localhost:5173
- API文档：http://localhost:8001/docs

---

## 使用指南

### 第一步：准备法律文档
将法律文本文件（PDF / Word / TXT）放入 `data/raw/` 目录。

推荐数据来源：
- 中国法律法规数据库：https://flk.npc.gov.cn
- 北大法宝：https://www.pkulaw.com

### 第二步：入库文档
打开系统 → 知识库管理 → 点击「加载文档目录」

也可以在知识库管理页面直接上传单个文件。

### 第三步：开始问答
切换到「法律问答」页面，输入法律问题即可。

---

## 项目结构

```
legal-rag/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由
│   │   │   ├── chat.py       # 问答接口
│   │   │   ├── ingest.py     # 文档入库接口
│   │   │   └── system.py     # 系统状态接口
│   │   ├── core/         # 核心逻辑
│   │   │   ├── document_processor.py  # 文档加载与法律文本切割
│   │   │   ├── vector_store.py        # ChromaDB 向量库管理
│   │   │   ├── retriever.py           # 混合检索器
│   │   │   └── rag_pipeline.py        # RAG 推理流水线
│   │   ├── models/
│   │   │   └── schemas.py    # 数据模型
│   │   ├── config.py     # 配置管理
│   │   └── main.py       # FastAPI 应用入口
│   ├── requirements.txt
│   ├── run.py
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── stores/       # Pinia 状态管理
│   │   ├── api/          # 接口封装
│   │   └── App.vue       # 根组件
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── raw/              # 原始法律文档（放这里）
│   └── vectordb/         # ChromaDB 向量库（自动生成）
├── scripts/
│   ├── install_deps.py
│   └── prepare_data.py
└── start.bat             # 一键启动
```

---

## 配置说明

修改 `backend/.env` 调整系统参数：

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b             # 支持 qwen2.5、deepseek-r1 等任意 Ollama 模型
PORT=8001                           # 后端端口
CHUNK_SIZE=500                      # 文档切块大小
TOP_K_RETRIEVAL=5                   # 检索返回条数
BM25_WEIGHT=0.4                     # BM25检索权重
VECTOR_WEIGHT=0.6                   # 向量检索权重
```

---

## 软件著作权说明

本系统代码原创，包含以下技术创新：
1. **法律文本专项切割算法**（`document_processor.py`）
2. **BM25+向量混合检索融合策略**（`retriever.py`）
3. **法律场景RAG推理流水线**（`rag_pipeline.py`）

可依据本系统源代码申请软件著作权登记。

---

## License

MIT License
