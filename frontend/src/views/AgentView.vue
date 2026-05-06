<template>
  <div class="agent-view">
    <!-- 顶部标题栏 -->
    <div class="agent-header">
      <div class="header-left">
        <div class="header-icon agent-icon">
          <el-icon size="16"><Cpu /></el-icon>
        </div>
        <span class="header-title">Agent 自主模式</span>
        <span class="header-badge">自主决策</span>
        <span class="iter-badge" v-if="currentIteration > 0">
          第 {{ currentIteration }} 轮迭代
        </span>
      </div>
      <div class="header-right">
        <!-- 模式切换 -->
        <div class="mode-tabs">
          <button
            v-for="m in modes"
            :key="m.value"
            class="mode-tab"
            :class="{ active: activeMode === m.value }"
            @click="switchMode(m.value)"
          >
            <el-icon size="12"><component :is="m.icon" /></el-icon>
            {{ m.label }}
          </button>
        </div>
        <button class="clear-btn" @click="clearAll">
          <el-icon size="13"><Delete /></el-icon>
          清空
        </button>
      </div>
    </div>

    <!-- 主体区域 -->
    <div class="agent-body">
      <!-- 左侧：对话区 -->
      <div class="chat-panel">
        <!-- 欢迎页 -->
        <transition name="welcome-fade">
          <div v-if="messages.length === 0 && !isLoading" class="agent-welcome">
            <div class="aw-icon-wrap">
              <div class="aw-ring r1"></div>
              <div class="aw-ring r2"></div>
              <div class="aw-icon">
                <el-icon size="40"><Cpu /></el-icon>
              </div>
            </div>
            <h2 class="aw-title">Agent 自主模式</h2>
            <p class="aw-sub">AI 可自主调用工具，完成复杂法律任务</p>
            <div class="capability-grid">
              <div class="cap-card" v-for="cap in capabilities" :key="cap.title"
                   @click="handleCapClick(cap)">
                <el-icon size="20" :style="{ color: cap.color }"><component :is="cap.icon" /></el-icon>
                <div class="cap-info">
                  <div class="cap-title">{{ cap.title }}</div>
                  <div class="cap-desc">{{ cap.desc }}</div>
                </div>
              </div>
            </div>
          </div>
        </transition>

        <!-- 消息列表 -->
        <div class="msg-list" ref="msgListRef">
          <template v-for="(msg, idx) in messages" :key="msg.id">
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="msg-row user">
              <div class="spacer"></div>
              <div class="bubble user-bubble">{{ msg.content }}</div>
              <div class="avatar user-av">
                <el-icon size="14"><User /></el-icon>
              </div>
            </div>

            <!-- Agent 消息 -->
            <div v-else class="msg-row agent">
              <div class="avatar agent-av" :class="{ spinning: msg.streaming }">
                <el-icon size="14"><Cpu /></el-icon>
              </div>
              <div class="agent-content">
                <!-- 工具调用时间线 -->
                <div v-if="msg.steps && msg.steps.length > 0" class="steps-timeline">
                  <div class="timeline-header">
                    <el-icon size="11"><Timer /></el-icon>
                    <span>执行过程 ({{ msg.steps.length }} 步)</span>
                    <button class="toggle-steps" @click="toggleSteps(msg.id)">
                      {{ stepsOpen[msg.id] ? '收起' : '展开' }}
                    </button>
                  </div>
                  <transition name="slide-down">
                    <div v-if="stepsOpen[msg.id] !== false" class="timeline-body">
                      <div
                        v-for="(step, si) in msg.steps"
                        :key="si"
                        class="step-item"
                        :class="step.type"
                      >
                        <div class="step-dot">
                          <el-icon size="10"><component :is="stepIcon(step.type)" /></el-icon>
                        </div>
                        <div class="step-content">
                          <span class="step-label">{{ stepLabel(step.type) }}</span>
                          <template v-if="step.type === 'tool_call'">
                            <span class="tool-name">{{ step.tool?.name || '工具' }}</span>
                            <div class="tool-args" v-if="step.tool?.arguments">
                              <span
                                v-for="(v, k) in step.tool.arguments"
                                :key="k"
                                class="tool-arg-chip"
                              >
                                {{ k }}: {{ truncate(String(v), 40) }}
                              </span>
                            </div>
                          </template>
                          <template v-else-if="step.type === 'tool_result'">
                            <div class="tool-result-preview">{{ truncate(step.content, 120) }}</div>
                          </template>
                          <template v-else>
                            <div class="thinking-text">{{ truncate(step.content, 100) }}</div>
                          </template>
                        </div>
                      </div>
                    </div>
                  </transition>
                </div>

                <!-- 回答气泡 -->
                <div v-if="msg.content" class="bubble agent-bubble" :class="{ streaming: msg.streaming }">
                  <div class="answer-text" v-html="renderMarkdown(msg.content)"></div>
                  <!-- 如果内容中有文件路径，显示下载按钮 -->
                  <div v-if="extractFilePaths(msg.content).length > 0" class="download-bar">
                    <button
                      v-for="fp in extractFilePaths(msg.content)"
                      :key="fp"
                      class="download-btn"
                      @click="downloadFile(fp)"
                    >
                      <el-icon size="12"><Download /></el-icon>
                      下载 {{ getFileName(fp) }}
                    </button>
                  </div>
                </div>

                <!-- 流式加载中（还没有 content） -->
                <div v-if="msg.streaming && !msg.content" class="bubble agent-bubble loading-bubble">
                  <div class="loading-scanner"><div class="scanner-bar"></div></div>
                  <div class="loading-content">
                    <div class="thinking-dots"><span></span><span></span><span></span></div>
                    <span class="thinking-text-s">Agent 正在执行...</span>
                  </div>
                </div>

                <div class="msg-time">{{ msg.time }}</div>
              </div>
            </div>
          </template>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
          <!-- 文件上传区（文件分析模式） -->
          <div v-if="activeMode === 'file'" class="file-upload-zone"
               :class="{ dragging: isDragging }"
               @dragover.prevent="isDragging = true"
               @dragleave="isDragging = false"
               @drop.prevent="handleDrop">
            <template v-if="!uploadedFile">
              <el-icon size="24" style="color: var(--accent-light)"><Upload /></el-icon>
              <span>拖拽文件到此处，或</span>
              <label class="upload-label">
                <input type="file" @change="handleFileSelect" style="display:none"
                       accept=".txt,.md,.doc,.docx,.pdf,.csv" />
                点击选择文件
              </label>
              <span class="hint-text">支持 .txt .md .doc .docx .pdf</span>
            </template>
            <template v-else>
              <el-icon size="20" style="color: var(--accent-light)"><Document /></el-icon>
              <span class="file-name">{{ uploadedFile.name }}</span>
              <span class="file-size">{{ (uploadedFile.size / 1024).toFixed(1) }}KB</span>
              <button class="remove-file" @click="uploadedFile = null">✕</button>
            </template>
          </div>

          <!-- 目录路径输入（目录分析模式） -->
          <div v-if="activeMode === 'dir'" class="dir-input-zone">
            <el-icon size="16" style="color: var(--accent-light)"><FolderOpened /></el-icon>
            <el-input
              v-model="dirPath"
              placeholder="输入要分析的目录路径，如 D:\法律文件夹"
              class="dir-input"
              @keydown.enter.prevent="sendDirAnalysis"
            />
            <button class="dir-analyze-btn" :disabled="!dirPath.trim() || isLoading" @click="sendDirAnalysis">
              <el-icon size="14"><Search /></el-icon>
              分析
            </button>
          </div>

          <!-- 文字输入（对话/文书模式） -->
          <div v-if="activeMode !== 'dir'" class="input-wrap">
            <el-input
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 5 }"
              :placeholder="inputPlaceholder"
              @keydown.enter.exact.prevent="handleSend"
              @keydown.shift.enter.prevent="inputText += '\n'"
              class="agent-input"
            />
            <button
              class="send-btn"
              :class="{ active: canSend }"
              :disabled="!canSend"
              @click="handleSend"
            >
              <el-icon v-if="!isLoading" size="18"><Promotion /></el-icon>
              <el-icon v-else class="rotating" size="18"><Loading /></el-icon>
            </button>
          </div>
          <div class="input-hint">
            <template v-if="activeMode === 'chat'">Agent 可自主调用工具完成任务 · Shift+Enter 换行</template>
            <template v-else-if="activeMode === 'file'">上传文件后输入问题，Agent 将读取并分析</template>
            <template v-else-if="activeMode === 'dir'">输入目录路径，Agent 将批量分析其中所有文档</template>
            <template v-else-if="activeMode === 'doc'">描述需要生成的法律文书，Agent 将帮您起草</template>
          </div>
        </div>
      </div>

      <!-- 右侧：工具面板 -->
      <div class="tools-panel" :class="{ collapsed: toolsPanelCollapsed }">
        <div class="tools-panel-header" @click="toolsPanelCollapsed = !toolsPanelCollapsed">
          <el-icon size="13"><Tools /></el-icon>
          <span>可用工具 ({{ tools.length }})</span>
          <el-icon size="11" class="collapse-arrow" :class="{ open: !toolsPanelCollapsed }">
            <ArrowRight />
          </el-icon>
        </div>
        <transition name="slide-down">
          <div v-if="!toolsPanelCollapsed" class="tools-list">
            <div
              v-for="tool in tools"
              :key="tool.name"
              class="tool-card"
              :class="{ active: activeTool === tool.name }"
            >
              <div class="tool-header">
                <el-icon size="11" :style="{ color: toolColor(tool.name) }">
                  <component :is="toolIcon(tool.name)" />
                </el-icon>
                <span class="tool-name">{{ tool.name }}</span>
              </div>
              <div class="tool-desc">{{ tool.description }}</div>
            </div>
          </div>
        </transition>

        <!-- 迭代统计 -->
        <div v-if="!toolsPanelCollapsed && stats.totalSteps > 0" class="run-stats">
          <div class="stats-title">本次执行统计</div>
          <div class="stats-row">
            <span>工具调用</span>
            <span class="stats-val">{{ stats.toolCalls }} 次</span>
          </div>
          <div class="stats-row">
            <span>迭代轮次</span>
            <span class="stats-val">{{ currentIteration }}</span>
          </div>
          <div class="stats-row">
            <span>总步骤数</span>
            <span class="stats-val">{{ stats.totalSteps }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import {
  Cpu, Delete, User, Timer, Download, Upload, Document,
  FolderOpened, Search, Promotion, Loading, Tools, ArrowRight,
  ChatDotRound, MagicStick, EditPen, Folder,
  Lightning, Check, MoreFilled, Tickets, Connection, Setting
} from '@element-plus/icons-vue'
import { agentApi } from '@/api'

// ── 状态 ────────────────────────────────────────────────────────────────────
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const msgListRef = ref(null)
const tools = ref([])
const activeTool = ref(null)
const stepsOpen = ref({})
const toolsPanelCollapsed = ref(false)
const currentIteration = ref(0)
const activeMode = ref('chat')  // 'chat' | 'file' | 'dir' | 'doc'
const uploadedFile = ref(null)
const dirPath = ref('')
const isDragging = ref(false)
const stats = ref({ toolCalls: 0, totalSteps: 0 })

// ── 模式配置 ─────────────────────────────────────────────────────────────────
const modes = [
  { value: 'chat', label: '对话', icon: ChatDotRound },
  { value: 'file', label: '文件分析', icon: Document },
  { value: 'dir',  label: '批量分析', icon: Folder },
  { value: 'doc',  label: '生成文书', icon: EditPen },
]

const capabilities = [
  { title: '文件分析', desc: '上传合同/文书，快速识别关键信息和风险', icon: Document, color: '#60a5fa', mode: 'file' },
  { title: '批量处理', desc: '扫描整个目录，批量分析所有法律文档', icon: FolderOpened, color: '#a78bfa', mode: 'dir' },
  { title: '文书生成', desc: '根据需求自动起草合同、起诉状等文书', icon: EditPen, color: '#34d399', mode: 'doc' },
  { title: '法律研究', desc: '结合知识库和联网检索，深度分析法律问题', icon: MagicStick, color: '#fbbf24', mode: 'chat' },
]

const inputPlaceholder = computed(() => {
  const map = {
    chat: '描述您的法律问题，Agent 将自主调用工具为您解答...',
    file: uploadedFile.value
      ? `对《${uploadedFile.value.name}》有什么问题？留空则自动全文分析`
      : '请先上传文件...',
    doc: '描述您需要的法律文书，例如：帮我起草一份软件开发服务合同，甲方为某某公司，乙方为某某个人...',
  }
  return map[activeMode.value] || '输入指令...'
})

const canSend = computed(() => {
  if (isLoading.value) return false
  if (activeMode.value === 'file') return uploadedFile.value != null
  if (activeMode.value === 'dir') return false  // 目录模式有独立按钮
  return inputText.value.trim().length > 0
})

// ── 初始化 ───────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const res = await agentApi.listTools()
    tools.value = res.tools || []
  } catch (e) {
    console.warn('获取工具列表失败:', e)
  }
})

// ── 交互 ─────────────────────────────────────────────────────────────────────
const switchMode = (mode) => {
  activeMode.value = mode
  uploadedFile.value = null
  inputText.value = ''
}

const handleCapClick = (cap) => {
  activeMode.value = cap.mode
}

const handleFileSelect = (e) => {
  const f = e.target.files[0]
  if (f) uploadedFile.value = f
}

const handleDrop = (e) => {
  isDragging.value = false
  const f = e.dataTransfer.files[0]
  if (f) uploadedFile.value = f
}

const toggleSteps = (id) => {
  stepsOpen.value[id] = stepsOpen.value[id] === false ? true : false
}

const handleSend = () => {
  if (!canSend.value) return
  if (activeMode.value === 'file' && uploadedFile.value) {
    sendFileAnalysis()
  } else if (activeMode.value === 'doc') {
    sendDocGenerate()
  } else {
    sendChat()
  }
}

// ── 核心：流式 SSE 处理 ──────────────────────────────────────────────────────
const handleSSEStream = async (response, aiMsgIdx) => {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  currentIteration.value = 0
  stats.value = { toolCalls: 0, totalSteps: 0 }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop()

    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const text = line.slice(5).trim()
      if (!text) continue
      try {
        const evt = JSON.parse(text)
        const msg = messages.value[aiMsgIdx]
        if (!msg) continue

        if (evt.type === 'thinking') {
          // 思考过程 → 追加到 steps
          const step = { type: 'thinking', content: evt.content }
          msg.steps.push(step)
          stats.value.totalSteps++
          // 检测迭代次数
          const m = evt.content.match(/\[迭代\s*(\d+)\]/)
          if (m) currentIteration.value = parseInt(m[1])
          activeTool.value = null
        } else if (evt.type === 'tool_call') {
          // 工具调用
          const tool = evt.tool || {}
          msg.steps.push({ type: 'tool_call', content: evt.content, tool })
          activeTool.value = tool.name
          stats.value.toolCalls++
          stats.value.totalSteps++
        } else if (evt.type === 'tool_result') {
          // 工具结果
          msg.steps.push({ type: 'tool_result', content: evt.content })
          stats.value.totalSteps++
          activeTool.value = null
        } else if (evt.type === 'text') {
          msg.content += evt.content
        } else if (evt.type === 'done') {
          msg.streaming = false
          activeTool.value = null
          // 默认展开第一条消息的 steps
          if (!stepsOpen.value[msg.id]) {
            stepsOpen.value[msg.id] = msg.steps.length > 0 ? true : false
          }
        } else if (evt.type === 'error') {
          msg.content = `⚠️ 执行出错：${evt.content}`
          msg.streaming = false
        }
      } catch {}
    }
    await scrollToBottom()
  }
}

const createAiMsg = () => {
  const msg = {
    id: Date.now() + 1,
    role: 'assistant',
    content: '',
    steps: [],
    streaming: true,
    time: new Date().toLocaleTimeString('zh-CN'),
  }
  messages.value.push(msg)
  return messages.value.length - 1
}

// 发送对话
const sendChat = async () => {
  const q = inputText.value.trim()
  if (!q) return
  inputText.value = ''
  addUserMsg(q)
  const idx = createAiMsg()
  isLoading.value = true
  try {
    const resp = await agentApi.chat({ prompt: q })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await handleSSEStream(resp, idx)
  } catch (e) {
    messages.value[idx].content = `⚠️ 请求失败：${e.message}`
    messages.value[idx].streaming = false
  } finally {
    isLoading.value = false
  }
}

// 发送文件分析
const sendFileAnalysis = async () => {
  const file = uploadedFile.value
  const question = inputText.value.trim()
  inputText.value = ''
  uploadedFile.value = null
  addUserMsg(question ? `分析文件《${file.name}》：${question}` : `分析文件《${file.name}》`)
  const idx = createAiMsg()
  isLoading.value = true
  try {
    const resp = await agentApi.uploadAndAnalyze(file, question)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await handleSSEStream(resp, idx)
  } catch (e) {
    messages.value[idx].content = `⚠️ 分析失败：${e.message}`
    messages.value[idx].streaming = false
  } finally {
    isLoading.value = false
  }
}

// 发送目录分析
const sendDirAnalysis = async () => {
  const path = dirPath.value.trim()
  if (!path) return
  addUserMsg(`批量分析目录：${path}`)
  const idx = createAiMsg()
  isLoading.value = true
  try {
    const resp = await agentApi.analyzeDir(path)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await handleSSEStream(resp, idx)
  } catch (e) {
    messages.value[idx].content = `⚠️ 分析失败：${e.message}`
    messages.value[idx].streaming = false
  } finally {
    isLoading.value = false
    dirPath.value = ''
  }
}

// 生成文书
const sendDocGenerate = async () => {
  const q = inputText.value.trim()
  if (!q) return
  inputText.value = ''
  const prompt = `请帮我生成一份法律文书。需求描述：${q}

请：
1. 根据描述确定文书类型（合同/起诉状/协议书等）
2. 如果需要查询相关法律规定，使用 search_kb 工具检索知识库
3. 生成完整、规范的文书内容
4. 使用 generate_legal_doc 工具将文书保存为Word文档
5. 告知用户文件保存路径并提供下载`
  addUserMsg(`生成文书：${q}`)
  const idx = createAiMsg()
  isLoading.value = true
  try {
    const resp = await agentApi.chat({ prompt })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await handleSSEStream(resp, idx)
  } catch (e) {
    messages.value[idx].content = `⚠️ 生成失败：${e.message}`
    messages.value[idx].streaming = false
  } finally {
    isLoading.value = false
  }
}

// ── 工具函数 ─────────────────────────────────────────────────────────────────
const addUserMsg = (text) => {
  messages.value.push({
    id: Date.now(),
    role: 'user',
    content: text,
    time: new Date().toLocaleTimeString('zh-CN'),
  })
}

const clearAll = () => {
  messages.value = []
  currentIteration.value = 0
  stats.value = { toolCalls: 0, totalSteps: 0 }
  activeTool.value = null
}

const scrollToBottom = async () => {
  await nextTick()
  if (msgListRef.value) {
    msgListRef.value.scrollTo({ top: msgListRef.value.scrollHeight, behavior: 'smooth' })
  }
}

const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : s

const stepIcon = (type) => {
  const map = { thinking: 'Lightning', tool_call: 'Cpu', tool_result: 'Check' }
  return map[type] || 'MoreFilled'
}
const stepLabel = (type) => {
  const map = { thinking: '思考', tool_call: '调用工具', tool_result: '工具返回' }
  return map[type] || type
}
const toolIcon = (name) => {
  const map = {
    read_file: 'Document', list_dir: 'FolderOpened', write_file: 'EditPen',
    search_kb: 'Search', web_search: 'Connection', analyze_dir: 'Folder',
    generate_legal_doc: 'Tickets',
  }
  return map[name] || 'Setting'
}
const toolColor = (name) => {
  const map = {
    read_file: '#60a5fa', list_dir: '#a78bfa', write_file: '#34d399',
    search_kb: '#fbbf24', web_search: '#4ade80', analyze_dir: '#f472b6',
    generate_legal_doc: '#fb923c',
  }
  return map[name] || '#94a3b8'
}

// 提取回答中的文件路径
const extractFilePaths = (text) => {
  if (!text) return []
  const matches = text.match(/[A-Za-z]:\\[^\s\n"'<>]+\.(docx|doc|pdf|txt|md)/g) || []
  return [...new Set(matches)]
}

const getFileName = (fp) => fp.split(/[/\\]/).pop()

const downloadFile = (fp) => {
  agentApi.downloadFile(fp)
}

// 简单 Markdown 渲染
const renderMarkdown = (text) => {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^#{1,3}\s+(.+)$/gm, (_, t) => `<div class="md-heading">${t}</div>`)
    .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped>
.agent-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: transparent;
}

/* ===== 顶部 ===== */
.agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: rgba(13,18,36,0.75);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 12px;
  flex-wrap: wrap;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-right { display: flex; align-items: center; gap: 10px; margin-left: auto; }

.header-icon {
  width: 28px; height: 28px; border-radius: 8px;
  background: rgba(139,92,246,0.15);
  border: 1px solid rgba(139,92,246,0.3);
  display: flex; align-items: center; justify-content: center;
  color: #a78bfa;
}
.agent-icon { background: rgba(139,92,246,0.2); }

.header-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.header-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 99px;
  background: rgba(139,92,246,0.12); color: #a78bfa;
  border: 1px solid rgba(139,92,246,0.25);
}
.iter-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 99px;
  background: rgba(251,191,36,0.1); color: #fbbf24;
  border: 1px solid rgba(251,191,36,0.2);
  animation: blink 1.5s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.5} }

/* 模式切换 */
.mode-tabs { display: flex; gap: 2px; background: rgba(255,255,255,0.04); border: 1px solid var(--border); border-radius: 8px; padding: 2px; }
.mode-tab {
  display: flex; align-items: center; gap: 4px;
  padding: 4px 10px; font-size: 11px; border-radius: 6px;
  border: none; background: transparent; color: var(--text-muted);
  cursor: pointer; transition: all 0.15s;
}
.mode-tab:hover { color: var(--text-secondary); background: rgba(255,255,255,0.06); }
.mode-tab.active { background: rgba(139,92,246,0.2); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3); }

.clear-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 10px; font-size: 11px; border-radius: 7px;
  border: 1px solid var(--border); background: transparent;
  color: var(--text-muted); cursor: pointer; transition: all 0.15s;
}
.clear-btn:hover { color: #f87171; border-color: rgba(248,113,113,0.4); }

/* ===== 主体 ===== */
.agent-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ===== 对话面板 ===== */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* ===== 欢迎页 ===== */
.agent-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}
.aw-icon-wrap {
  position: relative; width: 100px; height: 100px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 20px;
}
.aw-ring {
  position: absolute; border-radius: 50%;
  border: 1.5px solid rgba(139,92,246,0.35);
  animation: ripple 2.5s ease-out infinite;
}
.aw-ring.r1 { width: 80px; height: 80px; }
.aw-ring.r2 { width: 80px; height: 80px; animation-delay: 1.25s; }
@keyframes ripple { 0%{transform:scale(1);opacity:0.8} 100%{transform:scale(2);opacity:0} }
.aw-icon {
  width: 64px; height: 64px; border-radius: 16px;
  background: linear-gradient(135deg, rgba(109,40,217,0.5), rgba(139,92,246,0.3));
  border: 1px solid rgba(139,92,246,0.5);
  display: flex; align-items: center; justify-content: center;
  color: #a78bfa;
  box-shadow: 0 0 24px rgba(139,92,246,0.3);
  animation: floatY 4s ease-in-out infinite;
}
@keyframes floatY { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
.aw-title { font-size: 22px; font-weight: 700; color: var(--text-primary); margin-bottom: 8px; }
.aw-sub { font-size: 13px; color: var(--text-muted); margin-bottom: 28px; }

.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  max-width: 520px;
  width: 100%;
}
.cap-card {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition);
  text-align: left;
}
.cap-card:hover { background: var(--bg-card-hover); border-color: var(--border-glow); transform: translateY(-2px); box-shadow: var(--shadow-glow); }
.cap-info { flex: 1; min-width: 0; }
.cap-title { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.cap-desc { font-size: 11px; color: var(--text-muted); line-height: 1.5; }

/* ===== 消息列表 ===== */
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.msg-row { display: flex; align-items: flex-start; gap: 10px; max-width: 92%; }
.msg-row.user { align-self: flex-end; flex-direction: row; }
.msg-row.agent { align-self: flex-start; }
.spacer { flex: 1; }

.avatar {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 2px;
}
.user-av { background: linear-gradient(135deg, #1d4ed8, #3b82f6); color: #fff; }
.agent-av {
  background: rgba(139,92,246,0.12);
  border: 1px solid rgba(139,92,246,0.3);
  color: #a78bfa;
}
.agent-av.spinning {
  animation: spin 1.5s linear infinite;
  border-color: rgba(139,92,246,0.6);
}
@keyframes spin { to { transform: rotate(360deg); } }

.bubble { padding: 12px 16px; border-radius: var(--radius-md); font-size: 14px; line-height: 1.75; word-break: break-word; }
.user-bubble { background: var(--user-bubble); color: #fff; border-radius: var(--radius-md) 4px var(--radius-md) var(--radius-md); }
.agent-bubble { background: var(--bg-card); border: 1px solid var(--border); border-radius: 4px var(--radius-md) var(--radius-md) var(--radius-md); color: var(--text-primary); }
.agent-bubble.streaming { border-color: rgba(139,92,246,0.35); box-shadow: 0 0 12px rgba(139,92,246,0.1); }

.agent-content { display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 0; }

/* ===== 步骤时间线 ===== */
.steps-timeline {
  background: rgba(139,92,246,0.04);
  border: 1px solid rgba(139,92,246,0.15);
  border-radius: var(--radius-sm);
  overflow: hidden;
  font-size: 12px;
}
.timeline-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px;
  color: #a78bfa;
  border-bottom: 1px solid rgba(139,92,246,0.1);
  font-size: 11px;
}
.toggle-steps {
  margin-left: auto; font-size: 10px; color: var(--text-muted);
  background: none; border: none; cursor: pointer;
  padding: 0 4px;
}
.toggle-steps:hover { color: #a78bfa; }
.timeline-body { padding: 8px 12px; display: flex; flex-direction: column; gap: 8px; }
.step-item { display: flex; gap: 10px; align-items: flex-start; }
.step-dot {
  width: 18px; height: 18px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 1px;
}
.step-item.thinking .step-dot { background: rgba(251,191,36,0.15); color: #fbbf24; }
.step-item.tool_call .step-dot { background: rgba(139,92,246,0.15); color: #a78bfa; }
.step-item.tool_result .step-dot { background: rgba(52,211,153,0.15); color: #34d399; }
.step-content { flex: 1; min-width: 0; }
.step-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-right: 6px; }
.tool-name { font-size: 11px; font-weight: 600; color: #a78bfa; background: rgba(139,92,246,0.12); padding: 1px 6px; border-radius: 4px; }
.tool-args { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.tool-arg-chip { font-size: 10px; padding: 1px 7px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 4px; color: var(--text-secondary); }
.tool-result-preview { font-size: 11px; color: var(--text-muted); line-height: 1.5; white-space: pre-wrap; max-height: 80px; overflow-y: auto; }
.thinking-text { font-size: 11px; color: var(--text-muted); line-height: 1.5; }

/* ===== 答案内容 ===== */
.answer-text { white-space: pre-wrap; line-height: 1.8; }
.answer-text :deep(.md-heading) { font-size: 15px; font-weight: 600; color: var(--text-primary); margin: 8px 0 4px; }
.answer-text :deep(strong) { color: var(--text-primary); }
.answer-text :deep(code) { background: rgba(255,255,255,0.08); padding: 1px 5px; border-radius: 4px; font-family: monospace; font-size: 12px; }
.answer-text :deep(ul) { padding-left: 16px; }
.answer-text :deep(li) { margin: 3px 0; color: var(--text-secondary); }

.download-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); }
.download-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 12px; font-size: 12px; border-radius: 7px;
  background: rgba(52,211,153,0.1); border: 1px solid rgba(52,211,153,0.25);
  color: #34d399; cursor: pointer; transition: all 0.15s;
}
.download-btn:hover { background: rgba(52,211,153,0.2); }

/* ===== 加载气泡 ===== */
.loading-bubble { padding: 0 !important; overflow: hidden; min-width: 200px; }
.loading-scanner { width: 100%; height: 2px; background: rgba(139,92,246,0.1); position: relative; overflow: hidden; }
.scanner-bar {
  position: absolute; left: -40%; width: 40%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(139,92,246,0.8), transparent);
  animation: scannerMove 1.5s ease-in-out infinite;
}
@keyframes scannerMove { 0%{left:-40%} 100%{left:100%} }
.loading-content { display: flex; align-items: center; gap: 10px; padding: 12px 16px; }
.thinking-dots { display: flex; gap: 4px; }
.thinking-dots span { width: 6px; height: 6px; border-radius: 50%; background: #a78bfa; animation: bounce 1.2s infinite; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,80%,100%{transform:scale(0.7);opacity:0.4} 40%{transform:scale(1);opacity:1} }
.thinking-text-s { font-size: 12px; color: var(--text-muted); }

.msg-time { font-size: 10px; color: var(--text-muted); padding: 0 2px; }

/* ===== 输入区 ===== */
.input-area {
  padding: 14px 20px 18px;
  background: rgba(13,18,36,0.75);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

/* 文件上传区 */
.file-upload-zone {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 12px 16px; margin-bottom: 10px;
  border: 1.5px dashed var(--border); border-radius: var(--radius-md);
  background: rgba(255,255,255,0.02);
  font-size: 13px; color: var(--text-muted);
  transition: all 0.2s; cursor: default;
}
.file-upload-zone.dragging { border-color: #a78bfa; background: rgba(139,92,246,0.08); }
.upload-label {
  color: #a78bfa; cursor: pointer; text-decoration: underline;
  text-underline-offset: 2px;
}
.hint-text { font-size: 11px; color: var(--text-muted); opacity: 0.7; }
.file-name { font-weight: 500; color: var(--text-primary); }
.file-size { font-size: 11px; color: var(--text-muted); }
.remove-file {
  margin-left: auto; background: none; border: none;
  color: var(--text-muted); cursor: pointer; font-size: 13px;
}
.remove-file:hover { color: #f87171; }

/* 目录输入 */
.dir-input-zone { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.dir-input { flex: 1; }
.dir-input :deep(.el-input__inner) { font-size: 13px !important; }
.dir-analyze-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 8px 16px; border-radius: 8px; font-size: 13px;
  background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.3);
  color: #a78bfa; cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.dir-analyze-btn:hover:not(:disabled) { background: rgba(139,92,246,0.25); }
.dir-analyze-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* 文字输入 */
.input-wrap { display: flex; gap: 10px; align-items: flex-end; }
.agent-input :deep(.el-textarea__inner) {
  border-radius: var(--radius-md) !important;
  padding: 12px 16px !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
}
.send-btn {
  width: 44px; height: 44px; border-radius: 12px;
  border: 1px solid var(--border); background: rgba(255,255,255,0.04);
  color: var(--text-muted); cursor: not-allowed;
  display: flex; align-items: center; justify-content: center;
  transition: var(--transition); flex-shrink: 0; outline: none;
}
.send-btn.active { background: #7c3aed; border-color: #7c3aed; color: #fff; cursor: pointer; box-shadow: 0 0 16px rgba(139,92,246,0.4); }
.send-btn.active:hover { background: #a78bfa; transform: scale(1.05); }
.rotating { animation: spin 1s linear infinite; }
.input-hint { margin-top: 6px; font-size: 11px; color: var(--text-muted); text-align: center; }

/* ===== 工具面板 ===== */
.tools-panel {
  width: 240px;
  flex-shrink: 0;
  border-left: 1px solid var(--border);
  background: rgba(13,18,36,0.5);
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s;
}
.tools-panel.collapsed { width: 40px; }
.tools-panel-header {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  font-size: 12px; color: var(--text-secondary);
  flex-shrink: 0;
}
.tools-panel-header:hover { background: rgba(255,255,255,0.04); }
.collapse-arrow { margin-left: auto; transition: transform 0.2s; color: var(--text-muted); }
.collapse-arrow.open { transform: rotate(90deg); }
.tools-list { flex: 1; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 6px; }
.tool-card {
  padding: 10px 12px; border-radius: 8px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border);
  transition: all 0.15s;
}
.tool-card.active { border-color: rgba(139,92,246,0.4); background: rgba(139,92,246,0.06); }
.tool-header { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
.tool-name { font-size: 12px; font-weight: 500; color: var(--text-secondary); font-family: monospace; }
.tool-desc { font-size: 11px; color: var(--text-muted); line-height: 1.5; }

/* 统计 */
.run-stats { padding: 12px 14px; border-top: 1px solid var(--border); flex-shrink: 0; }
.stats-title { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-bottom: 10px; }
.stats-row { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.stats-val { color: #a78bfa; font-weight: 600; }

/* ===== 动画 ===== */
.welcome-fade-enter-active { transition: opacity 0.5s, transform 0.5s cubic-bezier(0.34,1.56,0.64,1); }
.welcome-fade-enter-from { opacity: 0; transform: translateY(20px) scale(0.98); }
.slide-down-enter-active { transition: all 0.25s ease; }
.slide-down-enter-from { opacity: 0; transform: translateY(-6px); }
.slide-down-leave-active { transition: all 0.2s ease; }
.slide-down-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
