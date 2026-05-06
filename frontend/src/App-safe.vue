<template>
  <div class="app-root">
    <!-- 临时移除 ParticlesBg 组件进行测试 -->
    <!-- <ParticlesBg /> -->

    <!-- 启动 Loading 遮罩：后端未就绪时显示 -->
    <transition name="boot-fade">
      <div v-if="booting" class="boot-overlay">
        <div class="boot-card">
          <div class="boot-logo">⚖️</div>
          <div class="boot-title">法律智能问答</div>
          <div class="boot-sub">Legal AI Assistant</div>
          <div class="boot-spinner">
            <span class="spin-dot" v-for="i in 3" :key="i" :style="{ animationDelay: (i-1)*0.2 + 's' }"></span>
          </div>
          <div class="boot-msg">{{ bootMsg }}</div>
          <div class="boot-hint">正在加载 BGE-M3 嵌入模型,请稍候…</div>
        </div>
      </div>
    </transition>

    <!-- 布局容器 -->
    <el-container class="layout" v-show="!booting">
      <!-- 侧边栏 -->
      <el-aside width="220px" class="sidebar">
        <!-- Logo -->
        <div class="logo">
          <div class="logo-icon">⚖️</div>
          <div class="logo-text">
            <span class="logo-title">法律智能问答</span>
            <span class="logo-sub">Legal AI Assistant</span>
          </div>
        </div>

        <!-- 导航 -->
        <el-menu
          :default-active="route.path"
          router
          class="nav-menu"
        >
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>法律问答</span>
          </el-menu-item>
          <el-menu-item index="/knowledge">
            <el-icon><FolderOpened /></el-icon>
            <span>知识库管理</span>
          </el-menu-item>
          <el-menu-item index="/analytics">
            <el-icon><DataAnalysis /></el-icon>
            <span>数据统计</span>
          </el-menu-item>
          <el-menu-item index="/about">
            <el-icon><InfoFilled /></el-icon>
            <span>系统介绍</span>
          </el-menu-item>
        </el-menu>

        <!-- 状态面板 -->
        <div class="status-panel">
          <div class="status-title">系统状态</div>
          <div class="status-row">
            <span class="s-label">模型</span>
            <el-tag size="small" type="info">DeepSeek-R1</el-tag>
          </div>
          <div class="status-row">
            <span class="s-label">知识库</span>
            <el-tag size="small" :type="stats.doc_count > 0 ? 'success' : 'warning'">
              {{ stats.doc_count || 0 }} 条
            </el-tag>
          </div>
          <div class="status-row">
            <span class="s-label">服务</span>
            <el-tag size="small" :type="health.status === 'healthy' ? 'success' : 'danger'">
              {{ health.status === 'healthy' ? '正常' : '异常' }}
            </el-tag>
          </div>

          <!-- 在线指示灯 -->
          <div class="online-dot" :class="{ active: health.status === 'healthy' }">
            <span class="dot-pulse"></span>
            <span class="dot-label">{{ health.status === 'healthy' ? '服务在线' : '服务离线' }}</span>
          </div>
        </div>
      </el-aside>

      <!-- 主内容 -->
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { systemApi } from '@/api'
// import ParticlesBg from '@/components/ParticlesBg.vue'  // 暂时注释掉
import {
  ScaleToOriginal,
  ChatDotRound,
  FolderOpened,
  InfoFilled,
  DataAnalysis,
} from '@element-plus/icons-vue'

const route = useRoute()
const health = ref({ status: 'unknown' })
const stats = ref({ doc_count: 0 })

// ── 启动状态 ───────────────────────────────────────────────
const booting = ref(true)
const bootMsg = ref('正在连接后端服务…')

const waitForBackend = async () => {
  let attempts = 0
  const maxAttempts = 40  // 最多等 80 秒(每次 2s)

  while (attempts < maxAttempts) {
    try {
      const h = await systemApi.health()
      if (h && h.status === 'healthy') {
        // 后端就绪,拉取 stats 后关闭遮罩
        try {
          const s = await systemApi.stats()
          stats.value = s
        } catch {}
        health.value = h
        booting.value = false
        // 后续正常轮询
        setInterval(refreshStatus, 30000)
        return
      }
    } catch {
      // 连接拒绝 / 超时,继续重试
    }
    attempts++
    const elapsed = attempts * 2
    bootMsg.value = elapsed < 20
      ? `正在连接后端服务… (${elapsed}s)`
      : elapsed < 50
        ? `模型加载中,请稍候… (${elapsed}s)`
        : `即将就绪… (${elapsed}s)`
    await new Promise(r => setTimeout(r, 2000))
  }

  // 超时后强制进入,让用户自行刷新
  bootMsg.value = '连接超时,请检查后端是否正常启动'
  await new Promise(r => setTimeout(r, 2000))
  booting.value = false
}

const refreshStatus = async () => {
  try {
    const [h, s] = await Promise.all([systemApi.health(), systemApi.stats()])
    health.value = h
    stats.value = s
  } catch {
    health.value = { status: 'error' }
  }
}

onMounted(() => {
  console.log('[App-safe] 组件已挂载')
  waitForBackend()
})
</script>

<style scoped>
.app-root {
  height: 100vh;
  overflow: hidden;
  background: var(--bg-deep);
}

/* ===== 启动遮罩 ===== */
.boot-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(8, 12, 28, 0.97);
  backdrop-filter: blur(20px);
}

.boot-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 60px;
  border-radius: 20px;
  background: rgba(13, 18, 36, 0.9);
  border: 1px solid rgba(59, 130, 246, 0.25);
  box-shadow: 0 0 60px rgba(59, 130, 246, 0.12);
}

.boot-logo {
  width: 72px;
  height: 72px;
  border-radius: 18px;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 36px;
  box-shadow: 0 0 30px rgba(59, 130, 246, 0.5);
}

.boot-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary, #e2e8f0);
  letter-spacing: 1px;
  margin-top: 4px;
}

.boot-sub {
  font-size: 12px;
  color: var(--text-muted, #64748b);
  letter-spacing: 2px;
}

.boot-spinner {
  display: flex;
  gap: 8px;
  margin: 8px 0 4px;
}

.spin-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #3b82f6;
  animation: bounce 1.2s ease-in-out infinite;
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%            { transform: scale(1.2); opacity: 1; }
}

.boot-msg {
  font-size: 13px;
  color: #60a5fa;
  min-height: 20px;
  text-align: center;
  transition: all 0.3s;
}

.boot-hint {
  font-size: 11px;
  color: var(--text-muted, #64748b);
  text-align: center;
}

.boot-fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}
.boot-fade-leave-to {
  opacity: 0;
  transform: scale(1.04);
}

.layout {
  height: 100vh;
  position: relative;
  z-index: 1;
}

/* ===== 侧边栏 ===== */
.sidebar {
  background: rgba(13, 18, 36, 0.85);
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  border-bottom: 1px solid var(--border);
}

.logo-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  flex-shrink: 0;
  box-shadow: 0 0 16px var(--accent-glow);
}

.logo-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.logo-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.logo-sub {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 1px;
}

.nav-menu {
  background: transparent !important;
  flex: 1;
  padding: 8px 0;
}

/* ===== 状态面板 ===== */
.status-panel {
  padding: 16px;
  border-top: 1px solid var(--border);
  background: rgba(0,0,0,0.2);
}

.status-title {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.s-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.online-dot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
}

.dot-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.online-dot.active .dot-pulse {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.6; transform: scale(1.3); }
}

.dot-label {
  font-size: 11px;
  color: var(--text-muted);
}

.online-dot.active .dot-label {
  color: var(--success);
}

/* ===== 主内容 ===== */
.main-content {
  padding: 0;
  overflow: hidden;
  background: transparent;
}

/* 页面切换动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
