import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '@/views/ChatView.vue'
import KnowledgeView from '@/views/KnowledgeView.vue'
import AboutView from '@/views/AboutView.vue'
import AnalyticsView from '@/views/AnalyticsView.vue'
import DeveloperView from '@/views/DeveloperView.vue'
import PendingPoolView from '@/views/PendingPoolView.vue'
import AgentView from '@/views/AgentView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/chat', component: ChatView, meta: { title: '法律问答' } },
    { path: '/agent', component: AgentView, meta: { title: 'Agent 自主模式' } },
    { path: '/knowledge', component: KnowledgeView, meta: { title: '知识库管理' } },
    { path: '/analytics', component: AnalyticsView, meta: { title: '数据统计' } },
    { path: '/developer', component: DeveloperView, meta: { title: '开发者监控' } },
    { path: '/pending', component: PendingPoolView, meta: { title: '暂存池管理' } },
    { path: '/about', component: AboutView, meta: { title: '系统介绍' } },
  ]
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '法律问答'} - 法律咨询智能问答系统`
})

export default router

