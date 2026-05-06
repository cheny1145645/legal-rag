<template>
  <div class="developer-container">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon class="title-icon"><Monitor /></el-icon>
        开发者监控
      </h1>
      <div class="header-actions">
        <el-button @click="refreshLogs" size="default" :icon="Refresh">
          刷新数据
        </el-button>
        <el-button @click="exportLogs" type="primary" size="default" :icon="Download">
          导出日志
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-icon class="loading-icon" :size="60"><Loading /></el-icon>
      <p class="loading-text">正在加载监控数据...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-container">
      <el-icon class="error-icon" :size="60"><WarningFilled /></el-icon>
      <p class="error-text">{{ error }}</p>
      <el-button @click="retryLoading" type="primary" :icon="Refresh">
        重试
      </el-button>
    </div>

    <!-- 主内容 -->
    <div v-else class="dashboard-content">
      <!-- 技术指标卡片 -->
      <el-row :gutter="16" class="metrics-row">
        <el-col :span="4" v-for="(metric, index) in metrics" :key="index">
          <div class="metric-card">
            <div class="metric-icon" :style="{ background: metric.color }">
              <el-icon :size="28"><component :is="metric.icon" /></el-icon>
            </div>
            <div class="metric-info">
              <p class="metric-value">{{ metric.value }}</p>
              <p class="metric-label">{{ metric.label }}</p>
              <p class="metric-trend" :class="metric.trend > 0 ? 'trend-up' : 'trend-down'">
                {{ metric.trend > 0 ? '↑' : '↓' }} {{ Math.abs(metric.trend) }}%
              </p>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 图表区域 -->
      <el-row :gutter="16" class="charts-row">
        <!-- 命中率监控 -->
        <el-col :span="12">
          <div class="chart-card">
            <div class="chart-header">
              <h3 class="chart-title">命中率实时监控</h3>
              <el-tag type="success" size="small">实时</el-tag>
            </div>
            <div ref="hitRateChartRef" class="chart-body"></div>
          </div>
        </el-col>

        <!-- 检索性能对比 -->
        <el-col :span="12">
          <div class="chart-card">
            <div class="chart-header">
              <h3 class="chart-title">检索性能对比</h3>
              <el-tag type="info" size="small">平均</el-tag>
            </div>
            <div ref="retrievalPerfChartRef" class="chart-body"></div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="charts-row">
        <!-- 查询类型分布 -->
        <el-col :span="8">
          <div class="chart-card">
            <div class="chart-header">
              <h3 class="chart-title">查询类型分布</h3>
              <el-tag type="info" size="small">7天</el-tag>
            </div>
            <div ref="queryTypeChartRef" class="chart-body"></div>
          </div>
        </el-col>

        <!-- 模型推理波动 -->
        <el-col :span="8">
          <div class="chart-card">
            <div class="chart-header">
              <h3 class="chart-title">模型推理波动</h3>
              <el-radio-group v-model="inferenceTimeRange" size="small">
                <el-radio-button value="1h">1小时</el-radio-button>
                <el-radio-button value="24h">24小时</el-radio-button>
              </el-radio-group>
            </div>
            <div ref="inferenceChartRef" class="chart-body"></div>
          </div>
        </el-col>

        <!-- RAG流程耗时 -->
        <el-col :span="8">
          <div class="chart-card">
            <div class="chart-header">
              <h3 class="chart-title">RAG流程耗时</h3>
              <el-tag type="warning" size="small">占比</el-tag>
            </div>
            <div ref="ragTimingChartRef" class="chart-body"></div>
          </div>
        </el-col>
      </el-row>

      <!-- 专业级知识图谱可视化 -->
      <el-row :gutter="16" class="charts-row">
        <el-col :span="24">
          <div class="chart-card kg-card">
            <div class="chart-header">
              <h3 class="chart-title">
                <el-icon><Connection /></el-icon>
                法律知识图谱可视化
              </h3>
              <div class="kg-controls">
                <el-select v-model="selectedDomain" size="small" @change="updateKG" style="width: 150px; margin-right: 10px;">
                  <el-option label="劳动法" value="labor"></el-option>
                  <el-option label="合同法" value="contract"></el-option>
                  <el-option label="侵权法" value="tort"></el-option>
                  <el-option label="刑法" value="criminal"></el-option>
                </el-select>
                <el-button size="small" @click="resetKGView">重置视图</el-button>
              </div>
            </div>
            <div class="kg-container">
              <div class="kg-legend">
                <div class="legend-item">
                  <span class="legend-color" style="background: #1890ff;"></span>
                  <span>核心概念</span>
                </div>
                <div class="legend-item">
                  <span class="legend-color" style="background: #52c41a;"></span>
                  <span>法律条款</span>
                </div>
                <div class="legend-item">
                  <span class="legend-color" style="background: #fa8c16;"></span>
                  <span>案例判例</span>
                </div>
                <div class="legend-item">
                  <span class="legend-color" style="background: #722ed1;"></span>
                  <span>法理原则</span>
                </div>
              </div>
              <div ref="kgChartRef" class="chart-body kg-body"></div>
              <div class="kg-stats">
                <div class="stat-item">
                  <span class="stat-label">节点数:</span>
                  <span class="stat-value">{{ kgStats.nodes }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">边数:</span>
                  <span class="stat-value">{{ kgStats.edges }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">连接密度:</span>
                  <span class="stat-value">{{ kgStats.density }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 性能日志表格 -->
      <div class="logs-section">
        <div class="logs-header">
          <h3 class="logs-title">性能日志</h3>
          <div class="logs-actions">
            <el-input
              v-model="searchQuery"
              placeholder="搜索查询内容..."
              size="small"
              style="width: 200px;"
              :prefix-icon="Search"
            />
            <el-select v-model="statusFilter" size="small" placeholder="状态" style="width: 100px; margin-left: 10px;">
              <el-option label="全部" value=""></el-option>
              <el-option label="成功" value="success"></el-option>
              <el-option label="失败" value="error"></el-option>
            </el-select>
          </div>
        </div>
        <el-table
          :data="filteredLogs"
          stripe
          height="400"
          size="small"
          :header-cell-style="{ background: 'rgba(255, 255, 255, 0.1)', color: '#fff' }"
          :cell-style="{ color: 'rgba(255, 255, 255, 0.9)' }"
        >
          <el-table-column prop="query" label="查询内容" width="300" show-overflow-tooltip />
          <el-table-column prop="latency" label="总耗时" width="100">
            <template #default="{ row }">
              <span :class="row.latency > 2000 ? 'text-danger' : 'text-success'">
                {{ row.latency }}ms
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="hitRate" label="命中率" width="100">
            <template #default="{ row }">
              {{ (row.hitRate * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column prop="retrievalTime" label="检索时间" width="100">
            <template #default="{ row }">
              {{ row.retrievalTime }}ms
            </template>
          </el-table-column>
          <el-table-column prop="llmTime" label="LLM时间" width="100">
            <template #default="{ row }">
              {{ row.llmTime }}ms
            </template>
          </el-table-column>
          <el-table-column prop="tokens" label="Token数" width="100" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                {{ row.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import {
  Monitor,
  Refresh,
  Download,
  Loading,
  WarningFilled,
  Document,
  Timer,
  Aim,
  Histogram,
  Connection,
  Search
} from '@element-plus/icons-vue'
import { systemApi } from '@/api'
import { ElMessage } from 'element-plus'

// 懒加载 echarts
let echarts = null

// 响应式数据
const loading = ref(true)
const error = ref(null)
const stats = ref({})
const performance = ref({
  hitRate: 0.78,
  avgLatency: 1200,
  qps: 5,
  memoryUsage: 3800,
  gpuMemory: 4.2
})
const performanceLogs = ref([])
const searchQuery = ref('')
const statusFilter = ref('')
const inferenceTimeRange = ref('1h')
const selectedDomain = ref('labor')
const kgStats = ref({ nodes: 0, edges: 0, density: 0 })

// 技术指标
const metrics = computed(() => [
  {
    label: '知识库文档',
    value: stats.value.totalDocs || 12708,
    icon: Document,
    color: '#1890ff',
    trend: 3.2
  },
  {
    label: '检索命中率',
    value: (performance.value.hitRate * 100).toFixed(1) + '%',
    icon: Aim,
    color: '#52c41a',
    trend: 1.5
  },
  {
    label: '平均响应时间',
    value: performance.value.avgLatency + 'ms',
    icon: Timer,
    color: '#fa8c16',
    trend: -5.2
  },
  {
    label: '图谱节点数',
    value: kgStats.value.nodes || 486,
    icon: Histogram,
    color: '#722ed1',
    trend: 2.1
  },
  {
    label: '实时QPS',
    value: performance.value.qps,
    icon: Timer,
    color: '#eb2f96',
    trend: 0.8
  },
  {
    label: '内存占用',
    value: (performance.value.memoryUsage / 1024).toFixed(1) + 'GB',
    icon: Histogram,
    color: '#13c2c2',
    trend: -1.2
  }
])

// 过滤后的日志
const filteredLogs = computed(() => {
  let logs = performanceLogs.value
  if (searchQuery.value) {
    logs = logs.filter(log => log.query.includes(searchQuery.value))
  }
  if (statusFilter.value) {
    logs = logs.filter(log => log.status === statusFilter.value)
  }
  return logs
})

// 图表引用
const hitRateChartRef = ref(null)
const retrievalPerfChartRef = ref(null)
const queryTypeChartRef = ref(null)
const inferenceChartRef = ref(null)
const ragTimingChartRef = ref(null)
const kgChartRef = ref(null)

// 图表实例
let hitRateChartInstance = null
let retrievalPerfChartInstance = null
let queryTypeChartInstance = null
let inferenceChartInstance = null
let ragTimingChartInstance = null
let kgChartInstance = null

// 专业级法律知识图谱数据
const kgDomainData = {
  labor: {
    nodes: [
      // 核心概念
      { id: 'labor_core', name: '劳动合同', category: 0, symbolSize: 60 },
      { id: 'salary_core', name: '工资报酬', category: 0, symbolSize: 55 },
      { id: 'termination_core', name: '合同解除', category: 0, symbolSize: 55 },
      
      // 法律条款
      { id: 'art15', name: '《劳动合同法》第15条', category: 1, symbolSize: 45 },
      { id: 'art20', name: '《劳动合同法》第20条', category: 1, symbolSize: 45 },
      { id: 'art36', name: '《劳动合同法》第36条', category: 1, symbolSize: 45 },
      { id: 'art39', name: '《劳动合同法》第39条', category: 1, symbolSize: 45 },
      { id: 'art40', name: '《劳动合同法》第40条', category: 1, symbolSize: 45 },
      { id: 'art46', name: '《劳动合同法》第46条', category: 1, symbolSize: 45 },
      { id: 'art47', name: '《劳动合同法》第47条', category: 1, symbolSize: 45 },
      { id: 'art51', name: '《劳动合同法》第51条', category: 1, symbolSize: 45 },
      
      // 案例判例
      { id: 'case1', name: '试用期违法解除案', category: 2, symbolSize: 35 },
      { id: 'case2', name: '加班费争议案', category: 2, symbolSize: 35 },
      { id: 'case3', name: '经济补偿金案', category: 2, symbolSize: 35 },
      { id: 'case4', name: '竞业限制违约案', category: 2, symbolSize: 35 },
      
      // 法理原则
      { id: 'principle1', name: '平等就业原则', category: 3, symbolSize: 30 },
      { id: 'principle2', name: '按劳分配原则', category: 3, symbolSize: 30 },
      { id: 'principle3', name: '公平竞争原则', category: 3, symbolSize: 30 },
      { id: 'principle4', name: '保护劳动者原则', category: 3, symbolSize: 30 }
    ],
    links: [
      // 核心概念到法律条款
      { source: 'labor_core', target: 'art15' },
      { source: 'labor_core', target: 'art20' },
      { source: 'labor_core', target: 'art36' },
      { source: 'labor_core', target: 'art39' },
      { source: 'labor_core', target: 'art40' },
      { source: 'labor_core', target: 'art46' },
      { source: 'termination_core', target: 'art36' },
      { source: 'termination_core', target: 'art39' },
      { source: 'termination_core', target: 'art40' },
      { source: 'termination_core', target: 'art46' },
      { source: 'termination_core', target: 'art47' },
      { source: 'salary_core', target: 'art20' },
      { source: 'salary_core', target: 'art51' },
      
      // 法律条款到案例
      { source: 'art20', target: 'case2' },
      { source: 'art39', target: 'case1' },
      { source: 'art46', target: 'case3' },
      { source: 'art47', target: 'case3' },
      { source: 'art36', target: 'case4' },
      
      // 法理原则连接
      { source: 'principle1', target: 'labor_core' },
      { source: 'principle2', target: 'salary_core' },
      { source: 'principle3', target: 'labor_core' },
      { source: 'principle4', target: 'labor_core' },
      
      // 核心概念间关系
      { source: 'labor_core', target: 'salary_core' },
      { source: 'labor_core', target: 'termination_core' },
      { source: 'salary_core', target: 'termination_core' }
    ]
  },
  
  contract: {
    nodes: [
      { id: 'contract_core', name: '合同订立', category: 0, symbolSize: 60 },
      { id: 'performance_core', name: '合同履行', category: 0, symbolSize: 55 },
      { id: 'breach_core', name: '合同违约', category: 0, symbolSize: 55 },
      
      { id: 'contract_art1', name: '《民法典》第465条', category: 1, symbolSize: 45 },
      { id: 'contract_art2', name: '《民法典》第509条', category: 1, symbolSize: 45 },
      { id: 'contract_art3', name: '《民法典》第577条', category: 1, symbolSize: 45 },
      { id: 'contract_art4', name: '《民法典》第585条', category: 1, symbolSize: 45 },
      { id: 'contract_art5', name: '《民法典》第593条', category: 1, symbolSize: 45 },
      
      { id: 'contract_case1', name: '违约金争议案', category: 2, symbolSize: 35 },
      { id: 'contract_case2', name: '解除合同纠纷案', category: 2, symbolSize: 35 },
      { id: 'contract_case3', name: '定金返还案', category: 2, symbolSize: 35 },
      
      { id: 'contract_principle1', name: '意思自治原则', category: 3, symbolSize: 30 },
      { id: 'contract_principle2', name: '诚实信用原则', category: 3, symbolSize: 30 },
      { id: 'contract_principle3', name: '公平原则', category: 3, symbolSize: 30 }
    ],
    links: [
      { source: 'contract_core', target: 'contract_art1' },
      { source: 'performance_core', target: 'contract_art2' },
      { source: 'breach_core', target: 'contract_art3' },
      { source: 'breach_core', target: 'contract_art4' },
      { source: 'breach_core', target: 'contract_art5' },
      { source: 'contract_art3', target: 'contract_case1' },
      { source: 'contract_art5', target: 'contract_case2' },
      { source: 'contract_art4', target: 'contract_case3' },
      { source: 'contract_principle1', target: 'contract_core' },
      { source: 'contract_principle2', target: 'performance_core' },
      { source: 'contract_principle3', target: 'breach_core' },
      { source: 'contract_core', target: 'performance_core' },
      { source: 'performance_core', target: 'breach_core' }
    ]
  },
  
  tort: {
    nodes: [
      { id: 'tort_core', name: '侵权行为', category: 0, symbolSize: 60 },
      { id: 'liability_core', name: '侵权责任', category: 0, symbolSize: 55 },
      { id: 'damages_core', name: '损害赔偿', category: 0, symbolSize: 55 },
      
      { id: 'tort_art1', name: '《民法典》第1165条', category: 1, symbolSize: 45 },
      { id: 'tort_art2', name: '《民法典》第1166条', category: 1, symbolSize: 45 },
      { id: 'tort_art3', name: '《民法典》第1179条', category: 1, symbolSize: 45 },
      { id: 'tort_art4', name: '《民法典》第1184条', category: 1, symbolSize: 45 },
      
      { id: 'tort_case1', name: '交通事故赔偿案', category: 2, symbolSize: 35 },
      { id: 'tort_case2', name: '医疗损害责任案', category: 2, symbolSize: 35 },
      { id: 'tort_case3', name: '产品责任案', category: 2, symbolSize: 35 },
      
      { id: 'tort_principle1', name: '过错责任原则', category: 3, symbolSize: 30 },
      { id: 'tort_principle2', name: '无过错责任原则', category: 3, symbolSize: 30 },
      { id: 'tort_principle3', name: '过错推定原则', category: 3, symbolSize: 30 }
    ],
    links: [
      { source: 'tort_core', target: 'tort_art1' },
      { source: 'tort_core', target: 'tort_art2' },
      { source: 'liability_core', target: 'tort_art1' },
      { source: 'damages_core', target: 'tort_art3' },
      { source: 'damages_core', target: 'tort_art4' },
      { source: 'tort_art1', target: 'tort_case1' },
      { source: 'tort_art2', target: 'tort_case2' },
      { source: 'tort_art3', target: 'tort_case3' },
      { source: 'tort_principle1', target: 'liability_core' },
      { source: 'tort_principle2', target: 'liability_core' },
      { source: 'tort_principle3', target: 'liability_core' },
      { source: 'tort_core', target: 'liability_core' },
      { source: 'liability_core', target: 'damages_core' }
    ]
  },
  
  criminal: {
    nodes: [
      { id: 'crime_core', name: '犯罪构成', category: 0, symbolSize: 60 },
      { id: 'punishment_core', name: '刑罚适用', category: 0, symbolSize: 55 },
      { id: 'procedure_core', name: '刑事程序', category: 0, symbolSize: 55 },
      
      { id: 'criminal_art1', name: '《刑法》第13条', category: 1, symbolSize: 45 },
      { id: 'criminal_art2', name: '《刑法》第14条', category: 1, symbolSize: 45 },
      { id: 'criminal_art3', name: '《刑法》第61条', category: 1, symbolSize: 45 },
      { id: 'criminal_art4', name: '《刑法》第62条', category: 1, symbolSize: 45 },
      { id: 'criminal_art5', name: '《刑事诉讼法》第112条', category: 1, symbolSize: 45 },
      
      { id: 'criminal_case1', name: '故意伤害案', category: 2, symbolSize: 35 },
      { id: 'criminal_case2', name: '盗窃案', category: 2, symbolSize: 35 },
      { id: 'criminal_case3', name: '诈骗案', category: 2, symbolSize: 35 },
      
      { id: 'criminal_principle1', name: '罪刑法定原则', category: 3, symbolSize: 30 },
      { id: 'criminal_principle2', name: '罪责刑相适应原则', category: 3, symbolSize: 30 },
      { id: 'criminal_principle3', name: '法律面前人人平等', category: 3, symbolSize: 30 }
    ],
    links: [
      { source: 'crime_core', target: 'criminal_art1' },
      { source: 'crime_core', target: 'criminal_art2' },
      { source: 'punishment_core', target: 'criminal_art3' },
      { source: 'punishment_core', target: 'criminal_art4' },
      { source: 'procedure_core', target: 'criminal_art5' },
      { source: 'criminal_art1', target: 'criminal_case1' },
      { source: 'criminal_art2', target: 'criminal_case2' },
      { source: 'criminal_art3', target: 'criminal_case3' },
      { source: 'criminal_principle1', target: 'crime_core' },
      { source: 'criminal_principle2', target: 'punishment_core' },
      { source: 'criminal_principle3', target: 'procedure_core' },
      { source: 'crime_core', target: 'punishment_core' },
      { source: 'punishment_core', target: 'procedure_core' }
    ]
  }
}

// 安全的图表初始化
const safeInitChart = async (refEl, initFn, retryCount = 0) => {
  try {
    // 确保echarts已加载
    if (!echarts) {
      echarts = await import('echarts')
    }
    
    // 如果refEl.value为空，等待DOM渲染
    if (!refEl.value) {
      console.log('refEl.value为空，等待DOM渲染, retryCount:', retryCount)
      if (retryCount < 10) {
        await new Promise(resolve => setTimeout(resolve, 100))
        return safeInitChart(refEl, initFn, retryCount + 1)
      } else {
        console.error('重试次数过多，放弃初始化')
        return
      }
    }
    
    await nextTick()
    
    // 检查容器是否存在并有尺寸
    if (refEl.value) {
      const rect = refEl.value.getBoundingClientRect()
      console.log('图表容器尺寸:', rect.width, rect.height)
      
      if (rect.width === 0 || rect.height === 0) {
        // 容器还没有尺寸，等待后重试
        if (retryCount < 10) {
          await new Promise(resolve => setTimeout(resolve, 100))
          return safeInitChart(refEl, initFn, retryCount + 1)
        }
      }
      initFn()
    }
  } catch (err) {
    console.error('图表初始化失败:', err)
  }
}

// 初始化知识图谱
const initKGChart = () => {
  if (!echarts || !kgChartRef.value) return

  kgChartInstance = echarts.init(kgChartRef.value)
  const domainData = kgDomainData[selectedDomain.value]
  
  // 更新统计数据
  kgStats.value = {
    nodes: domainData.nodes.length,
    edges: domainData.links.length,
    density: (domainData.links.length / (domainData.nodes.length * (domainData.nodes.length - 1) / 2) * 100).toFixed(2)
  }

  const categoryNames = ['核心概念', '法律条款', '案例判例', '法理原则']
  const categoryColors = ['#1890ff', '#52c41a', '#fa8c16', '#722ed1']

  kgChartInstance.setOption({
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      backgroundColor: 'rgba(20, 30, 50, 0.95)',
      borderColor: '#4a90e2',
      borderWidth: 1,
      padding: [12, 16],
      textStyle: {
        color: '#fff'
      },
      formatter: (params) => {
        if (params.dataType === 'node') {
          const category = params.data.category || 0
          return `<div style="min-width: 150px;">
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 8px; color: ${categoryColors[category]};">${params.name}</div>
            <div style="color: #aaa; font-size: 13px;">📋 ${categoryNames[category]}</div>
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1);">
              <span style="color: #888;">点击节点查看详情</span>
            </div>
          </div>`
        }
        return ''
      }
    },
    // 添加 toolbox 用于操作
    toolbox: {
      show: true,
      right: 20,
      top: 10,
      feature: {
        restore: { show: true, title: '重置' },
        saveAsImage: { show: true, title: '保存' }
      },
      iconStyle: {
        borderColor: '#4a90e2'
      }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      // 启用拖拽
      draggable: true,
      // 初始布局配置
      initialTreeGraph: true,
      data: domainData.nodes.map(node => ({
        ...node,
        name: node.name,
        label: {
          show: true,
          fontSize: node.symbolSize > 50 ? 14 : 12,
          fontWeight: node.symbolSize > 50 ? 'bold' : 'normal',
          color: '#fff',
          backgroundColor: 'rgba(0,0,0,0.3)',
          borderRadius: 4,
          padding: [4, 8]
        },
        itemStyle: {
          shadowBlur: 15,
          shadowColor: categoryColors[node.category || 0],
          borderColor: '#fff',
          borderWidth: 2
        },
        // 边的动画
        value: node.symbolSize
      })),
      links: domainData.links.map(link => ({
        ...link,
        label: {
          show: false
        },
        lineStyle: {
          color: 'source',
          curveness: 0.2,
          width: 1.5,
          opacity: 0.5
        }
      })),
      // 允许缩放和拖拽
      roam: true,
      // 开启缩放
      scaleLimit: {
        min: 0.5,
        max: 3
      },
      label: { 
        show: true,
        color: '#fff'
      },
      // 力学布局配置
      force: {
        repulsion: 600,
        edgeLength: 150,
        gravity: 0.08,
        layoutAnimation: true
      },
      // 边的样式
      lineStyle: {
        color: 'source',
        curveness: 0.2,
        width: 2,
        opacity: 0.6
      },
      // 鼠标悬停效果
      emphasis: {
        focus: 'adjacency',
        scale: 1.3,
        lineStyle: {
          width: 5,
          color: '#4a90e2',
          opacity: 1
        },
        itemStyle: {
          shadowBlur: 30,
          shadowColor: '#4a90e2',
          borderColor: '#4a90e2',
          borderWidth: 3
        }
      },
      // 选中效果
      select: {
        itemStyle: {
          borderColor: '#ff6b6b',
          borderWidth: 3
        }
      },
      // 节点样式
      itemStyle: {
        color: (params) => {
          const colors = ['#1890ff', '#52c41a', '#fa8c16', '#722ed1']
          return colors[params.data.category || 0]
        }
      },
      // 连接线标签
      edgeLabel: {
        show: false
      }
    }]
  })

  // 添加点击事件 - 点击节点弹出更多信息
  kgChartInstance.on('click', (params) => {
    if (params.dataType === 'node') {
      const category = params.data.category || 0
      ElMessage({
        message: `📌 ${params.name} (${categoryNames[category]})`,
        type: 'info',
        duration: 2000
      })
    }
  })

  // 双击节点放大
  kgChartInstance.on('dblclick', (params) => {
    if (params.dataType === 'node') {
      kgChartInstance.dispatchAction({
        type: 'focusNodeAdjacency',
        dataIndex: params.dataIndex
      })
    }
  })
}

// 更新知识图谱
const updateKG = () => {
  if (kgChartInstance) {
    kgChartInstance.dispose()
    initKGChart()
  }
}

// 重置知识图谱视图
const resetKGView = () => {
  if (kgChartInstance) {
    kgChartInstance.dispatchAction({
      type: 'restore'
    })
  }
}

// 加载数据
const loadData = async () => {
  try {
    loading.value = true
    error.value = null

    try {
      const response = await systemApi.stats()
      stats.value = response
    } catch (apiErr) {
      console.warn('API调用失败，使用默认数据:', apiErr)
      // 使用默认数据
      stats.value = { totalDocs: 12708 }
    }

    generatePerformanceLogs()

    // 先关闭 loading，让 DOM 元素渲染出来
    loading.value = false

    // 等待 DOM 渲染完成
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    // 初始化所有图表（无论API是否成功都初始化）
    await Promise.all([
      safeInitChart(hitRateChartRef, initHitRateChart),
      safeInitChart(retrievalPerfChartRef, initRetrievalPerfChart),
      safeInitChart(queryTypeChartRef, initQueryTypeChart),
      safeInitChart(inferenceChartRef, initInferenceChart),
      safeInitChart(ragTimingChartRef, initRagTimingChart),
      safeInitChart(kgChartRef, initKGChart)
    ])
  } catch (err) {
    console.error('加载失败:', err)
    error.value = '加载监控数据失败，请重试'
    loading.value = false
  }
}

// 命中率图表
const initHitRateChart = () => {
  if (!echarts || !hitRateChartRef.value) return

  hitRateChartInstance = echarts.init(hitRateChartRef.value)
  const times = Array.from({ length: 12 }, (_, i) => `${i * 5}分钟前`)
  const data = times.map(() => 0.72 + Math.random() * 0.15)

  hitRateChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: times.reverse(),
      axisLine: { lineStyle: { color: '#4a90e2' } }
    },
    yAxis: {
      type: 'value',
      min: 0.6,
      max: 0.95,
      axisLabel: { formatter: (val) => (val * 100).toFixed(0) + '%' }
    },
    series: [{
      name: '命中率',
      type: 'line',
      data: data.reverse(),
      smooth: true,
      lineStyle: { color: '#52c41a', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(82, 196, 26, 0.3)' },
          { offset: 1, color: 'rgba(82, 196, 26, 0.05)' }
        ])
      }
    }]
  })
}

// 检索性能图表
const initRetrievalPerfChart = () => {
  if (!echarts || !retrievalPerfChartRef.value) return

  retrievalPerfChartInstance = echarts.init(retrievalPerfChartRef.value)
  const data = [
    { name: '向量检索', value: 120 },
    { name: 'BM25', value: 35 },
    { name: 'Rerank', value: 65 },
    { name: '融合', value: 15 },
    { name: '过滤', value: 8 }
  ]

  retrievalPerfChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(d => d.name),
      axisLine: { lineStyle: { color: '#4a90e2' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}ms' }
    },
    series: [{
      type: 'bar',
      data: data.map(d => ({
        value: d.value,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#4a90e2' },
            { offset: 1, color: '#2c5aa0' }
          ])
        }
      }))
    }]
  })
}

// 查询类型图表
const initQueryTypeChart = () => {
  if (!echarts || !queryTypeChartRef.value) return

  queryTypeChartInstance = echarts.init(queryTypeChartRef.value)
  const data = [
    { name: '劳动合同', value: 35 },
    { name: '工资报酬', value: 25 },
    { name: '社保咨询', value: 20 },
    { name: '工伤认定', value: 12 },
    { name: '其他', value: 8 }
  ]

  queryTypeChartInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: data,
      label: { formatter: '{b}: {c}%' },
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

// 推理波动监控
const initInferenceChart = () => {
  if (!echarts || !inferenceChartRef.value) return

  inferenceChartInstance = echarts.init(inferenceChartRef.value)
  const hours = inferenceTimeRange.value === '1h' ? 12 : 24
  const times = Array.from({ length: hours }, (_, i) =>
    inferenceTimeRange.value === '1h' ? `${i * 5}分钟前` : `${i}小时前`
  )

  inferenceChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['推理时间', 'Token生成速度'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: times.reverse(),
      axisLine: { lineStyle: { color: '#4a90e2' } }
    },
    yAxis: [
      { type: 'value', name: '推理时间(ms)', position: 'left' },
      { type: 'value', name: 'Token/s', position: 'right' }
    ],
    series: [
      {
        name: '推理时间',
        type: 'line',
        data: times.map(() => 400 + Math.random() * 350),
        smooth: true,
        lineStyle: { color: '#fa8c16', width: 2 }
      },
      {
        name: 'Token生成速度',
        type: 'line',
        yAxisIndex: 1,
        data: times.map(() => 16 + Math.random() * 8),
        smooth: true,
        lineStyle: { color: '#52c41a', width: 2 }
      }
    ]
  })
}

// RAG流程耗时
const initRagTimingChart = () => {
  if (!echarts || !ragTimingChartRef.value) return

  ragTimingChartInstance = echarts.init(ragTimingChartRef.value)
  const data = [
    { name: '查询增强', value: 8 },
    { name: '向量检索', value: 7 },
    { name: 'BM25检索', value: 5 },
    { name: 'Rerank重排', value: 4 },
    { name: 'LLM推理', value: 13 },
    { name: '答案生成', value: 3 }
  ]

  ragTimingChartInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
    series: [{
      type: 'pie',
      radius: '65%',
      data: data,
      label: { formatter: '{b}: {c}%' },
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2
      }
    }]
  })
}

// 生成模拟性能日志
const generatePerformanceLogs = () => {
  const queries = [
    '劳动法中关于加班费的规定',
    '劳动合同解除需要什么条件',
    '社保缴纳比例是多少',
    '工伤认定标准是什么',
    '竞业限制期限是多久',
    '试用期工资标准',
    '年假天数如何计算',
    '未签劳动合同赔偿',
  ]

  const logs = []
  for (let i = 0; i < 30; i++) {
    logs.push({
      query: queries[Math.floor(Math.random() * queries.length)],
      latency: Math.floor(600 + Math.random() * 500),
      hitRate: 0.55 + Math.random() * 0.25,
      retrievalTime: Math.floor(80 + Math.random() * 150),
      llmTime: Math.floor(300 + Math.random() * 500),
      tokens: Math.floor(150 + Math.random() * 300),
      status: Math.random() > 0.08 ? 'success' : 'error'
    })
  }
  performanceLogs.value = logs
}

// 刷新日志
const refreshLogs = () => {
  generatePerformanceLogs()
  ElMessage.success('日志已刷新')
}

// 导出日志
const exportLogs = () => {
  const dataStr = JSON.stringify(performanceLogs.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'performance_logs.json'
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('日志已导出')
}

// 重试加载
const retryLoading = () => {
  loadData()
}

// 监听推理时间范围变化
watch(inferenceTimeRange, () => {
  if (inferenceChartInstance) {
    initInferenceChart()
  }
})

// 窗口大小变化时调整图表
const handleResize = () => {
  const charts = [
    hitRateChartInstance,
    retrievalPerfChartInstance,
    queryTypeChartInstance,
    inferenceChartInstance,
    ragTimingChartInstance,
    kgChartInstance
  ]
  charts.forEach(chart => {
    if (chart) {
      chart.resize()
    }
  })
}

onMounted(async () => {
  await loadData()

  // 实时数据更新
  setInterval(async () => {
    try {
      const response = await systemApi.stats()
      stats.value = response
      performance.value = {
        hitRate: 0.72 + Math.random() * 0.12,
        avgLatency: Math.floor(900 + Math.random() * 600),
        qps: Math.floor(3 + Math.random() * 8),
        memoryUsage: Math.floor(3200 + Math.random() * 800),
        gpuMemory: (3.5 + Math.random() * 1.5).toFixed(1)
      }
    } catch (err) {
      console.error('更新数据失败:', err)
    }
  }, 5000)

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  const charts = [
    hitRateChartInstance,
    retrievalPerfChartInstance,
    queryTypeChartInstance,
    inferenceChartInstance,
    ragTimingChartInstance,
    kgChartInstance
  ]
  charts.forEach(chart => {
    if (chart) {
      chart.dispose()
    }
  })
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.developer-container {
  padding: 20px;
  min-height: calc(100vh - 60px);
  background: linear-gradient(135deg, #0a1628 0%, #1a2744 100%);
  color: #ffffff;
  overflow-y: auto;
  overflow-x: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid rgba(74, 144, 226, 0.3);
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  color: #4a90e2;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  gap: 20px;
}

.loading-icon {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
}

.error-icon {
  color: #ff4d4f;
}

.error-text {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
}

.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 0;
}

.metrics-row {
  margin-bottom: 0;
}

.metric-card {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  transition: all 0.3s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
}

.metric-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.metric-info {
  flex: 1;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: #fff;
}

.metric-label {
  font-size: 14px;
  margin: 0 0 4px 0;
  color: rgba(255, 255, 255, 0.7);
}

.metric-trend {
  font-size: 12px;
  margin: 0;
}

.trend-up {
  color: #52c41a;
}

.trend-down {
  color: #ff4d4f;
}

.charts-row {
  margin-bottom: 24px;
}

.chart-card {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  height: 380px;
  display: flex;
  flex-direction: column;
}

.kg-card {
  height: 700px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.kg-controls {
  display: flex;
  align-items: center;
}

.chart-body {
  flex: 1;
  min-height: 0;
  height: 320px;
  min-height: 320px;
}

.kg-body {
  height: 550px;
  min-height: 550px;
}

.kg-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.kg-legend {
  display: flex;
  gap: 20px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  margin-bottom: 12px;
  justify-content: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.legend-color {
  width: 16px;
  height: 16px;
  border-radius: 4px;
}

.kg-stats {
  display: flex;
  gap: 30px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  margin-top: 12px;
  justify-content: center;
}

.stat-item {
  display: flex;
  gap: 8px;
  font-size: 14px;
}

.stat-label {
  color: rgba(255, 255, 255, 0.7);
}

.stat-value {
  font-weight: 600;
  color: #52c41a;
}

.logs-section {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 20px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-top: 24px;
}

.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.logs-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.logs-actions {
  display: flex;
  align-items: center;
}

.text-danger {
  color: #ff4d4f;
}

.text-success {
  color: #52c41a;
}
</style>
