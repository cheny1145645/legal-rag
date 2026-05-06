# Legal RAG — Agent 模块流程说明

> 文件位置：`backend/app/core/agent.py`  
> API 入口：`backend/app/api/agent.py`  
> 前端页面：`frontend/src/views/AgentView.vue`

---

## 一、整体架构

```
用户输入
   │
   ▼
AgentView.vue（前端）
   │  SSE 流式连接
   ▼
POST /api/agent/chat（FastAPI）
   │
   ▼
Agent.chat()  ◄─────────────────────────────────┐
   │                                             │
   ├── 构建 system prompt（含工具 schema）         │
   ├── 调用 LLM（Ollama 本地 / 远程 API）         │
   ├── 解析输出中的 [[TOOL_CALL]] 块              │
   ├── 执行工具 → 拿到结果                        │
   └── 把结果追加进对话历史 ─────────────────────┘
         循环，直到：
         · LLM 不再调用工具  → 输出最终回答
         · 迭代次数 ≥ max_iterations(10) → 强制结束
```

---

## 二、Agent 循环详解（观察 → 思考 → 行动）

每一轮迭代包含以下步骤：

```
┌─────────────────────────────────────────────────────┐
│  第 N 轮迭代                                         │
│                                                     │
│  1. 构建 prompt                                     │
│     · 首轮：直接发用户问题                            │
│     · 多轮：把历史消息（含工具结果）拼成完整段落         │
│                                                     │
│  2. 调用 LLM（流式/非流式）                          │
│     · 远程 API → chat_stream()，实时 yield thinking  │
│     · 本地 Ollama → chat()，一次性返回               │
│                                                     │
│  3. 解析 [[TOOL_CALL]] 块                           │
│     · 用 re.findall 提取块内容                       │
│     · 用 find('{') + rfind('}') 定位 JSON 边界       │
│     · json.loads() 解析，必须有 name + arguments     │
│                                                     │
│  4. 分支判断                                        │
│     · 有工具调用 → 执行工具（见第三节）→ 下一轮       │
│     · 无工具调用 → 清理残留标记 → yield text → 结束  │
└─────────────────────────────────────────────────────┘
```

### SSE 事件类型

| 事件类型 | 含义 | 前端显示 |
|---|---|---|
| `thinking` | LLM 正在推理 / 迭代提示 | 折叠的思考气泡 |
| `tool_call` | 即将调用某个工具（含参数） | 蓝色工具卡片 |
| `tool_result` | 工具执行返回的内容 | 绿色/红色结果块 |
| `text` | 最终回答文本 | 主对话气泡 |
| `done` | 流结束 | - |

---

## 三、工具注册表（ToolRegistry）

共 7 个工具，均在 `ToolRegistry._register_default_tools()` 中注册：

| 工具名 | 函数 | 主要参数 | 作用 |
|---|---|---|---|
| `read_file` | `_read_file_handler` | `path`, `encoding` | 读取文件内容，支持 .txt/.md/.docx/.pdf |
| `list_dir` | `_list_dir_handler` | `path`, `show_hidden` | 列出目录文件树 |
| `write_file` | `_write_file_handler` | `path`, `content`, `mode` | 写入或追加文本文件 |
| `search_kb` | `_search_kb_handler` | `query`, `top_k` | 检索本地法律知识库（BM25+向量融合） |
| `web_search` | `_web_search_handler` | `query`, `max_results` | 联网搜索（OpenLaw → 北大法宝 → DuckDuckGo 三级级联） |
| `analyze_dir` | `_analyze_dir_handler` | `path`, `file_types`, `max_files` | 批量分析目录内文件，返回摘要报告 |
| `generate_legal_doc` | `_generate_legal_doc_handler` | `title`, `content`, `output_path`, `doc_type` | 生成格式化 Word 文书（.docx）或纯文本 |

### 安全策略

- **read_file**：黑名单模式，阻止读取 `Windows/System32/Program Files/AppData` 等系统目录
- **write_file**：黑名单模式，阻止写入系统目录；允许写入任意用户路径
- **analyze_dir**：每个文件只读前 3000 字符，防止超大目录撑爆上下文

---

## 四、联网搜索（web_search）详解

入口：`backend/app/core/web_searcher.py`

```
web_search_handler(query)
   │
   ▼
WebSearcher.search(query)
   │
   ├─ 法律话题过滤（白名单关键词）
   │   · 含法律关键词 → 继续搜索
   │   · 不含（且含黑名单词）→ 返回空
   │
   ├─ [来源1] OpenLaw (openlaw.cn) 爬取
   │   · requests GET + BeautifulSoup 解析
   │   · 提取案例标题、摘要、URL
   │
   ├─ [来源2] 北大法宝 (pkulaw.com)
   │   · 同上，解析搜索结果页
   │
   └─ [来源3] DuckDuckGo（兜底）
       · duckduckgo_search==3.9.11
       · region=cn-zh，最多取 5 条
       · 再次过法律话题过滤
```

**注意**：OpenLaw 和北大法宝需要能访问这两个网站，网络受限时会自动降级到 DuckDuckGo。

---

## 五、多轮对话上下文传递

LLM 接口（Ollama / 远程 API）目前通过单段文本方式接收上下文：

```
第1轮：prompt = "帮我写劳动合同"
        └─ LLM 调用 search_kb → 返回法律条款片段

第2轮：prompt = "[用户]: 帮我写劳动合同
                 [助手]: [[TOOL_CALL]]...search_kb结果...[[/TOOL_CALL]]
                         找到以下条款：...
                 [助手]: 请继续完成任务。"
        └─ LLM 根据完整历史调用 generate_legal_doc
```

这样 LLM 在第2轮不会"忘记"第1轮工具的结果。

---

## 六、前端 AgentView 四种模式

| 模式 | 接口 | 说明 |
|---|---|---|
| 💬 对话模式 | `POST /api/agent/chat` | 自由提问，Agent 自主选工具 |
| 📄 文件分析 | `POST /api/agent/upload-and-analyze` | 上传文件后自动调 read_file 分析 |
| 📁 目录批处理 | `POST /api/agent/analyze-dir` | 输入目录路径，批量分析文件 |
| 📝 文书生成 | `POST /api/agent/chat`（带提示词模板） | 填写标题+当事人，生成标准 Word 文书 |

---

## 七、扩展工具（How To）

在 `backend/app/core/agent.py` 中：

1. 在文件顶部新增处理函数：
```python
def _my_tool_handler(param1: str, param2: int = 10) -> str:
    """工具功能描述"""
    # ... 实现 ...
    return "结果字符串"
```

2. 在 `ToolRegistry._register_default_tools()` 末尾注册：
```python
self.register(Tool(
    name="my_tool",
    description="工具的自然语言描述（LLM 会读这段话来决定是否调用）",
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

注册后无需重启前端，刷新页面右侧工具面板即可看到新工具。
