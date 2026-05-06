<template>
  <span class="typewriter">
    <span v-html="displayedHtml"></span>
    <span v-if="typing" class="cursor">|</span>
  </span>
</template>

<script setup>
import { ref, watch, computed, onUnmounted } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  text:      { type: String,  default: '' },
  speed:     { type: Number,  default: 18 },
  active:    { type: Boolean, default: true },
  // streaming=true 时跳过打字机，直接渲染（SSE 已经是逐字流，不需要再动效）
  streaming: { type: Boolean, default: false },
})

const emit = defineEmits(['done'])

const displayedText = ref('')
const displayedHtml = ref('')
const typing = ref(false)
let timer = null
let lastLen = 0   // 记录上次处理到的字符位置，增量追加

const renderHtml = (t) => {
  try { return marked.parse(t) } catch { return t }
}

// ── 流式模式：text prop 每次追加新内容，直接累加渲染，不重置 ──
const handleStreamingUpdate = (text) => {
  if (text.length <= lastLen) return
  lastLen = text.length
  displayedText.value = text
  displayedHtml.value = renderHtml(text)
  typing.value = true   // 保持光标显示
}

// ── 非流式模式：完整文本一次性触发打字机 ──
const startTyping = (text) => {
  if (timer) clearInterval(timer)
  displayedText.value = ''
  displayedHtml.value = ''
  lastLen = 0
  let idx = 0
  typing.value = true

  if (!props.active || !text) {
    displayedText.value = text
    displayedHtml.value = renderHtml(text)
    typing.value = false
    emit('done')
    return
  }

  timer = setInterval(() => {
    if (idx < text.length) {
      const batch = Math.min(3, text.length - idx)
      displayedText.value += text.slice(idx, idx + batch)
      displayedHtml.value = renderHtml(displayedText.value)
      idx += batch
    } else {
      clearInterval(timer)
      typing.value = false
      emit('done')
    }
  }, props.speed)
}

watch(
  () => props.text,
  (val) => {
    if (props.streaming) {
      handleStreamingUpdate(val)
    } else {
      if (val) startTyping(val)
    }
  },
  { immediate: true }
)

// streaming 结束时（false→true→false）关闭光标
watch(
  () => props.streaming,
  (val) => {
    if (!val) {
      typing.value = false
      lastLen = 0
    }
  }
)

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.typewriter {
  display: inline;
  line-height: 1.8;
}

.cursor {
  display: inline-block;
  color: var(--accent-light);
  animation: blink 0.8s step-end infinite;
  font-weight: 300;
  margin-left: 1px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
</style>
