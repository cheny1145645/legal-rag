<template>
  <teleport to="body">
    <!-- 遮罩 -->
    <transition name="mask-fade">
      <div v-if="visible" class="drawer-mask" @click="close"></div>
    </transition>

    <!-- 抽屉面板 -->
    <transition name="drawer-slide">
      <div v-if="visible" class="module-drawer">
        <!-- 头部 -->
        <div class="drawer-header">
          <div class="drawer-title">
            <el-icon><Setting /></el-icon>
            <span>模块控制</span>
          </div>
          <button class="drawer-close" @click="close">
            <el-icon><Close /></el-icon>
          </button>
        </div>

        <!-- 内容 -->
        <div class="drawer-body">
          <!-- 懒加载模式 -->
          <div class="section">
            <div class="section-header">
              <div class="section-label">启动模式</div>
              <el-switch
                v-model="status.lazy_load_enabled"
                @change="toggle('lazy_load', $event)"
                :loading="loading"
              />
            </div>
            <div class="section-desc">
              {{ status.lazy_load_enabled ? '懒加载：首次请求时加载组件' : '预加载：启动时加载所有组件' }}
            </div>
          </div>

          <!-- 模块开关 -->
          <div class="section">
            <div class="section-label">核心算法模块</div>
            
            <!-- GLVR -->
            <div class="module-item">
              <div class="module-info">
                <span class="module-name">GLVR</span>
                <span class="module-desc">图谱引导的向量重排序</span>
              </div>
              <el-switch
                v-model="status.enable_glvr"
                @change="toggle('glvr', $event)"
                :loading="loading"
              />
            </div>
            <div v-if="status.enable_glvr" class="module-params">
              <span class="param-label">γ (图权重): {{ status.glvr_gamma }}</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                v-model.number="status.glvr_gamma"
                class="range-input"
              />
            </div>

            <!-- QAWRF -->
            <div class="module-item">
              <div class="module-info">
                <span class="module-name">QAWRF</span>
                <span class="module-desc">查询感知动态权重融合</span>
              </div>
              <el-switch
                v-model="status.enable_qawrf"
                @change="toggle('qawrf', $event)"
                :loading="loading"
              />
            </div>

            <!-- LCCP -->
            <div class="module-item">
              <div class="module-info">
                <span class="module-name">LCCP</span>
                <span class="module-desc">法律推理链置信度传播</span>
              </div>
              <el-switch
                v-model="status.enable_lccp"
                @change="toggle('lccp', $event)"
                :loading="loading"
              />
            </div>
            <div v-if="status.enable_lccp" class="module-params">
              <span class="param-label">λ (衰减因子): {{ status.lccp_decay_factor }}</span>
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.1"
                v-model.number="status.lccp_decay_factor"
                class="range-input"
              />
            </div>
          </div>

          <!-- 权重配置 -->
          <div class="section">
            <div class="section-label">检索权重</div>
            <div class="weight-row">
              <div class="weight-item">
                <span class="weight-label">BM25</span>
                <span class="weight-value">{{ status.bm25_weight }}</span>
              </div>
              <div class="weight-item">
                <span class="weight-label">向量</span>
                <span class="weight-value">{{ status.vector_weight }}</span>
              </div>
            </div>
          </div>

          <!-- 系统状态 -->
          <div class="section">
            <div class="section-label">系统状态</div>
            <div class="status-grid">
              <div class="status-item">
                <span class="status-key">BM25索引</span>
                <span class="status-val" :class="status.retriever?.bm25_initialized ? 'ok' : 'pending'">
                  {{ status.retriever?.bm25_initialized ? '已就绪' : '待初始化' }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-key">图谱节点</span>
                <span class="status-val">
                  {{ status.knowledge_graph?.node_count || 0 }}
                </span>
              </div>
            </div>
          </div>

          <!-- 日志级别 -->
          <div class="section">
            <div class="section-label">日志级别</div>
            <div class="log-level-btns">
              <button
                v-for="level in ['DEBUG', 'INFO', 'WARNING']"
                :key="level"
                class="log-btn"
                :class="{ active: currentLogLevel === level }"
                @click="setLogLevel(level)"
              >
                {{ level }}
              </button>
            </div>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="drawer-footer">
          <button class="btn-refresh" @click="refresh" :disabled="loading">
            <el-icon><Refresh /></el-icon>
            刷新状态
          </button>
          <button class="btn-apply" @click="close">关闭</button>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Setting, Close, Refresh } from '@element-plus/icons-vue'
import { systemApi } from '@/api'
import { ElMessage } from 'element-plus'

const visible = ref(false)
const loading = ref(false)
const currentLogLevel = ref('INFO')

const status = ref({
  lazy_load_enabled: true,
  enable_glvr: true,
  enable_qawrf: false,
  enable_lccp: false,
  glvr_gamma: 0.3,
  lccp_decay_factor: 0.7,
  bm25_weight: 0.45,
  vector_weight: 0.70,
  retriever: { bm25_initialized: false, bm25_doc_count: 0 },
  knowledge_graph: { node_count: 0, edge_count: 0 },
})

onMounted(async () => {
  await refresh()
  // 获取当前日志级别
  try {
    const res = await systemApi.getLogLevel()
    currentLogLevel.value = res.log_level
  } catch {}
})

async function refresh() {
  loading.value = true
  try {
    const res = await systemApi.getModulesStatus()
    status.value = res
  } catch (e) {
    ElMessage.error('获取状态失败')
  } finally {
    loading.value = false
  }
}

async function toggle(module, enable) {
  loading.value = true
  try {
    let params = null
    if (module === 'lccp' && enable) {
      params = { decay_factor: status.value.lccp_decay_factor }
    }
    await systemApi.toggleModule(module, enable, params)
    ElMessage.success(`${module} 已${enable ? '启用' : '禁用'}`)
  } catch (e) {
    ElMessage.error('操作失败')
    await refresh() // 失败回滚
  } finally {
    loading.value = false
  }
}

async function setLogLevel(level) {
  try {
    await systemApi.setLogLevel(level)
    currentLogLevel.value = level
    ElMessage.success(`日志级别已设置为 ${level}`)
  } catch (e) {
    ElMessage.error('设置失败')
  }
}

function open() {
  visible.value = true
  refresh()
}

function close() {
  visible.value = false
}

defineExpose({ open, close })
</script>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.mask-fade-enter-active, .mask-fade-leave-active { transition: opacity 0.2s; }
.mask-fade-enter-from, .mask-fade-leave-to { opacity: 0; }

.module-drawer {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 340px;
  background: #0f1629;
  border-left: 1px solid var(--border);
  z-index: 1001;
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.5);
}

.drawer-slide-enter-active, .drawer-slide-leave-active { transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
.drawer-slide-enter-from, .drawer-slide-leave-to { transform: translateX(100%); }

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
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section { display: flex; flex-direction: column; gap: 10px; }

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.6px;
}

.section-desc {
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.7;
}

.module-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.module-info { display: flex; flex-direction: column; gap: 2px; }

.module-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }

.module-desc { font-size: 10px; color: var(--text-muted); }

.module-params {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: rgba(0,0,0,0.2);
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
}

.param-label { font-size: 11px; color: var(--text-muted); }

.range-input { flex: 1; cursor: pointer; }

.weight-row {
  display: flex;
  gap: 12px;
}

.weight-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.weight-label { font-size: 11px; color: var(--text-muted); }

.weight-value { font-size: 14px; font-weight: 600; color: var(--accent-light); font-family: monospace; }

.status-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}

.status-key { font-size: 11px; color: var(--text-muted); }

.status-val { font-size: 12px; color: var(--text-secondary); font-weight: 500; }
.status-val.ok { color: #4ade80; }
.status-val.pending { color: #fbbf24; }

.log-level-btns { display: flex; gap: 6px; }

.log-btn {
  flex: 1;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.log-btn:hover { color: var(--text-secondary); }
.log-btn.active {
  background: rgba(59,130,246,0.15);
  border-color: rgba(59,130,246,0.4);
  color: var(--accent-light);
}

.drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  gap: 8px;
}

.btn-refresh, .btn-apply {
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

.btn-refresh { background: rgba(255,255,255,0.04); color: var(--text-secondary); }
.btn-refresh:hover:not(:disabled) { background: rgba(255,255,255,0.08); }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-apply { background: rgba(59,130,246,0.2); border-color: rgba(59,130,246,0.4); color: var(--accent-light); }
.btn-apply:hover { background: rgba(59,130,246,0.3); }
</style>