<template>
  <div class="chat-view">
    <!-- 顶部 -->
    <div class="chat-header">
      <div class="header-left">
        <div class="header-icon">
          <el-icon size="16"><ChatDotRound /></el-icon>
        </div>
        <span class="header-title">法律咨询问答</span>
        <span class="header-badge">AI Powered</span>
      </div>
      <el-button size="small" @click="store.clearMessages()" :icon="Delete" text style="color: var(--text-muted)">
        清空对话
      </el-button>
    </div>

    <!-- 消息区域 -->
    <div class="message-list" ref="messageListRef">
      <!-- 欢迎屏 -->
      <transition name="welcome-fade">
        <div v-if="store.messages.length === 0" class="welcome">
          <div class="welcome-glow"></div>
          <div class="welcome-glow welcome-glow-2"></div>

          <!-- 核心图标区 -->
          <div class="welcome-icon-wrap">
            <!-- 外轨道旋转环 -->
            <div class="orbit-ring orbit-outer"></div>
            <div class="orbit-ring orbit-inner"></div>
            <!-- 脉冲扩散圈 -->
            <div class="ripple-ring r1"></div>
            <div class="ripple-ring r2"></div>
            <!-- 主图标 -->
            <div class="welcome-icon">
              <el-icon size="52"><ScaleToOriginal /></el-icon>
            </div>
          </div>

          <h1 class="welcome-title">法律咨询智能问答</h1>
          <p class="welcome-sub">基于 DeepSeek-R1 + RAG 混合检索，为您提供专业法律解答</p>

          <!-- 技术标签条 -->
          <div class="tech-tags">
            <span class="tech-tag">RAG 混合检索</span>
            <span class="tech-tag">知识图谱</span>
            <span class="tech-tag">BM25 + 向量</span>
            <span class="tech-tag">流式推理</span>
          </div>

          <div class="quick-grid">
            <div
              v-for="(q, qi) in quickQuestions"
              :key="q.text"
              class="quick-card"
              :style="{ animationDelay: qi * 0.08 + 's' }"
              @click="handleSend(q.text)"
            >
              <el-icon class="quick-icon"><component :is="q.icon" /></el-icon>
              <span>{{ q.text }}</span>
            </div>
          </div>
        </div>
      </transition>

      <!-- 消息列表 -->
      <div
        v-for="(msg, idx) in store.messages"
        :key="msg.id"
        class="msg-row"
        :class="msg.role"
      >
        <!-- 用户消息 -->
        <template v-if="msg.role === 'user'">
          <div class="spacer"></div>
          <div class="bubble user-bubble">
            <span>{{ msg.content }}</span>
          </div>
          <div class="avatar user-avatar">
            <el-icon size="16"><User /></el-icon>
          </div>
        </template>

        <!-- AI消息 -->
        <template v-else>
          <div class="avatar ai-avatar">
            <el-icon size="16"><ScaleToOriginal /></el-icon>
          </div>
          <div class="ai-content">
            <!-- 思维链 -->
            <transition name="fade-in">
              <div v-if="msg.thinking" class="thinking-box" :class="{ streaming: msg.streaming }">
                <div class="thinking-header" @click="toggleThinking(msg.id)">
                  <el-icon size="12"><Lightning /></el-icon>
                  <span>{{ msg.streaming ? '推理中...' : '推理过程' }}</span>
                  <span class="thinking-chars">{{ msg.thinking.length }} 字</span>
                  <el-icon size="10" class="arrow" :class="{ open: isThinkingOpen(msg) }">
                    <ArrowRight />
                  </el-icon>
                </div>
                <transition name="slide-down">
                  <div v-if="isThinkingOpen(msg)" class="thinking-body" :ref="el => setThinkingRef(msg.id, el)">{{ msg.thinking }}</div>
                </transition>
              </div>
            </transition>

            <!-- 回答气泡 -->
            <div class="bubble ai-bubble" :class="{ streaming: msg.streaming }">
              <TypeWriter
                :text="msg.content"
                :active="isLatestAI(idx)"
                :streaming="!!msg.streaming"
                :speed="15"
              />
            </div>

            <!-- 查询增强 + 记忆状态 + 联网标记 -->
            <div v-if="msg.enhanceMode || msg.memoryInfo?.has_summary || msg.webSearchTriggered" class="meta-tags">
              <span v-if="msg.enhanceMode === 'hyde'" class="meta-tag tag-hyde">
                <el-icon size="10"><MagicStick /></el-icon> HyDE
              </span>
              <span v-else-if="msg.enhanceMode === 'multi_query'" class="meta-tag tag-mq">
                <el-icon size="10"><Search /></el-icon> Multi-Query
              </span>
              <span v-if="msg.memoryInfo?.has_summary" class="meta-tag tag-mem">
                <el-icon size="10"><ChatLineRound /></el-icon> 历史摘要 {{ msg.memoryInfo.total_turns }} 轮
              </span>
              <span v-if="msg.webSearchTriggered" class="meta-tag tag-web">
                <el-icon size="10"><Connection /></el-icon> 联网补充 {{ msg.webDocsCount }} 条
              </span>
            </div>

            <!-- 引用来源 -->
            <div v-if="msg.sources?.length" class="sources-box">
              <div class="sources-header">
                <el-icon size="12"><Document /></el-icon>
                <span>引用条文 {{ msg.sources.length }} 条</span>
              </div>
              <div class="sources-list">
                <div
                  v-for="(src, i) in msg.sources"
                  :key="i"
                  class="source-chip"
                  :class="{ 'chip-kg': src.from_kg, 'chip-web': src.from_web }"
                  @click="src.from_web && src.url ? window.open(src.url, '_blank') : toggleSource(msg.id, i)"
                >
                  <span v-if="src.from_kg" class="chip-kg-badge">图谱</span>
                  <span v-else-if="src.from_web" class="chip-web-badge">联网</span>
                  <span class="chip-name">{{ src.source }}</span>
                  <span class="chip-score">{{ (src.score * 100).toFixed(0) }}%</span>
                </div>
              </div>
              <transition name="slide-down">
                <div v-if="expandedSource && expandedSource.msgId === msg.id" class="source-detail">
                  {{ getExpandedSource(msg) }}
                </div>
              </transition>
            </div>

            <div class="msg-time">{{ msg.time }}</div>
          </div>
        </template>
      </div>

      <!-- 加载动画：仅在还没收到任何流式内容时显示 -->
      <div v-if="store.loading && !hasStreamingContent" class="msg-row assistant">
        <div class="avatar ai-avatar ai-avatar-loading">
          <el-icon size="16"><ScaleToOriginal /></el-icon>
        </div>
        <div class="bubble ai-bubble loading-bubble">
          <div class="loading-scanner">
            <div class="scanner-bar"></div>
          </div>
          <div class="loading-content">
            <div class="thinking-dots">
              <span></span><span></span><span></span>
            </div>
            <span class="thinking-text">正在检索法律条文并推理...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <!-- 设置工具栏 -->
      <div class="settings-bar">
        <!-- 查询增强模式 -->
        <div class="setting-group">
          <span class="setting-label">增强检索</span>
          <div class="seg-ctrl">
            <button
              v-for="opt in enhanceModeOptions"
              :key="opt.value"
              class="seg-btn"
              :class="{ active: store.enhanceMode === opt.value }"
              :title="opt.tip"
              @click="store.enhanceMode = opt.value"
            >
              <el-icon size="11" style="vertical-align: -1px"><component :is="opt.icon" /></el-icon>
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div class="setting-divider"></div>

        <!-- 知识图谱开关 -->
        <div class="setting-group">
          <span class="setting-label">知识图谱</span>
          <button
            class="toggle-btn"
            :class="{ on: store.enableKg }"
            :title="store.enableKg ? '点击关闭知识图谱扩展' : '点击开启知识图谱扩展'"
            @click="store.enableKg = !store.enableKg"
          >
            <span class="toggle-dot"></span>
          </button>
        </div>

        <div class="setting-divider"></div>

        <!-- Reranker 开关 -->
        <div class="setting-group">
          <span class="setting-label">重排序</span>
          <button
            class="toggle-btn reranker-toggle"
            :class="{ on: store.enableRerank, loading: rerankerLoading }"
            :title="rerankerLoading ? '正在切换...' : (store.enableRerank ? '点击关闭 Reranker（释放内存）' : '点击开启 Reranker（提升检索精度）')"
            :disabled="rerankerLoading"
            @click="toggleReranker"
          >
            <span class="toggle-dot"></span>
          </button>
          <span v-if="rerankerLoading" class="reranker-hint" style="color: var(--text-muted); font-size: 10px;">
            {{ store.enableRerank ? '释放中...' : '加载中...' }}
          </span>
        </div>

        <div class="setting-divider"></div>

        <!-- Top-K 调节 -->
        <div class="setting-group">
          <span class="setting-label">引用条数</span>
          <div class="topk-ctrl">
            <button class="topk-btn" :disabled="store.topK <= 1" @click="store.topK = Math.max(1, store.topK - 1)">−</button>
            <span class="topk-val">{{ store.topK }}</span>
            <button class="topk-btn" :disabled="store.topK >= 10" @click="store.topK = Math.min(10, store.topK + 1)">+</button>
          </div>
        </div>

        <div class="setting-divider"></div>

        <!-- 联网检索开关 -->
        <div class="setting-group">
          <span class="setting-label">联网检索</span>
          <div class="seg-ctrl">
            <button
              class="seg-btn"
              :class="{ active: store.enableWebSearch === true }"
              title="强制开启联网检索（每次都联网）"
              @click="store.enableWebSearch = store.enableWebSearch === true ? null : true"
            >
              <el-icon size="11" style="vertical-align:-1px"><Connection /></el-icon>
              开
            </button>
            <button
              class="seg-btn"
              :class="{ active: store.enableWebSearch === null }"
              title="自动判断（知识库置信度不足时自动联网）"
              @click="store.enableWebSearch = null"
            >
              自动
            </button>
            <button
              class="seg-btn"
              :class="{ active: store.enableWebSearch === false }"
              title="强制关闭联网检索"
              @click="store.enableWebSearch = store.enableWebSearch === false ? null : false"
            >
              <el-icon size="11" style="vertical-align:-1px"><Minus /></el-icon>
              关
            </button>
          </div>
        </div>

        <div class="setting-divider"></div>

        <!-- 模型选择入口 -->
        <button class="model-entry-btn" @click="modelDrawerRef.open()" :title="'当前模型: ' + store.modelLabel">
          <el-icon size="11"><Cpu /></el-icon>
          <span class="model-entry-label">{{ store.modelLabel }}</span>
          <span v-if="store.llmProvider === 'remote'" class="provider-badge remote">远程</span>
          <span v-else class="provider-badge local">本地</span>
        </button>
      </div>

      <div class="input-wrap">
        <el-input
          v-model="inputText"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          placeholder="输入您的法律问题，按 Enter 发送..."
          @keydown.enter.exact.prevent="handleSend()"
          @keydown.shift.enter.prevent="inputText += '\n'"
          class="chat-input"
        />
        <button
          v-if="store.loading"
          class="send-btn active stop-btn"
          title="停止输出"
          @click="store.abortChat()"
        >
          <el-icon size="18"><Close /></el-icon>
        </button>
        <button
          v-else
          class="send-btn"
          :class="{ active: inputText.trim() }"
          :disabled="!inputText.trim() || store.loading"
          @click="handleSend()"
        >
          <el-icon v-if="!store.loading" size="18"><Promotion /></el-icon>
          <el-icon v-else class="rotating" size="18"><Loading /></el-icon>
        </button>
      </div>
      <div class="input-hint">Enter 发送 · Shift+Enter 换行 · 仅供参考，请咨询专业律师</div>
    </div>

    <!-- 模型配置抽屉 -->
    <ModelDrawer ref="modelDrawerRef" />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { Delete, Promotion, Loading, Document, ArrowRight, MagicStick, Search, ChatLineRound, Minus, Cpu, Connection, Close } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { systemApi } from '@/api'
import TypeWriter from '@/components/TypeWriter.vue'
import ModelDrawer from '@/components/ModelDrawer.vue'

// 动态导入图标
import { QuestionFilled, Coin, House, ShoppingCart } from '@element-plus/icons-vue'

const store = useChatStore()
const inputText = ref('')
const messageListRef = ref(null)
const openThinking = ref({})   // 手动折叠标记（true=用户主动折叠）
const thinkingRefs = ref({})   // thinking-body DOM 引用，用于自动滚动
const expandedSource = ref(null)
const modelDrawerRef = ref(null)

// streaming 时默认展开，用户点击后折叠/展开
const isThinkingOpen = (msg) => {
  if (msg.streaming) return true          // 推理中强制展开
  return !openThinking.value[msg.id]      // 完成后默认展开，点过才折叠
}

const toggleThinking = (id) => {
  const msg = store.messages.find(m => m.id === id)
  if (msg?.streaming) return              // 推理中不允许折叠
  openThinking.value[id] = !openThinking.value[id]
}

const setThinkingRef = (id, el) => {
  thinkingRefs.value[id] = el
}

// thinking 内容更新时自动滚到底部
watch(
  () => store.messages.map(m => m.thinking),
  () => {
    nextTick(() => {
      const lastMsg = store.messages[store.messages.length - 1]
      if (lastMsg?.streaming && lastMsg.thinking) {
        const el = thinkingRefs.value[lastMsg.id]
        if (el) el.scrollTop = el.scrollHeight
      }
    })
  }
)

// 增强模式选项
const enhanceModeOptions = [
  { value: 'hyde',        label: 'HyDE',        icon: MagicStick, tip: '生成假设答案后做向量检索，专业术语召回更准' },
  { value: 'multi_query', label: '多路',          icon: Search,    tip: '扩写3个子查询并行检索，覆盖面更广' },
  { value: 'off',         label: '关闭',          icon: Minus,     tip: '不做查询增强，直接检索' },
]

const quickQuestions = [
  { text: '劳动合同到期不续签有补偿吗？', icon: QuestionFilled },
  { text: '被公司无故辞退怎么办？', icon: Coin },
  { text: '离婚财产如何分割？', icon: House },
  { text: '网购收到假货如何维权？', icon: ShoppingCart },
]

const isLatestAI = (idx) => {
  const msgs = store.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return i === idx
  }
  return false
}

// 最后一条 AI 消息已有内容则不再显示骨架 loading
const hasStreamingContent = computed(() => {
  const last = store.messages[store.messages.length - 1]
  return last && last.role === 'assistant' && last.content.length > 0
})

// ── Reranker 动态开关 ─────────────────────────────────────────────────────────
const rerankerLoading = ref(false)

const toggleReranker = async () => {
  if (rerankerLoading.value) return
  rerankerLoading.value = true
  try {
    const target = !store.enableRerank
    const res = await systemApi.rerankerToggle(target)
    if (res.success) {
      store.enableRerank = target
    }
  } catch {
    // 网络错误等，静默忽略
  } finally {
    rerankerLoading.value = false
  }
}

const handleSend = (text) => {
  const q = (text || inputText.value).trim()
  if (!q || store.loading) return
  inputText.value = ''
  store.sendQuestion(q)
}



const toggleSource = (msgId, index) => {
  if (expandedSource.value && expandedSource.value.msgId === msgId && expandedSource.value.index === index) {
    expandedSource.value = null
  } else {
    expandedSource.value = { msgId, index }
  }
}

const getExpandedSource = (msg) => {
  if (!expandedSource.value || expandedSource.value.msgId !== msg.id) return ''
  return msg.sources?.[expandedSource.value.index]?.content || ''
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTo({ top: messageListRef.value.scrollHeight, behavior: 'smooth' })
  }
}

watch(() => store.messages.length, scrollToBottom)

// 流式输出时跟随滚动
watch(
  () => store.messages[store.messages.length - 1]?.content,
  scrollToBottom
)
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: transparent;
}

/* ===== 顶部 ===== */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: rgba(13, 18, 36, 0.7);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(59,130,246,0.15);
  border: 1px solid rgba(59,130,246,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-light);
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 99px;
  background: rgba(59,130,246,0.12);
  color: var(--accent-light);
  border: 1px solid rgba(59,130,246,0.25);
  letter-spacing: 0.5px;
}

/* ===== 消息列表 ===== */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ===== 消息行 ===== */
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 88%;
}

.msg-row.user { align-self: flex-end; flex-direction: row; }
.msg-row.assistant { align-self: flex-start; }
.spacer { flex: 1; }

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.user-avatar {
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  color: #fff;
  box-shadow: 0 0 10px var(--accent-glow);
}

.ai-avatar {
  background: rgba(59,130,246,0.1);
  border: 1px solid rgba(59,130,246,0.25);
  color: var(--accent-light);
}

/* ===== 气泡 ===== */
.bubble {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  line-height: 1.75;
  word-break: break-word;
  font-size: 14px;
}

.user-bubble {
  background: var(--user-bubble);
  color: #fff;
  border-radius: var(--radius-md) 4px var(--radius-md) var(--radius-md);
  box-shadow: 0 4px 16px rgba(59,130,246,0.3);
}

.ai-bubble {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 4px var(--radius-md) var(--radius-md) var(--radius-md);
  box-shadow: var(--shadow-card);
}

.ai-bubble.streaming {
  border-color: rgba(59,130,246,0.3);
  box-shadow: 0 0 12px rgba(59,130,246,0.1);
}

/* ===== AI内容区 ===== */
.ai-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

/* ===== 思维链 ===== */
.thinking-box {
  background: rgba(59,130,246,0.04);
  border: 1px solid rgba(59,130,246,0.15);
  border-radius: var(--radius-sm);
  overflow: hidden;
  font-size: 12px;
  margin-bottom: 6px;
}

.thinking-box.streaming {
  border-color: rgba(59,130,246,0.35);
  animation: thinking-pulse 2s ease-in-out infinite;
}

@keyframes thinking-pulse {
  0%, 100% { border-color: rgba(59,130,246,0.25); }
  50%       { border-color: rgba(59,130,246,0.55); }
}

.thinking-chars {
  margin-left: auto;
  margin-right: 4px;
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.7;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  color: var(--accent-light);
  user-select: none;
}

.thinking-header:hover { background: rgba(59,130,246,0.06); }

.arrow {
  margin-left: auto;
  transition: transform 0.2s;
  color: var(--text-muted);
}
.arrow.open { transform: rotate(90deg); }

.thinking-body {
  padding: 10px 12px;
  color: var(--text-muted);
  white-space: pre-wrap;
  line-height: 1.6;
  border-top: 1px solid rgba(59,130,246,0.1);
  max-height: 260px;
  overflow-y: auto;
  scroll-behavior: smooth;
  max-height: 180px;
  overflow-y: auto;
}

/* ===== 引用来源 ===== */
.sources-box {
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  font-size: 12px;
}

.sources-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sources-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.source-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(59,130,246,0.08);
  border: 1px solid rgba(59,130,246,0.2);
  border-radius: 99px;
  cursor: pointer;
  transition: var(--transition);
}

.source-chip:hover {
  background: rgba(59,130,246,0.15);
  border-color: var(--accent);
}

.chip-name {
  color: var(--text-secondary);
  font-size: 11px;
}

.chip-score {
  color: var(--accent-light);
  font-size: 10px;
  font-weight: 600;
}

.source-detail {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(0,0,0,0.2);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 12px;
}

/* 知识图谱来源 chip */
.chip-kg {
  background: rgba(139,92,246,0.1);
  border-color: rgba(139,92,246,0.25);
}
.chip-kg:hover {
  background: rgba(139,92,246,0.2);
  border-color: rgba(139,92,246,0.5);
}
.chip-kg-badge {
  font-size: 9px;
  font-weight: 700;
  color: #a78bfa;
  background: rgba(139,92,246,0.15);
  padding: 1px 5px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* 联网来源 chip */
.chip-web {
  background: rgba(34,197,94,0.08);
  border-color: rgba(34,197,94,0.2);
}
.chip-web:hover {
  background: rgba(34,197,94,0.16);
  border-color: rgba(34,197,94,0.4);
}
.chip-web-badge {
  font-size: 9px;
  font-weight: 700;
  color: #4ade80;
  background: rgba(34,197,94,0.12);
  padding: 1px 5px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* meta-tags 标记条 */
.meta-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;
}

.meta-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 5px;
  font-weight: 500;
  letter-spacing: 0.2px;
}

.tag-hyde {
  background: rgba(139,92,246,0.12);
  color: #a78bfa;
}
.tag-mq {
  background: rgba(59,130,246,0.12);
  color: var(--accent-light);
}
.tag-mem {
  background: rgba(234,179,8,0.1);
  color: #fbbf24;
}
.tag-web {
  background: rgba(34,197,94,0.1);
  color: #4ade80;
}

.msg-time {
  font-size: 10px;
  color: var(--text-muted);
  padding: 0 2px;
}

/* ===== 输入区 ===== */
.input-area {
  padding: 16px 20px 20px;
  background: rgba(13,18,36,0.7);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.input-wrap {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input-wrap :deep(.el-textarea__inner) {
  border-radius: var(--radius-md) !important;
  padding: 12px 16px !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text-muted);
  cursor: not-allowed;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
  flex-shrink: 0;
  outline: none;
}

.send-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 0 16px var(--accent-glow);
}

.send-btn.active:hover {
  background: var(--accent-light);
  transform: scale(1.05);
}

.stop-btn {
  background: rgba(239, 68, 68, 0.2) !important;
  border-color: rgba(239, 68, 68, 0.5) !important;
  color: #fca5a5 !important;
  cursor: pointer !important;
}

.stop-btn:hover {
  background: rgba(239, 68, 68, 0.35) !important;
  transform: scale(1.05);
}

.rotating {
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.input-hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
  letter-spacing: 0.3px;
}

/* 模型选择入口按钮 */
.model-entry-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px 3px 7px;
  border-radius: 7px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
  max-width: 180px;
  overflow: hidden;
  margin-left: auto;
}
.model-entry-btn:hover {
  background: rgba(255,255,255,0.08);
  border-color: rgba(59,130,246,0.35);
  color: var(--text-primary);
}

.model-entry-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}

.provider-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
  flex-shrink: 0;
}
.provider-badge.local {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
}
.provider-badge.remote {
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
}

/* ===== 设置工具栏 ===== */
.settings-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px 6px;
  background: rgba(13, 18, 36, 0.5);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}

.setting-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.setting-label {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  letter-spacing: 0.3px;
}

.setting-divider {
  width: 1px;
  height: 16px;
  background: var(--border);
  margin: 0 2px;
}

/* 分段控制器 */
.seg-ctrl {
  display: flex;
  gap: 2px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  border-radius: 7px;
  padding: 2px;
}

.seg-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px 9px;
  font-size: 11px;
  border-radius: 5px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}

.seg-btn:hover {
  color: var(--text-secondary);
  background: rgba(255,255,255,0.06);
}

.seg-btn.active {
  background: rgba(59,130,246,0.2);
  color: var(--accent-light);
  border: 1px solid rgba(59,130,246,0.3);
}

/* 知识图谱开关 */
.toggle-btn {
  width: 34px;
  height: 18px;
  border-radius: 99px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.05);
  cursor: pointer;
  position: relative;
  transition: background 0.2s, border-color 0.2s;
  flex-shrink: 0;
}

.toggle-btn.on {
  background: rgba(59,130,246,0.3);
  border-color: rgba(59,130,246,0.5);
}

.toggle-dot {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: transform 0.2s, background 0.2s;
}

.toggle-btn.on .toggle-dot {
  transform: translateX(16px);
  background: var(--accent-light);
}

.toggle-btn.loading {
  opacity: 0.6;
  cursor: wait;
}

.reranker-hint {
  white-space: nowrap;
}

/* Top-K 调节 */
.topk-ctrl {
  display: flex;
  align-items: center;
  gap: 0;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  border-radius: 7px;
  overflow: hidden;
}

.topk-btn {
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  line-height: 1;
}

.topk-btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.08);
  color: var(--text-primary);
}

.topk-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.topk-val {
  min-width: 18px;
  text-align: center;
  font-size: 12px;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

/* ===== 查询增强 & 记忆标记 ===== */
.meta-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 2px;
}

.meta-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 99px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.tag-hyde {
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
  border: 1px solid rgba(139, 92, 246, 0.25);
}

.tag-mq {
  background: rgba(34, 197, 94, 0.1);
  color: #4ade80;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.tag-mem {
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.2);
}

/* 知识图谱来源 chip */
.source-chip.chip-kg {
  background: rgba(139, 92, 246, 0.1);
  border-color: rgba(139, 92, 246, 0.3);
}

.chip-kg-badge {
  font-size: 9px;
  font-weight: 700;
  color: #a78bfa;
  background: rgba(139, 92, 246, 0.15);
  padding: 1px 4px;
  border-radius: 4px;
  letter-spacing: 0.3px;
}

/* ===== 欢迎页升级 ===== */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px 20px;
  position: relative;
  text-align: center;
}

.welcome-glow {
  position: absolute;
  width: 500px;
  height: 500px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(59,130,246,0.07) 0%, transparent 70%);
  pointer-events: none;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
.welcome-glow-2 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%);
  animation: orbitRing 12s linear infinite;
}

/* 图标容器 */
.welcome-icon-wrap {
  position: relative;
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

/* 旋转轨道环 */
.orbit-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid transparent;
}
.orbit-outer {
  width: 110px;
  height: 110px;
  border-top-color: rgba(59,130,246,0.5);
  border-right-color: rgba(59,130,246,0.15);
  border-bottom-color: rgba(59,130,246,0.05);
  border-left-color: rgba(59,130,246,0.15);
  animation: orbitRing 3s linear infinite;
}
.orbit-inner {
  width: 90px;
  height: 90px;
  border-top-color: rgba(139,92,246,0.4);
  border-right-color: rgba(139,92,246,0.1);
  border-bottom-color: transparent;
  border-left-color: rgba(139,92,246,0.1);
  animation: orbitRing 2s linear infinite reverse;
}

/* 脉冲扩散圈 */
.ripple-ring {
  position: absolute;
  border-radius: 50%;
  border: 1.5px solid rgba(59,130,246,0.4);
  width: 72px;
  height: 72px;
  animation: ripple 2.5s ease-out infinite;
}
.r2 { animation-delay: 1.25s; }

/* 主图标 */
.welcome-icon {
  width: 72px;
  height: 72px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(29,78,216,0.6), rgba(59,130,246,0.35));
  border: 1px solid rgba(59,130,246,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-light);
  box-shadow: 0 0 30px var(--accent-glow), inset 0 1px 0 rgba(255,255,255,0.1);
  animation: borderGlow 3s ease-in-out infinite, floatY 4s ease-in-out infinite;
  position: relative;
  z-index: 1;
}

.welcome-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
  background: linear-gradient(135deg, #e2e8f0 20%, #93c5fd 60%, #a78bfa 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: holographic 5s linear infinite;
}

.welcome-sub {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
  line-height: 1.6;
}

/* 技术标签 */
.tech-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  margin-bottom: 28px;
}
.tech-tag {
  font-size: 10px;
  padding: 3px 10px;
  border-radius: 99px;
  border: 1px solid rgba(59,130,246,0.25);
  background: rgba(59,130,246,0.08);
  color: var(--accent-light);
  letter-spacing: 0.5px;
  animation: blink 3s ease-in-out infinite;
}
.tech-tag:nth-child(2) { animation-delay: 0.5s; border-color: rgba(139,92,246,0.25); background: rgba(139,92,246,0.08); color: #a78bfa; }
.tech-tag:nth-child(3) { animation-delay: 1s; border-color: rgba(59,200,246,0.25); background: rgba(59,200,246,0.08); color: #67e8f9; }
.tech-tag:nth-child(4) { animation-delay: 1.5s; border-color: rgba(16,185,129,0.25); background: rgba(16,185,129,0.08); color: #34d399; }

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  max-width: 480px;
  width: 100%;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition);
  text-align: left;
  font-size: 12px;
  color: var(--text-secondary);
  animation: bounceIn 0.5s ease both;
  position: relative;
  overflow: hidden;
}

/* 快捷卡悬停扫光 */
.quick-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent 20%, rgba(59,130,246,0.08) 50%, transparent 80%);
  background-size: 200% 100%;
  opacity: 0;
  transition: opacity 0.2s;
}
.quick-card:hover::after {
  opacity: 1;
  animation: shimmer 1s linear;
}

.quick-card:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-glow);
  color: var(--text-primary);
  transform: translateY(-3px);
  box-shadow: var(--shadow-glow);
}

.quick-icon {
  color: var(--accent-light);
  flex-shrink: 0;
}

/* ===== 加载气泡升级 ===== */
.loading-bubble {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 !important;
  overflow: hidden;
  min-width: 220px;
}

.loading-scanner {
  width: 100%;
  height: 2px;
  background: rgba(59,130,246,0.1);
  position: relative;
  overflow: hidden;
}
.scanner-bar {
  position: absolute;
  left: -40%;
  width: 40%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(59,130,246,0.8), transparent);
  animation: scannerMove 1.5s ease-in-out infinite;
}
@keyframes scannerMove {
  0%   { left: -40%; }
  100% { left: 100%; }
}

.loading-content {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: bounce 1.2s infinite;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
  40%           { transform: scale(1); opacity: 1; }
}

.thinking-text {
  font-size: 12px;
  color: var(--text-muted);
}

/* AI 头像加载态发光 */
.ai-avatar-loading {
  animation: borderGlow 1.5s ease-in-out infinite;
  border-color: rgba(59,130,246,0.5) !important;
}

/* ===== 动画 ===== */
.welcome-fade-enter-active { transition: opacity 0.6s, transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
.welcome-fade-enter-from   { opacity: 0; transform: translateY(24px) scale(0.97); }

.fade-in-enter-active { transition: opacity 0.3s; }
.fade-in-enter-from   { opacity: 0; }

.slide-down-enter-active { transition: all 0.25s ease; }
.slide-down-enter-from   { opacity: 0; transform: translateY(-6px); }
.slide-down-leave-active { transition: all 0.2s ease; }
.slide-down-leave-to     { opacity: 0; transform: translateY(-6px); }
</style>
