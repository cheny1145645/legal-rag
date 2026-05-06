import axios from 'axios'
import { ElMessage } from 'element-plus'
import { pendingPoolApi } from './pending_pool'

const http = axios.create({
  baseURL: 'http://localhost:8001/api',  // 直接请求后端（生产模式）
  timeout: 180000, // 通用3分钟超时
})

// 知识库接口 - 目录加载单独设置更长超时
http.post('/ingest/load-directory', {}, { timeout: 1800000 }) // 30分钟

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

// 问答接口
export const chatApi = {
  query: (data) => http.post('/chat/query', data),
  // 流式接口：返回 fetch Response，调用方自行处理 ReadableStream
  stream: (data) =>
    fetch('http://localhost:8001/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
}

// 知识库接口
export const ingestApi = {
  uploadFile: (formData) =>
    http.post('/ingest/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  loadDirectory: () => http.post('/ingest/load-directory'),  // 已有数据则跳过
  forceReload: () => http.post('/ingest/force-reload'),   // 强制重新入库
  clearVectorStore: () => http.delete('/ingest/clear'),
  deleteSource: (sourceName) =>
    http.delete('/ingest/source', { data: { source_name: sourceName } }),
  auditKnowledgeBase: (params) =>
    http.post('/ingest/audit', params, { timeout: 300000 }),  // 审核可能较慢，5分钟超时
}

// 系统接口
export const systemApi = {
  health: () => http.get('/health'),
  stats: () => http.get('/stats'),
  sources: () => http.get('/stats/sources'),
  analytics: () => http.get('/analytics'),
  rerankerStatus: () => http.get('/reranker-status'),
  rerankerToggle: (enable) => http.post(`/reranker-toggle?enable=${enable}`),
  
  // 核心算法模块管理
  getModulesStatus: () => http.get('/modules/status'),
  toggleModule: (module, enable, params = null) => 
    http.post(`/modules/toggle?module=${module}&enable=${enable}`, params),
  getLogLevel: () => http.get('/modules/log-level'),
  setLogLevel: (level) => http.post(`/modules/log-level?level=${level}`),
}

// 模型管理接口
export const modelApi = {
  listOllamaModels: (ollamaUrl) =>
    http.get('/models', { params: ollamaUrl ? { ollama_url: ollamaUrl } : {} }),
  getPresets: () => http.get('/llm-presets'),
  getLLMConfig: () => http.get('/llm-config'),
  setLLMConfig: (data) => http.post('/llm-config', data),
  testLLM: () => http.post('/llm-test'),
}

// 暂存池管理接口
export { pendingPoolApi }

// Agent 接口
export const agentApi = {
  // 获取可用工具列表
  listTools: () => http.get('/agent/tools'),
  // Agent 流式对话（SSE）
  chat: (data) =>
    fetch('http://localhost:8001/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  // 上传文件并分析（SSE 流式）
  uploadAndAnalyze: (file, question = '', sessionId = null) => {
    const form = new FormData()
    form.append('file', file)
    if (question) form.append('question', question)
    if (sessionId) form.append('session_id', sessionId)
    return fetch('http://localhost:8001/api/agent/upload-and-analyze', { method: 'POST', body: form })
  },
  // 目录批量分析（SSE 流式）
  analyzeDir: (path, sessionId = null) => {
    const params = new URLSearchParams({ path })
    if (sessionId) params.append('session_id', sessionId)
    return fetch(`http://localhost:8001/api/agent/analyze-dir?${params}`, { method: 'POST' })
  },
  // 下载生成的文书
  downloadFile: (filePath) => {
    const params = new URLSearchParams({ file_path: filePath })
    window.open(`http://localhost:8001/api/agent/download?${params}`, '_blank')
  },
}




