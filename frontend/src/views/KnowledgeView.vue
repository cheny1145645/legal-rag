<template>
  <div class="knowledge-view">
    <div class="page-header">
      <div class="page-title-row">
        <div class="page-icon"><el-icon size="18"><FolderOpened /></el-icon></div>
        <div>
          <h2>知识库管理</h2>
          <p>上传法律文档，构建专属向量知识库</p>
        </div>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- 上传区域 -->
      <el-col :span="13">
        <el-card class="dark-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#60a5fa"><Upload /></el-icon>
              <span>上传法律文档</span>
            </div>
          </template>
          <el-upload
            drag
            action="/api/ingest/upload"
            :accept="'.pdf,.docx,.doc,.txt'"
            :before-upload="beforeUpload"
            :on-success="onUploadSuccess"
            :on-error="onUploadError"
            :show-file-list="true"
            multiple
            class="dark-uploader"
          >
            <div class="upload-inner">
              <div class="upload-icon-wrap">
                <el-icon size="32" color="#3b82f6"><UploadFilled /></el-icon>
              </div>
              <p class="upload-text">拖拽文件至此，或 <em>点击上传</em></p>
              <p class="upload-tip">支持 PDF · Word · TXT，单文件 ≤ 50MB</p>
            </div>
          </el-upload>
        </el-card>

        <!-- 分类浏览面板 -->
        <el-card class="dark-card" style="margin-top:16px">
          <template #header>
            <div class="card-header" style="justify-content:space-between">
              <div style="display:flex;align-items:center;gap:8px">
                <el-icon color="#60a5fa"><Collection /></el-icon>
                <span>条文分类浏览</span>
                <span class="total-badge">共 {{ summaryData.total || 0 }} 条</span>
              </div>
              <button class="refresh-btn" @click="loadSources" :disabled="sourcesLoading">
                <el-icon :class="{ spinning: sourcesLoading }"><Refresh /></el-icon>
              </button>
            </div>
          </template>

          <div v-if="sourcesLoading" class="sources-loading">
            <div class="loading-dots"><span></span><span></span><span></span></div>
            <span>加载中...</span>
          </div>

          <div v-else-if="!summaryData.total" class="sources-empty">
            <el-icon size="32" color="var(--text-muted)"><FolderOpened /></el-icon>
            <p>知识库为空，请先上传法律文档</p>
          </div>

          <div v-else>
            <!-- 大类切换 -->
            <div class="category-tabs">
              <button
                v-for="(catData, catName) in summaryData.categories"
                :key="catName"
                class="cat-tab"
                :class="{ active: activeCategory === catName }"
                @click="switchCategory(catName)"
              >
                <span class="cat-icon">{{ catName === '法律文档' ? '📄' : '🌐' }}</span>
                <span class="cat-name">{{ catName }}</span>
                <span class="cat-count">{{ catData.total }}</span>
              </button>
            </div>

            <transition name="tab-slide" mode="out-in">
              <div v-if="activeCategory && summaryData.categories[activeCategory]" :key="activeCategory">
                <!-- 来源列表 -->
                <div class="source-list">
                  <div
                    v-for="(srcData, srcName) in summaryData.categories[activeCategory].sources"
                    :key="srcName"
                    class="source-entry"
                    :class="{ expanded: expandedSource === srcName }"
                    @click="toggleExpand(srcName)"
                  >
                    <!-- 来源头部 -->
                    <div class="source-entry-header">
                      <div class="source-entry-left">
                        <span class="source-dot"></span>
                        <span class="source-entry-name" :title="srcName">{{ srcName }}</span>
                      </div>
                      <div class="source-entry-right">
                        <span class="source-entry-count">{{ srcData.count }} 条</span>
                        <button
                          class="delete-source-btn"
                          :class="{ deleting: deletingSource === srcName }"
                          :disabled="deletingSource === srcName"
                          @click.stop="confirmDeleteSource(srcName)"
                          title="删除该来源的所有条文"
                        >
                          <el-icon v-if="deletingSource === srcName" class="spinning"><Loading /></el-icon>
                          <el-icon v-else><Delete /></el-icon>
                        </button>
                        <el-icon class="expand-arrow" :class="{ open: expandedSource === srcName }">
                          <ArrowRight />
                        </el-icon>
                      </div>
                    </div>

                    <!-- 展开的样本 -->
                    <transition name="expand-down">
                      <div v-if="expandedSource === srcName" class="source-samples">
                        <div
                          v-for="(sample, i) in srcData.samples"
                          :key="i"
                          class="sample-item"
                        >
                          <span class="sample-idx">{{ i + 1 }}</span>
                          <span class="sample-text">{{ sample }}</span>
                        </div>
                        <p class="sample-hint">随机抽样片段，仅供预览</p>
                      </div>
                    </transition>
                  </div>
                </div>
              </div>
            </transition>
          </div>
        </el-card>
      </el-col>

      <!-- 状态面板 -->
      <el-col :span="11">
        <el-card class="dark-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#60a5fa"><DataAnalysis /></el-icon>
              <span>知识库状态</span>
            </div>
          </template>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-num">{{ stats.doc_count || 0 }}</div>
              <div class="stat-label">文档块总数</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ stats.chunk_size || 500 }}</div>
              <div class="stat-label">切块大小</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ stats.top_k || 5 }}</div>
              <div class="stat-label">检索条数</div>
            </div>
          </div>

          <div class="divider"></div>

          <div class="action-row">
            <button class="action-btn primary" @click="loadDirectory" :disabled="loading">
              <el-icon><FolderAdd /></el-icon>
              <span>{{ loading ? '加载中...' : '加载文档目录' }}</span>
            </button>
            <button class="action-btn secondary" @click="forceReload" :disabled="loading">
              <el-icon><RefreshRight /></el-icon>
              <span>强制刷新</span>
            </button>
            <el-popconfirm title="确定清空知识库？不可恢复。" @confirm="clearVectorStore">
              <template #reference>
                <button class="action-btn danger">
                  <el-icon><Delete /></el-icon>
                  <span>清空知识库</span>
                </button>
              </template>
            </el-popconfirm>
          </div>
        </el-card>

        <!-- 技术配置 -->
        <el-card class="dark-card" style="margin-top:16px">
          <template #header>
            <div class="card-header">
              <el-icon color="#60a5fa"><Setting /></el-icon>
              <span>当前配置</span>
            </div>
          </template>
          <div class="config-list">
            <div class="config-item" v-for="c in configs" :key="c.label">
              <span class="c-label">{{ c.label }}</span>
              <span class="c-value">{{ c.value }}</span>
            </div>
          </div>
        </el-card>

        <!-- 批量审核卡片 -->
        <el-card class="dark-card audit-card" style="margin-top:16px">
          <template #header>
            <div class="card-header">
              <el-icon color="#a78bfa"><CircleCheck /></el-icon>
              <span>知识质量审核</span>
            </div>
          </template>

          <p class="audit-desc">调用模型对知识库内容进行主题鉴定，识别并清理与法律无关的噪音数据。</p>

          <!-- 审核选项 -->
          <div class="audit-options">
            <div class="audit-option-row">
              <span class="audit-opt-label">审核范围</span>
              <div class="seg-ctrl">
                <button :class="{ active: auditScope === 'web' }" @click="auditScope = 'web'">仅联网内容</button>
                <button :class="{ active: auditScope === 'all' }" @click="auditScope = 'all'">全部内容</button>
              </div>
            </div>
            <div class="audit-option-row">
              <span class="audit-opt-label">审核后处理</span>
              <div class="seg-ctrl">
                <button :class="{ active: !auditAutoDelete }" @click="auditAutoDelete = false">仅报告</button>
                <button :class="{ active: auditAutoDelete }" @click="auditAutoDelete = true">自动删除</button>
              </div>
            </div>
            <div class="audit-option-row">
              <span class="audit-opt-label">每来源样本数</span>
              <div class="num-ctrl">
                <button @click="auditSampleSize = Math.max(1, auditSampleSize - 1)">−</button>
                <span>{{ auditSampleSize }}</span>
                <button @click="auditSampleSize = Math.min(10, auditSampleSize + 1)">+</button>
              </div>
            </div>
          </div>

          <button
            class="action-btn primary audit-run-btn"
            :disabled="auditing"
            @click="runAudit"
          >
            <el-icon v-if="auditing" class="spinning"><Loading /></el-icon>
            <el-icon v-else><CircleCheck /></el-icon>
            <span>{{ auditing ? '审核中，请稍候...' : '开始审核' }}</span>
          </button>

          <!-- 审核进度条 -->
          <div v-if="auditing || auditProgressDone" class="audit-progress-wrap">
            <div class="audit-progress-bar" :style="{ width: auditProgress + '%' }"></div>
            <span class="audit-progress-label">{{ auditProgressLabel }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 审核结果抽屉 -->
    <el-drawer
      v-model="auditDrawerVisible"
      title="知识审核报告"
      direction="rtl"
      size="480px"
      :modal="true"
      class="audit-drawer"
    >
      <div v-if="auditResult" class="audit-report">
        <!-- 汇总统计 -->
        <div class="audit-summary">
          <div class="audit-stat pass">
            <div class="audit-stat-num">{{ auditResult.passed }}</div>
            <div class="audit-stat-label">通过</div>
          </div>
          <div class="audit-stat fail">
            <div class="audit-stat-num">{{ auditResult.failed }}</div>
            <div class="audit-stat-label">不通过</div>
          </div>
          <div class="audit-stat uncertain">
            <div class="audit-stat-num">{{ auditResult.uncertain }}</div>
            <div class="audit-stat-label">不确定</div>
          </div>
        </div>

        <p class="audit-msg">{{ auditResult.message }}</p>

        <div v-if="auditResult.deleted_sources.length" class="audit-deleted-tip">
          已自动删除：{{ auditResult.deleted_sources.join('、') }}
        </div>

        <!-- 结果列表 -->
        <div class="audit-result-list">
          <div
            v-for="r in auditResult.results"
            :key="r.source_name"
            class="audit-result-item"
            :class="r.verdict"
          >
            <div class="audit-result-header">
              <span class="audit-verdict-dot"></span>
              <span class="audit-result-name" :title="r.source_name">{{ r.source_name }}</span>
              <span class="audit-verdict-badge">{{ verdictLabel(r.verdict) }}</span>
            </div>
            <p class="audit-result-reason">{{ r.reason }}</p>
            <div class="audit-result-meta">
              {{ r.chunk_count }} 个文本块 · 抽样 {{ r.samples.length }} 条
            </div>

            <!-- 手动删除按钮（仅 fail/uncertain 且未自动删除时显示） -->
            <button
              v-if="r.verdict !== 'pass' && !auditResult.deleted_sources.includes(r.source_name)"
              class="audit-delete-btn"
              :disabled="deletingSource === r.source_name"
              @click="confirmDeleteSource(r.source_name)"
            >
              <el-icon v-if="deletingSource === r.source_name" class="spinning"><Loading /></el-icon>
              <el-icon v-else><Delete /></el-icon>
              删除该来源
            </button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, Refresh, ArrowRight, Delete, Loading, CircleCheck } from '@element-plus/icons-vue'
import {
  FolderOpened, Upload, UploadFilled, DataAnalysis,
  Setting, FolderAdd, RefreshRight,
} from '@element-plus/icons-vue'
import { ingestApi, systemApi } from '@/api'

const stats = ref({})
const loading = ref(false)
const summaryData = ref({ categories: {}, total: 0 })
const sourcesLoading = ref(false)
const activeCategory = ref(null)
const expandedSource = ref(null)
const deletingSource = ref(null)

// ── 审核相关状态 ──────────────────────────────────────────────────────────────
const auditing = ref(false)
const auditScope = ref('web')          // 'web' | 'all'
const auditAutoDelete = ref(false)
const auditSampleSize = ref(3)
const auditDrawerVisible = ref(false)
const auditResult = ref(null)

// 进度条
const auditProgress = ref(0)          // 0-100
const auditProgressDone = ref(false)  // 完成后短暂保留进度条
const auditProgressLabel = ref('')
let _progressTimer = null

const _startProgress = () => {
  auditProgress.value = 0
  auditProgressDone.value = false
  auditProgressLabel.value = '正在审核...'
  // 慢速随机步进：800ms/次，0.5-2%，上限75%，30%概率本次跳过（磕磕绊绊感）
  _progressTimer = setInterval(() => {
    if (auditProgress.value < 75) {
      if (Math.random() > 0.3) {  // 70%概率才走，制造停顿感
        const step = Math.random() * 1.5 + 0.5   // 0.5 ~ 2%
        auditProgress.value = Math.min(75, auditProgress.value + step)
      }
    }
  }, 800)
}

const _finishProgress = () => {
  clearInterval(_progressTimer)
  _progressTimer = null
  auditProgress.value = 100
  auditProgressLabel.value = '审核完成'
  auditProgressDone.value = true
  // 1.5 秒后收起进度条
  setTimeout(() => { auditProgressDone.value = false }, 1500)
}

const verdictLabel = (v) => ({ pass: '✓ 通过', fail: '✗ 不通过', uncertain: '? 不确定' }[v] || v)

const runAudit = async () => {
  auditing.value = true
  auditResult.value = null
  _startProgress()
  try {
    const res = await ingestApi.auditKnowledgeBase({
      web_only: auditScope.value === 'web',
      sample_size: auditSampleSize.value,
      auto_delete: auditAutoDelete.value,
    })
    auditResult.value = res
    _finishProgress()
    auditDrawerVisible.value = true
    if (auditAutoDelete.value && res.deleted_sources?.length) {
      await loadSources()
      await refreshStats()
    }
  } catch {
    clearInterval(_progressTimer)
    auditProgress.value = 0
    auditProgressDone.value = false
  } finally {
    auditing.value = false
  }
}

const configs = computed(() => [
  { label: '推理模型', value: stats.value.model || 'deepseek-r1:latest' },
  { label: '嵌入模型', value: 'BAAI/bge-m3' },
  { label: '检索策略', value: 'BM25 + 向量混合' },
  { label: '向量数据库', value: 'ChromaDB（本地）' },
])

const refreshStats = async () => {
  try { stats.value = await systemApi.stats() } catch {}
}

const loadSources = async () => {
  sourcesLoading.value = true
  try {
    const data = await systemApi.sources()
    summaryData.value = data
    const cats = Object.keys(data.categories || {})
    if (cats.length && !activeCategory.value) {
      activeCategory.value = cats[0]
    }
    // 当前大类被删空时自动切换
    if (activeCategory.value && !data.categories[activeCategory.value]) {
      activeCategory.value = cats[0] || null
    }
  } catch {
    ElMessage.error('加载分类失败')
  } finally {
    sourcesLoading.value = false
  }
}

const switchCategory = (cat) => {
  activeCategory.value = cat
  expandedSource.value = null
}

const toggleExpand = (srcName) => {
  expandedSource.value = expandedSource.value === srcName ? null : srcName
}

const confirmDeleteSource = async (srcName) => {
  try {
    await ElMessageBox.confirm(
      `确定删除来源「${srcName}」的所有条文？此操作不可撤销。`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  deletingSource.value = srcName
  if (expandedSource.value === srcName) expandedSource.value = null
  try {
    const res = await ingestApi.deleteSource(srcName)
    ElMessage.success(res.message)
    // 同步更新审核报告中该来源的删除状态
    if (auditResult.value) {
      auditResult.value.deleted_sources.push(srcName)
    }
    await loadSources()
    await refreshStats()
  } catch {
    // 错误已由 axios 拦截器处理
  } finally {
    deletingSource.value = null
  }
}

onMounted(async () => {
  await refreshStats()
  await loadSources()
})

const beforeUpload = (file) => {
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  return true
}

const onUploadSuccess = (res) => {
  ElMessage.success(res.message)
  refreshStats()
  loadSources()
}

const onUploadError = () => {
  ElMessage.error('上传失败，请检查文件格式')
}

const loadDirectory = async () => {
  loading.value = true
  try {
    const res = await ingestApi.loadDirectory()
    ElMessage.success(res.message)
    await refreshStats()
    await loadSources()
  } finally {
    loading.value = false
  }
}

const forceReload = async () => {
  loading.value = true
  try {
    const res = await ingestApi.forceReload()
    ElMessage.success(res.message)
    await refreshStats()
    await loadSources()
  } finally {
    loading.value = false
  }
}

const clearVectorStore = async () => {
  try {
    await ingestApi.clearVectorStore()
    ElMessage.success('知识库已清空')
    summaryData.value = { categories: {}, total: 0 }
    activeCategory.value = null
    expandedSource.value = null
    refreshStats()
  } catch {}
}
</script>

<style scoped>
.knowledge-view {
  padding: 24px;
  height: 100vh;
  overflow-y: auto;
  background: transparent;
}

.page-header { margin-bottom: 24px; }

.page-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.page-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(59,130,246,0.12);
  border: 1px solid rgba(59,130,246,0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-light);
}

h2 { font-size: 18px; font-weight: 700; color: var(--text-primary); margin-bottom: 2px; }
p  { font-size: 12px; color: var(--text-muted); margin: 0; }

.dark-card { background: rgba(17,24,39,0.8) !important; backdrop-filter: blur(12px); }

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.total-badge {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 99px;
  background: rgba(59,130,246,0.12);
  color: var(--accent-light);
  border: 1px solid rgba(59,130,246,0.2);
  font-weight: 400;
}

.refresh-btn {
  width: 26px;
  height: 26px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  margin-left: auto;
}
.refresh-btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.08);
  color: var(--text-primary);
}
.refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 加载 / 空 */
.sources-loading, .sources-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px;
  color: var(--text-muted);
  font-size: 13px;
}

.loading-dots { display: flex; gap: 4px; }
.loading-dots span {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: bounce 1.2s infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 大类切换 Tab */
.category-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.cat-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.03);
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.cat-tab:hover {
  background: rgba(255,255,255,0.06);
  color: var(--text-secondary);
}

.cat-tab.active {
  background: rgba(59,130,246,0.15);
  border-color: rgba(59,130,246,0.4);
  color: var(--accent-light);
}

.cat-icon { font-size: 14px; line-height: 1; }
.cat-name { font-weight: 500; }

.cat-count {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 99px;
  background: rgba(59,130,246,0.12);
  color: var(--accent-light);
  border: 1px solid rgba(59,130,246,0.2);
  font-weight: 600;
}

/* 来源折叠列表 */
.source-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.source-entry {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  transition: border-color 0.2s;
  cursor: pointer;
}

.source-entry:hover,
.source-entry.expanded {
  border-color: rgba(59,130,246,0.35);
}

.source-entry-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(255,255,255,0.02);
  user-select: none;
}

.source-entry.expanded .source-entry-header {
  background: rgba(59,130,246,0.06);
}

.source-entry-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.source-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
  opacity: 0.7;
}

.source-entry.expanded .source-dot {
  opacity: 1;
  box-shadow: 0 0 6px var(--accent-glow);
}

.source-entry-name {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.source-entry.expanded .source-entry-name {
  color: var(--text-primary);
}

.source-entry-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-left: 10px;
}

.source-entry-count {
  font-size: 11px;
  color: var(--accent-light);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.delete-source-btn {
  width: 22px;
  height: 22px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 5px;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.15s;
  flex-shrink: 0;
  opacity: 0;
}

.source-entry:hover .delete-source-btn {
  opacity: 1;
}

.delete-source-btn:hover {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
  border-color: rgba(248, 113, 113, 0.25);
}

.delete-source-btn.deleting {
  opacity: 1;
  color: var(--accent-light);
  cursor: not-allowed;
}

.expand-arrow {
  color: var(--text-muted);
  transition: transform 0.2s;
  font-size: 12px;
}

.expand-arrow.open {
  transform: rotate(90deg);
  color: var(--accent-light);
}

/* 展开样本区 */
.source-samples {
  padding: 10px 14px 12px;
  border-top: 1px solid rgba(59,130,246,0.1);
  background: rgba(0,0,0,0.15);
}

.sample-item {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  transition: border-color 0.15s;
  margin-bottom: 6px;
}

.sample-item:last-of-type { margin-bottom: 0; }

.sample-item:hover {
  border-color: rgba(59,130,246,0.25);
  background: rgba(59,130,246,0.03);
}

.sample-idx {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  background: rgba(59,130,246,0.15);
  color: var(--accent-light);
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.sample-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.sample-hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

/* Tab / 展开 动画 */
.tab-slide-enter-active { transition: all 0.22s ease; }
.tab-slide-leave-active { transition: all 0.15s ease; }
.tab-slide-enter-from   { opacity: 0; transform: translateX(12px); }
.tab-slide-leave-to     { opacity: 0; transform: translateX(-8px); }

.expand-down-enter-active { transition: all 0.22s ease; }
.expand-down-leave-active { transition: all 0.18s ease; }
.expand-down-enter-from   { opacity: 0; transform: translateY(-6px); }
.expand-down-leave-to     { opacity: 0; transform: translateY(-6px); }

/* 上传区 */
.upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  gap: 8px;
}

.upload-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: rgba(59,130,246,0.1);
  border: 1px solid rgba(59,130,246,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}

.upload-text { font-size: 14px; color: var(--text-secondary); }
.upload-text em { color: var(--accent-light); font-style: normal; }
.upload-tip { font-size: 12px; color: var(--text-muted); }

/* 状态面板 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  text-align: center;
  margin-bottom: 16px;
}

.stat-item {
  padding: 12px 8px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.stat-num { font-size: 26px; font-weight: 700; color: var(--accent-light); line-height: 1; }
.stat-label { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

.divider { height: 1px; background: var(--border); margin: 12px 0; }

.action-row { display: flex; gap: 10px; }

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid;
  font-size: 13px;
  cursor: pointer;
  transition: var(--transition);
  outline: none;
}

.action-btn.primary {
  background: rgba(59,130,246,0.15);
  border-color: rgba(59,130,246,0.3);
  color: var(--accent-light);
}
.action-btn.primary:hover:not(:disabled) {
  background: rgba(59,130,246,0.25);
  box-shadow: 0 0 12px var(--accent-glow);
}
.action-btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }

.action-btn.secondary {
  background: rgba(139,92,246,0.12);
  border-color: rgba(139,92,246,0.3);
  color: #a78bfa;
}
.action-btn.secondary:hover:not(:disabled) {
  background: rgba(139,92,246,0.22);
  box-shadow: 0 0 12px rgba(139,92,246,0.3);
}

.action-btn.danger {
  background: rgba(239,68,68,0.08);
  border-color: rgba(239,68,68,0.25);
  color: #f87171;
}
.action-btn.danger:hover { background: rgba(239,68,68,0.15); }

.config-list { display: flex; flex-direction: column; gap: 10px; }

.config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.config-item:last-child { border-bottom: none; }

.c-label { font-size: 12px; color: var(--text-muted); }
.c-value { font-size: 12px; color: var(--accent-light); font-weight: 500; }

/* ── 批量审核卡片 ─────────────────────────────────────────────────────────── */
.audit-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 16px;
  line-height: 1.7;
}

.audit-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.audit-option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.audit-opt-label {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 分段控制器 */
.seg-ctrl {
  display: flex;
  border: 1px solid var(--border);
  border-radius: 7px;
  overflow: hidden;
}

.seg-ctrl button {
  padding: 4px 12px;
  font-size: 12px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.seg-ctrl button + button {
  border-left: 1px solid var(--border);
}

.seg-ctrl button.active {
  background: rgba(167,139,250,0.15);
  color: #a78bfa;
}

.seg-ctrl button:hover:not(.active) {
  background: rgba(255,255,255,0.05);
  color: var(--text-secondary);
}

/* 数值控制器 */
.num-ctrl {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--border);
  border-radius: 7px;
  padding: 2px 10px;
}

.num-ctrl button {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0;
  transition: color 0.15s;
}

.num-ctrl button:hover { color: #a78bfa; }

.num-ctrl span {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 16px;
  text-align: center;
}

.audit-run-btn {
  width: 100%;
  justify-content: center;
  padding: 10px;
  background: rgba(167,139,250,0.12) !important;
  border-color: rgba(167,139,250,0.3) !important;
  color: #a78bfa !important;
}

.audit-run-btn:hover:not(:disabled) {
  background: rgba(167,139,250,0.22) !important;
  box-shadow: 0 0 12px rgba(167,139,250,0.25) !important;
}

/* 审核进度条 */
.audit-progress-wrap {
  margin-top: 12px;
  background: rgba(255,255,255,0.06);
  border-radius: 99px;
  height: 6px;
  overflow: hidden;
  position: relative;
}

.audit-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #7c3aed, #a78bfa);
  border-radius: 99px;
  transition: width 0.3s ease;
}

.audit-progress-label {
  position: absolute;
  right: 0;
  top: 10px;
  font-size: 11px;
  color: var(--text-muted);
}

/* ── 审核结果抽屉 ─────────────────────────────────────────────────────────── */
.audit-report { padding: 4px 0; }

.audit-summary {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.audit-stat {
  flex: 1;
  text-align: center;
  padding: 12px 8px;
  border-radius: 8px;
  border: 1px solid;
}

.audit-stat.pass   { background: rgba(52,211,153,0.08); border-color: rgba(52,211,153,0.25); }
.audit-stat.fail   { background: rgba(248,113,113,0.08); border-color: rgba(248,113,113,0.25); }
.audit-stat.uncertain { background: rgba(251,191,36,0.08); border-color: rgba(251,191,36,0.25); }

.audit-stat-num {
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
}

.pass .audit-stat-num   { color: #34d399; }
.fail .audit-stat-num   { color: #f87171; }
.uncertain .audit-stat-num { color: #fbbf24; }

.audit-stat-label { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

.audit-msg {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 12px;
  line-height: 1.6;
}

.audit-deleted-tip {
  font-size: 12px;
  color: #34d399;
  background: rgba(52,211,153,0.08);
  border: 1px solid rgba(52,211,153,0.2);
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
}

.audit-result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.audit-result-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  background: rgba(255,255,255,0.02);
}

.audit-result-item.pass      { border-left: 3px solid #34d399; }
.audit-result-item.fail      { border-left: 3px solid #f87171; }
.audit-result-item.uncertain { border-left: 3px solid #fbbf24; }

.audit-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.audit-verdict-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pass      .audit-verdict-dot { background: #34d399; }
.fail      .audit-verdict-dot { background: #f87171; }
.uncertain .audit-verdict-dot { background: #fbbf24; }

.audit-result-name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-verdict-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 99px;
  flex-shrink: 0;
}

.pass      .audit-verdict-badge { background: rgba(52,211,153,0.12); color: #34d399; }
.fail      .audit-verdict-badge { background: rgba(248,113,113,0.12); color: #f87171; }
.uncertain .audit-verdict-badge { background: rgba(251,191,36,0.12);  color: #fbbf24; }

.audit-result-reason {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 4px;
  line-height: 1.6;
}

.audit-result-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.audit-delete-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  font-size: 12px;
  background: rgba(248,113,113,0.08);
  border: 1px solid rgba(248,113,113,0.25);
  border-radius: 6px;
  color: #f87171;
  cursor: pointer;
  transition: all 0.15s;
}

.audit-delete-btn:hover:not(:disabled) {
  background: rgba(248,113,113,0.15);
}

.audit-delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
