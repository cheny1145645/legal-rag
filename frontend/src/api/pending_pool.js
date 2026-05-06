/**
 * 暂存池管理API
 */
import { http } from './index.js'

export const pendingPoolApi = {
  // 获取统计信息
  async getStats() {
    return http.get('/pending/stats')
  },

  // 获取文档列表
  async listDocuments(params = {}) {
    const { status, limit = 50 } = params
    return http.get('/pending/list', { params: { status, limit } })
  },

  // 获取文档详情
  async getDocument(docId) {
    return http.get(`/pending/${docId}`)
  },

  // 手动操作文档
  async manualAction(docId, action, reason = '') {
    return http.post(`/pending/${docId}/action`, { action, reason })
  },

  // 删除文档
  async deleteDocument(docId) {
    return http.delete(`/pending/${docId}`)
  },

  // 触发 AI 鉴别
  async evaluatePending(params = {}) {
    const { limit = 10 } = params
    return http.post('/pending/evaluate', { limit })
  },

  // 清空暂存池
  async clearPool() {
    return http.post('/pending/clear')
  }
}

export default pendingPoolApi
