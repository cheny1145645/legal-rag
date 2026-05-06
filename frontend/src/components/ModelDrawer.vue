<template>
  <!-- 触发按钮（由父组件插槽或直接调用 open() 控制） -->
  <teleport to="body">
    <!-- 遮罩 -->
    <transition name="mask-fade">
      <div v-if="visible" class="drawer-mask" @click="close"></div>
    </transition>

    <!-- 抽屉面板 -->
    <transition name="drawer-slide">
      <div v-if="visible" class="model-drawer">
        <!-- 头部 -->
        <div class="drawer-header">
          <div class="drawer-title">
            <el-icon size="15"><Cpu /></el-icon>
            <span>模型配置</span>
          </div>
          <button class="drawer-close" @click="close">
            <el-icon size="14"><Close /></el-icon>
          </button>
        </div>

        <!-- 内容 -->
        <div class="drawer-body">
          <!-- Provider 切换 -->
          <div class="section">
            <div class="section-label">推理模式</div>
            <div class="provider-tabs">
              <button
                class="provider-tab"
                :class="{ active: store.llmProvider === 'ollama' }"
                @click="store.llmProvider = 'ollama'"
              >
                <el-icon size="13"><Monitor /></el-icon>
                本地 Ollama
              </button>
              <button
                class="provider-tab"
                :class="{ active: store.llmProvider === 'remote' }"
                @click="store.llmProvider = 'remote'"
              >
                <el-icon size="13"><Connection /></el-icon>
                远程 API
              </button>
            </div>
          </div>

          <!-- ── Ollama 本地配置 ── -->
          <template v-if="store.llmProvider === 'ollama'">
            <div class="section">
              <div class="section-label">
                已安装模型
                <button class="refresh-btn" :disabled="loadingModels" @click="fetchModels" title="刷新模型列表">
                  <el-icon size="11" :class="{ spinning: loadingModels }"><Refresh /></el-icon>
                </button>
              </div>

              <div v-if="loadingModels" class="loading-row">
                <el-icon class="spinning" size="13"><Loading /></el-icon>
                <span>正在拉取模型列表...</span>
              </div>

              <div v-else-if="ollamaModels.length === 0" class="empty-tip">
                未检测到 Ollama 模型，请确认 Ollama 正在运行
              </div>

              <div v-else class="model-list">
                <div
                  v-for="m in ollamaModels"
                  :key="m.name"
                  class="model-item"
                  :class="{ selected: store.ollamaModel === m.name }"
                  @click="store.ollamaModel = m.name"
                >
                  <div class="model-item-main">
                    <span class="model-name">{{ m.name }}</span>
                    <span v-if="store.ollamaModel === m.name" class="model-check">
                      <el-icon size="11"><Check /></el-icon>
                    </span>
                  </div>
                  <div class="model-size">{{ formatSize(m.size) }}</div>
                </div>
              </div>

              <!-- 使用默认 -->
              <div
                class="model-item default-item"
                :class="{ selected: store.ollamaModel === '' }"
                @click="store.ollamaModel = ''"
              >
                <span class="model-name">跟随服务器默认配置</span>
                <span v-if="store.ollamaModel === ''" class="model-check">
                  <el-icon size="11"><Check /></el-icon>
                </span>
              </div>
            </div>
          </template>

          <!-- ── 远程 API 配置 ── -->
          <template v-else>
            <!-- 服务商预设 -->
            <div class="section">
              <div class="section-label">服务商</div>
              <div class="preset-grid">
                <button
                  v-for="(preset, key) in presets"
                  :key="key"
                  class="preset-btn"
                  :class="{ active: store.remotePreset === key }"
                  @click="selectPreset(key)"
                >
                  {{ preset.name }}
                </button>
              </div>
            </div>

            <!-- API Base URL -->
            <div class="section">
              <div class="section-label">Base URL</div>
              <input
                v-model="store.remoteBaseUrl"
                class="form-input"
                placeholder="https://api.deepseek.com/v1"
                spellcheck="false"
              />
            </div>

            <!-- API Key -->
            <div class="section">
              <div class="section-label">API Key</div>
              <div class="input-with-eye">
                <input
                  v-model="store.remoteApiKey"
                  :type="showKey ? 'text' : 'password'"
                  class="form-input"
                  placeholder="sk-..."
                  spellcheck="false"
                />
                <button class="eye-btn" @click="showKey = !showKey" :title="showKey ? '隐藏' : '显示'">
                  <el-icon size="13"><component :is="showKey ? Hide : View" /></el-icon>
                </button>
              </div>
            </div>

            <!-- 模型名 -->
            <div class="section">
              <div class="section-label">
                模型名
                <span class="label-hint">（手动填写或从预设选择）</span>
              </div>
              <input
                v-model="store.remoteModel"
                class="form-input"
                placeholder="deepseek-chat"
                spellcheck="false"
              />
              <!-- 预设模型快捷选择 -->
              <div v-if="currentPresetModels.length" class="quick-models">
                <span
                  v-for="m in currentPresetModels"
                  :key="m"
                  class="quick-model"
                  :class="{ active: store.remoteModel === m }"
                  @click="store.remoteModel = m"
                >{{ m }}</span>
              </div>
            </div>
          </template>

          <!-- ── 推理参数 ── -->
          <div class="section section-params">
            <div class="section-label">推理参数</div>
            <div class="params-row">
              <div class="param-item">
                <span class="param-label">Temperature</span>
                <input
                  v-model.number="temperature"
                  type="number" min="0" max="2" step="0.05"
                  class="param-input"
                />
              </div>
              <div class="param-item">
                <span class="param-label">Top-P</span>
                <input
                  v-model.number="topP"
                  type="number" min="0" max="1" step="0.05"
                  class="param-input"
                />
              </div>
              <div class="param-item">
                <span class="param-label">Max Tokens</span>
                <input
                  v-model.number="maxTokens"
                  type="number" min="256" max="32768" step="256"
                  class="param-input wide"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="drawer-footer">
          <button class="btn-test" :disabled="testing" @click="testConnection">
            <el-icon size="12" :class="{ spinning: testing }"><component :is="testing ? Loading : Promotion" /></el-icon>
            {{ testing ? '测试中...' : '连接测试' }}
          </button>
          <div class="footer-right">
            <button class="btn-cancel" @click="close">取消</button>
            <button class="btn-apply" @click="apply">应用</button>
          </div>
        </div>

        <!-- 测试结果提示 -->
        <transition name="toast-slide">
          <div v-if="testResult" class="test-toast" :class="testResult.ok ? 'toast-ok' : 'toast-err'">
            <el-icon size="13"><component :is="testResult.ok ? CircleCheck : CircleClose" /></el-icon>
            <span>{{ testResult.msg }}</span>
          </div>
        </transition>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  Cpu, Close, Monitor, Connection, Refresh, Loading,
  Check, View, Hide, Promotion, CircleCheck, CircleClose,
} from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { modelApi } from '@/api'
import { ElMessage } from 'element-plus'

const store = useChatStore()

const visible = ref(false)
const ollamaModels = ref([])
const loadingModels = ref(false)
const presets = ref({})
const showKey = ref(false)
const testing = ref(false)
const testResult = ref(null)
let testTimer = null

// 推理参数本地副本（应用时同步到 llm-config 接口）
const temperature = ref(0.3)
const topP = ref(0.9)
const maxTokens = ref(4096)

// 当前预设的推荐模型列表
const currentPresetModels = computed(() => {
  return presets.value[store.remotePreset]?.models || []
})

// ── 生命周期 ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  // 拉取远程预设（轻量，启动时加载一次）
  try {
    const res = await modelApi.getPresets()
    presets.value = res.presets || {}
  } catch {}

  // 拉取当前服务器配置
  try {
    const cfg = await modelApi.getLLMConfig()
    temperature.value = cfg.temperature ?? 0.3
    topP.value = cfg.top_p ?? 0.9
    maxTokens.value = cfg.max_tokens ?? 4096
  } catch {}
})

// ── 方法 ──────────────────────────────────────────────────────────────────────
function open() {
  visible.value = true
  if (store.llmProvider === 'ollama' && ollamaModels.value.length === 0) {
    fetchModels()
  }
}

function close() {
  visible.value = false
}

async function fetchModels() {
  loadingModels.value = true
  try {
    const res = await modelApi.listOllamaModels()
    ollamaModels.value = res.models || []
  } catch {
    ollamaModels.value = []
  } finally {
    loadingModels.value = false
  }
}

function selectPreset(key) {
  store.remotePreset = key
  const preset = presets.value[key]
  if (!preset) return
  if (preset.base_url) store.remoteBaseUrl = preset.base_url
  if (preset.models?.[0]) store.remoteModel = preset.models[0]
}

async function testConnection() {
  // 先应用当前配置到服务器
  await applyToServer()
  testing.value = true
  testResult.value = null
  clearTimeout(testTimer)
  try {
    const res = await modelApi.testLLM()
    testResult.value = {
      ok: true,
      msg: `连接成功 · ${res.model} · ${res.elapsed_s}s`,
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '连接失败'
    testResult.value = { ok: false, msg }
  } finally {
    testing.value = false
    testTimer = setTimeout(() => { testResult.value = null }, 5000)
  }
}

async function applyToServer() {
  try {
    const payload = {
      provider: store.llmProvider,
      temperature: temperature.value,
      top_p: topP.value,
      max_tokens: maxTokens.value,
    }
    if (store.llmProvider === 'ollama') {
      payload.ollama_model = store.ollamaModel
    } else {
      payload.remote_base_url = store.remoteBaseUrl
      payload.remote_api_key = store.remoteApiKey
      payload.remote_model = store.remoteModel
    }
    await modelApi.setLLMConfig(payload)
  } catch {}
}

async function apply() {
  await applyToServer()
  ElMessage.success('模型配置已应用')
  close()
}

function formatSize(bytes) {
  if (!bytes) return ''
  const gb = bytes / 1024 / 1024 / 1024
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1024 / 1024).toFixed(0)} MB`
}

// 暴露 open 方法给父组件
defineExpose({ open })
</script>

<style scoped>
/* ── 遮罩 ── */
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.mask-fade-enter-active, .mask-fade-leave-active { transition: opacity 0.2s; }
.mask-fade-enter-from, .mask-fade-leave-to { opacity: 0; }

/* ── 抽屉面板 ── */
.model-drawer {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 360px;
  background: #0f1629;
  border-left: 1px solid var(--border);
  z-index: 1001;
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.5);
}

.drawer-slide-enter-active, .drawer-slide-leave-active { transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
.drawer-slide-enter-from, .drawer-slide-leave-to { transform: translateX(100%); }

/* ── 头部 ── */
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.drawer-close {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.drawer-close:hover { background: rgba(255,255,255,0.07); color: var(--text-primary); }

/* ── 内容区 ── */
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section { display: flex; flex-direction: column; gap: 8px; }

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Provider Tab */
.provider-tabs { display: flex; gap: 6px; }

.provider-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.03);
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.provider-tab:hover { color: var(--text-secondary); background: rgba(255,255,255,0.06); }
.provider-tab.active {
  background: rgba(59,130,246,0.15);
  border-color: rgba(59,130,246,0.4);
  color: var(--accent-light);
}

/* 模型列表 */
.loading-row, .empty-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 0;
}

.model-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
}

.model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
}
.model-item:hover { background: rgba(255,255,255,0.04); }
.model-item.selected {
  background: rgba(59,130,246,0.1);
  border-color: rgba(59,130,246,0.3);
}

.model-item-main {
  display: flex;
  align-items: center;
  gap: 6px;
}

.model-name {
  font-size: 12px;
  color: var(--text-primary);
  font-family: monospace;
}

.model-size {
  font-size: 10px;
  color: var(--text-muted);
}

.model-check { color: var(--accent-light); }

.default-item {
  margin-top: 4px;
  border: 1px dashed var(--border) !important;
}

.refresh-btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;
  display: inline-flex;
  align-items: center;
  transition: color 0.15s;
}
.refresh-btn:hover { color: var(--accent-light); }

/* 服务商预设 */
.preset-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preset-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.03);
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.preset-btn:hover { color: var(--text-secondary); background: rgba(255,255,255,0.06); }
.preset-btn.active {
  background: rgba(59,130,246,0.15);
  border-color: rgba(59,130,246,0.35);
  color: var(--accent-light);
}

/* 表单输入 */
.form-input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--text-primary);
  font-size: 12px;
  font-family: monospace;
  outline: none;
  transition: border-color 0.15s;
}
.form-input:focus { border-color: rgba(59,130,246,0.5); }
.form-input::placeholder { color: var(--text-muted); }

.input-with-eye { position: relative; }
.input-with-eye .form-input { padding-right: 36px; }
.eye-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}
.eye-btn:hover { color: var(--text-secondary); }

/* 快捷模型选择 */
.quick-models {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 2px;
}

.quick-model {
  padding: 3px 9px;
  border-radius: 5px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  font-size: 10px;
  font-family: monospace;
  cursor: pointer;
  transition: all 0.15s;
}
.quick-model:hover { color: var(--text-secondary); background: rgba(255,255,255,0.04); }
.quick-model.active {
  background: rgba(59,130,246,0.12);
  border-color: rgba(59,130,246,0.35);
  color: var(--accent-light);
}

/* 推理参数 */
.params-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.param-label {
  font-size: 10px;
  color: var(--text-muted);
}

.param-input {
  width: 70px;
  padding: 6px 8px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  text-align: center;
}
.param-input.wide { width: 90px; }
.param-input:focus { border-color: rgba(59,130,246,0.5); }

/* ── 底部 ── */
.drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  gap: 8px;
}

.footer-right { display: flex; gap: 8px; }

.btn-test, .btn-cancel, .btn-apply {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: 7px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid var(--border);
}

.btn-test {
  background: rgba(255,255,255,0.04);
  color: var(--text-secondary);
}
.btn-test:hover:not(:disabled) { background: rgba(255,255,255,0.08); color: var(--text-primary); }
.btn-test:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-cancel {
  background: transparent;
  color: var(--text-muted);
}
.btn-cancel:hover { color: var(--text-secondary); background: rgba(255,255,255,0.04); }

.btn-apply {
  background: rgba(59,130,246,0.2);
  border-color: rgba(59,130,246,0.4);
  color: var(--accent-light);
}
.btn-apply:hover { background: rgba(59,130,246,0.3); }

/* ── 测试结果 Toast ── */
.test-toast {
  position: absolute;
  bottom: 64px;
  left: 18px;
  right: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 8px;
  font-size: 12px;
}

.toast-ok {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

.toast-err {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.toast-slide-enter-active, .toast-slide-leave-active { transition: all 0.2s; }
.toast-slide-enter-from, .toast-slide-leave-to { opacity: 0; transform: translateY(8px); }

/* ── 通用动画 ── */
.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* label hint */
.label-hint {
  font-size: 10px;
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  color: var(--text-muted);
  opacity: 0.7;
}
</style>
