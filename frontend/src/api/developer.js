import http from './index'

// 开发者接口
export const developerApi = {
  // 系统技术指标
  metrics: () => http.get('/developer/metrics'),

  // 性能日志
  performanceLogs: (limit = 100) => http.get('/developer/performance-logs', { params: { limit } }),

  // 命中率趋势
  hitRateTrend: (hours = 1) => http.get('/developer/hit-rate-trend', { params: { hours } }),

  // 推理统计
  inferenceStats: (hours = 1) => http.get('/developer/inference-stats', { params: { hours } }),

  // 查询类型分布
  queryTypes: () => http.get('/developer/query-types'),

  // RAG流程耗时
  ragTiming: () => http.get('/developer/rag-timing'),

  // 知识图谱
  knowledgeGraph: (limit = 50) => http.get('/developer/knowledge-graph', { params: { limit } }),
}
