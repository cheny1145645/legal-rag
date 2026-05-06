<template>
  <div class="pending-pool-view">
    <div class="page-header">
      <div class="page-title-row">
        <div class="page-icon"><el-icon size="18"><FolderOpened /></el-icon></div>
        <div>
          <h2>暂存池管理</h2>
          <p>管理待评估的网络搜索结果</p>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-icon total">
              <el-icon :size="28"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">总文档数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-icon pending">
              <el-icon :size="28"><Clock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.pending }}</div>
              <div class="stat-label">待评估</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-icon keep">
              <el-icon :size="28"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.keep }}</div>
              <div class="stat-label">建议保留</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-icon discard">
              <el-icon :size="28"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.discard }}</div>
              <div class="stat-label">建议丢弃</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <div class="toolbar">
      <el-radio-group v-model="statusFilter" @change="loadDocuments">
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button label="pending">待评估</el-radio-button>
        <el-radio-button label="keep">建议保留</el-radio-button>
        <el-radio-button label="discard">建议丢弃</el-radio-button>
      </el-radio-group>

      <el-button-group>
        <el-button :icon="Refresh" @click="refresh" :loading="loading">刷新</el-button>
        <el-button
          type="primary"
          :icon="MagicStick"
          @click="handleEvaluate"
          :loading="evaluating"
          :disabled="stats.pending === 0"
        >开始鉴别（{{ stats.pending }}条待评估）</el-button>
        <el-button :icon="Delete" type="danger" @click="handleClear">清空</el-button>
      </el-button-group>
    </div>

    <!-- 文档列表 -->
    <el-card class="document-list-card">
      <el-table :data="documents" v-loading="loading" stripe>
        <el-table-column prop="id" label="文档ID" width="200" show-overflow-tooltip />
        <el-table-column prop="query" label="查询内容" width="150" show-overflow-tooltip />
        <el-table-column prop="source_url" label="来源URL" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(getRowStatus(row))">
              {{ getStatusText(getRowStatus(row)) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="relevance_score" label="相关度" width="100">
          <template #default="{ row }">
            {{ (row.relevance_score * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="quality_score" label="质量评分" width="100">
          <template #default="{ row }">
            {{ row.quality_score ? (row.quality_score * 100).toFixed(1) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="evaluation_time" label="评估时间" width="180">
          <template #default="{ row }">
            {{ row.evaluation_time ? formatTime(row.evaluation_time) : '未评估' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button :icon="View" size="small" @click="viewDetail(row)">查看</el-button>
            <el-button
              v-if="row.should_keep === null || row.should_keep === undefined"
              size="small"
              type="success"
              @click="manualAction(row.id, 'keep')"
            >保留</el-button>
            <el-button
              v-if="row.should_keep === null || row.should_keep === undefined"
              size="small"
              type="warning"
              @click="manualAction(row.id, 'discard')"
            >丢弃</el-button>
            <el-button 
              :icon="Delete" 
              size="small" 
              type="danger" 
              @click="deleteDocument(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && documents.length === 0" description="暂无文档" />
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="文档详情" width="70%">
      <div v-if="currentDoc" class="detail-content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文档ID" :span="2">
            {{ currentDoc.id }}
          </el-descriptions-item>
          <el-descriptions-item label="查询内容" :span="2">
            {{ currentDoc.query }}
          </el-descriptions-item>
          <el-descriptions-item label="来源URL" :span="2">
            <a :href="currentDoc.source_url" target="_blank">{{ currentDoc.source_url }}</a>
          </el-descriptions-item>
          <el-descriptions-item label="状态" :span="2">
            <el-tag :type="getStatusType(getRowStatus(currentDoc))">
              {{ getStatusText(getRowStatus(currentDoc)) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="相关度" :span="2">
            {{ (currentDoc.relevance_score * 100).toFixed(1) }}%
          </el-descriptions-item>
          <el-descriptions-item label="质量评分" :span="2">
            {{ currentDoc.quality_score ? (currentDoc.quality_score * 100).toFixed(1) + '%' : '未评估' }}
          </el-descriptions-item>
          <el-descriptions-item label="爬取时间" :span="2">
            {{ formatTime(currentDoc.crawl_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="评估时间" :span="2">
            {{ currentDoc.evaluation_time ? formatTime(currentDoc.evaluation_time) : '未评估' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>文档内容</el-divider>
        <div class="doc-content">
          {{ currentDoc.content }}
        </div>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button
          v-if="currentDoc && currentDoc.should_keep === null || currentDoc && currentDoc.should_keep === undefined"
          type="success"
          @click="manualAction(currentDoc.id, 'keep')"
        >
          手动保留
        </el-button>
        <el-button
          v-if="currentDoc && currentDoc.should_keep === null || currentDoc && currentDoc.should_keep === undefined"
          type="warning"
          @click="manualAction(currentDoc.id, 'discard')"
        >
          手动丢弃
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  FolderOpened,
  Document,
  Clock,
  CircleCheck,
  CircleClose,
  Refresh,
  Delete,
  View,
  MagicStick
} from '@element-plus/icons-vue'
import { pendingPoolApi } from '@/api'

// 响应式数据
const stats = ref({ total: 0, pending: 0, keep: 0, discard: 0 })
const documents = ref([])
const statusFilter = ref('all')
const loading = ref(false)
const evaluating = ref(false)
const detailDialogVisible = ref(false)
const currentDoc = ref(null)

// 加载统计信息
const loadStats = async () => {
  try {
    const data = await pendingPoolApi.getStats()
    stats.value = data
  } catch (error) {
    console.error('加载统计信息失败:', error)
    ElMessage.error('加载统计信息失败')
  }
}

// 加载文档列表
const loadDocuments = async () => {
  try {
    loading.value = true

    const status = statusFilter.value === 'all' ? null : statusFilter.value
    const data = await pendingPoolApi.listDocuments({ status, limit: 100 })
    documents.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('加载文档列表失败:', error)
    ElMessage.error('加载文档列表失败')
    documents.value = []
  } finally {
    loading.value = false
  }
}

// 刷新
const refresh = async () => {
  await Promise.all([loadStats(), loadDocuments()])
  ElMessage.success('刷新成功')
}

// 开始 AI 鉴别
const handleEvaluate = async () => {
  try {
    await ElMessageBox.confirm(
      `将对 ${stats.value.pending} 条待评估文档进行 AI 鉴别，完成后自动更新状态，是否继续？`,
      '开始鉴别',
      {
        confirmButtonText: '开始',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    evaluating.value = true
    const result = await pendingPoolApi.evaluatePending({ limit: stats.value.pending || 10 })
    ElMessage.success(result.message || '鉴别任务已启动，请稍后刷新查看结果')
    // 5秒后自动刷新一次
    setTimeout(() => refresh(), 5000)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('开始鉴别失败:', error)
      ElMessage.error('启动鉴别失败，请检查后端服务')
    }
  } finally {
    evaluating.value = false
  }
}

// 查看详情
const viewDetail = async (doc) => {
  try {
    const data = await pendingPoolApi.getDocument(doc.id)
    currentDoc.value = data
    detailDialogVisible.value = true
  } catch (error) {
    console.error('加载文档详情失败:', error)
    ElMessage.error('加载文档详情失败')
  }
}

// 手动操作
const manualAction = async (docId, action) => {
  try {
    await ElMessageBox.confirm(
      `确定要${action === 'keep' ? '保留' : '丢弃'}这个文档吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: action === 'keep' ? 'success' : 'warning'
      }
    )

    const reason = prompt(`请输入操作原因（可选）：`, '')
    await pendingPoolApi.manualAction(docId, action, reason || '')

    ElMessage.success(`${action === 'keep' ? '保留' : '丢弃'}成功`)
    await refresh()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('手动操作失败:', error)
      ElMessage.error('操作失败')
    }
  }
}

// 删除文档
const deleteDocument = async (docId) => {
  try {
    await ElMessageBox.confirm('确定要删除这个文档吗？', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await pendingPoolApi.deleteDocument(docId)
    ElMessage.success('删除成功')
    await refresh()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除文档失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 清空暂存池
const handleClear = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要清空暂存池吗？这将删除所有 ${stats.value.total} 个文档。`,
      '确认清空',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await pendingPoolApi.clearPool()
    ElMessage.success('清空成功')
    await refresh()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('清空暂存池失败:', error)
      ElMessage.error('清空失败')
    }
  }
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 根据 should_keep 字段计算行状态字符串
const getRowStatus = (row) => {
  if (!row) return 'pending'
  if (row.should_keep === true) return 'keep'
  if (row.should_keep === false) return 'discard'
  return 'pending'
}

// 获取状态类型
const getStatusType = (status) => {
  const typeMap = {
    'pending': 'warning',
    'keep': 'success',
    'discard': 'danger'
  }
  return typeMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const textMap = {
    'pending': '待评估',
    'keep': '建议保留',
    'discard': '建议丢弃'
  }
  return textMap[status] || '未知'
}

// 组件挂载
onMounted(() => {
  loadStats()
  loadDocuments()
})
</script>

<style scoped>
.pending-pool-view {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.page-title-row h2 {
  margin: 0;
  font-size: 24px;
  color: var(--text-primary);
}

.page-title-row p {
  margin: 4px 0 0 0;
  font-size: 14px;
  color: var(--text-muted);
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-icon.pending {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
}

.stat-icon.keep {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
}

.stat-icon.discard {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  color: white;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 4px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.document-list-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.doc-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-content {
  max-height: 70vh;
  overflow-y: auto;
}
</style>
