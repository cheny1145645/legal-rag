import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi } from '@/api'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const loading = ref(false)
  const sessionId = ref(null)
  const chatRunId = ref(null)  // 追踪当前流式会话 ID，用于中断

  // ── RAG 运行时配置 ────────────────────────────────────────────────────────
  const enhanceMode = ref('hyde')   // "hyde" | "multi_query" | "off"
  const enableKg = ref(true)
  const topK = ref(5)
  const enableWebSearch = ref(null)  // null=自动判断, true=强制开启, false=强制关闭
  const enableRerank = ref(false)   // Reranker 开关（默认关闭，节省内存）

  // ── LLM 模型配置 ──────────────────────────────────────────────────────────
  // provider: "ollama"（本地）| "remote"（远程 API）
  const llmProvider = ref('ollama')
  // Ollama 本地模型
  const ollamaModel = ref('')       // 空字符串 = 跟随全局配置
  // 远程 API
  const remotePreset = ref('deepseek')  // 当前选中的预设服务商 key
  const remoteBaseUrl = ref('')
  const remoteApiKey = ref('')
  const remoteModel = ref('')

  // 当前模型显示名（用于 UI 标题栏简短展示）
  const modelLabel = computed(() => {
    if (llmProvider.value === 'remote') {
      return remoteModel.value || '远程 API'
    }
    return ollamaModel.value || 'Ollama 默认'
  })

  const addMessage = (role, content, sources = [], thinking = null, msgEnhanceMode = null, memoryInfo = null, webSearchTriggered = false, webDocsCount = 0) => {
    messages.value.push({
      id: Date.now(),
      role,
      content,
      sources,
      thinking,
      enhanceMode: msgEnhanceMode,
      memoryInfo,
      webSearchTriggered,
      webDocsCount,
      time: new Date().toLocaleTimeString('zh-CN'),
    })
  }

  const sendQuestion = async (question) => {
    if (!question.trim() || loading.value) return

    addMessage('user', question)
    loading.value = true

    // 先插入一条空 AI 消息，流式内容往里填
    const aiMsg = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      sources: [],
      thinking: null,
      enhanceMode: null,
      memoryInfo: null,
      webSearchTriggered: false,
      webDocsCount: 0,
      time: new Date().toLocaleTimeString('zh-CN'),
      streaming: true,
    }
    messages.value.push(aiMsg)
    const msgIndex = messages.value.length - 1

    try {
      const payload = {
        question,
        session_id: sessionId.value,
        top_k: topK.value,
        enhance_mode: enhanceMode.value,
        enable_kg: enableKg.value,
        enable_rerank: enableRerank.value,
        enable_web_search: enableWebSearch.value,
      }
      if (llmProvider.value === 'ollama' && ollamaModel.value) {
        payload.llm_provider = 'ollama'
        payload.llm_ollama_model = ollamaModel.value
      } else if (llmProvider.value === 'remote') {
        payload.llm_provider = 'remote'
        payload.llm_remote_base_url = remoteBaseUrl.value
        payload.llm_remote_api_key = remoteApiKey.value
        payload.llm_remote_model = remoteModel.value
      }

      const resp = await chatApi.stream(payload)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() // 最后一行可能不完整，留着
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const text = line.slice(5).trim()
          if (!text) continue
          try {
            const evt = JSON.parse(text)
            if (evt.type === 'meta') {
              sessionId.value = evt.session_id
              chatRunId.value = evt.session_id
              messages.value[msgIndex].sources = evt.sources || []
              messages.value[msgIndex].enhanceMode = evt.enhance_mode
              messages.value[msgIndex].memoryInfo = evt.memory_info
              messages.value[msgIndex].webSearchTriggered = evt.web_search_triggered
              messages.value[msgIndex].webDocsCount = evt.web_docs_count
            } else if (evt.type === 'thinking') {
              // 推理过程实时追加
              if (!messages.value[msgIndex].thinking) {
                messages.value[msgIndex].thinking = ''
              }
              messages.value[msgIndex].thinking += evt.content
            } else if (evt.type === 'text') {
              messages.value[msgIndex].content += evt.content
            } else if (evt.type === 'done') {
              messages.value[msgIndex].streaming = false
            } else if (evt.type === 'error') {
              messages.value[msgIndex].content = `错误：${evt.content}`
              messages.value[msgIndex].streaming = false
            } else if (evt.type === 'aborted') {
              messages.value[msgIndex].streaming = false
            }
          } catch {}
        }
      }
    } catch (e) {
      messages.value[msgIndex].content = '抱歉，系统出现错误，请稍后重试。'
      messages.value[msgIndex].streaming = false
    } finally {
      messages.value[msgIndex].streaming = false
      loading.value = false
    }
  }

  const clearMessages = () => {
    messages.value = []
    sessionId.value = null
    chatRunId.value = null
  }

  const abortChat = async () => {
    if (!chatRunId.value) return
    try {
      const res = await fetch('http://localhost:8001/api/chat/abort', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionKey: chatRunId.value }),
      })
      if (!res.ok) throw new Error(`Abort failed: ${res.status}`)
    } catch {}
  }

  return {
    messages,
    loading,
    sessionId,
    // RAG 配置
    enhanceMode,
    enableKg,
    topK,
    enableWebSearch,
    enableRerank,
    // LLM 配置
    llmProvider,
    ollamaModel,
    remotePreset,
    remoteBaseUrl,
    remoteApiKey,
    remoteModel,
    modelLabel,
    // 方法
    sendQuestion,
    abortChat,
    clearMessages,
  }
})
