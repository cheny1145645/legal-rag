<template>
  <div class="about-view">
    <!-- Hero -->
    <div class="hero">
      <div class="hero-glow"></div>
      <div class="hero-icon">
        <el-icon size="44"><ScaleToOriginal /></el-icon>
      </div>
      <h1 class="hero-title">法律咨询智能问答系统</h1>
      <p class="hero-sub">
        基于 RAG 技术与 DeepSeek-R1 本地大模型<br>
        专业、可靠、隐私安全的法律问答平台
      </p>
      <div class="hero-tags">
        <span class="htag" v-for="t in heroTags" :key="t">{{ t }}</span>
      </div>
    </div>

    <!-- 特性卡片 -->
    <div class="features-grid">
      <div class="feature-card" v-for="f in features" :key="f.title">
        <div class="feature-icon" :style="{ background: f.bg, borderColor: f.border }">
          <el-icon size="22" :color="f.color"><component :is="f.icon" /></el-icon>
        </div>
        <h3>{{ f.title }}</h3>
        <p>{{ f.desc }}</p>
      </div>
    </div>

    <!-- 技术架构 -->
    <el-card class="dark-card arch-card">
      <template #header>
        <div class="card-header">
          <el-icon color="#60a5fa"><Grid /></el-icon>
          <span>技术架构</span>
        </div>
      </template>
      <div class="arch-table">
        <div class="arch-row header-row">
          <span>模块</span><span>技术选型</span><span>说明</span>
        </div>
        <div class="arch-row" v-for="r in techStack" :key="r.module">
          <span class="module-tag">{{ r.module }}</span>
          <span class="tech-name">{{ r.tech }}</span>
          <span class="tech-desc">{{ r.desc }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { shallowRef } from 'vue'
import { Search, DataAnalysis, Lock, Grid } from '@element-plus/icons-vue'

const heroTags = ['RAG检索增强', 'DeepSeek-R1', '本地部署', '混合检索', '思维链']

const features = [
  {
    icon: shallowRef(Search),
    title: '混合检索策略',
    desc: '融合BM25关键词检索与BGE-M3向量语义检索，加权融合显著提升法律术语召回准确率',
    color: '#60a5fa', bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.25)',
  },
  {
    icon: shallowRef(DataAnalysis),
    title: 'DeepSeek-R1 推理',
    desc: '本地部署 DeepSeek-R1-8B 蒸馏模型，支持思维链推理过程可视化，答案更可解释',
    color: '#34d399', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.25)',
  },
  {
    icon: shallowRef(Lock),
    title: '本地化隐私保护',
    desc: '全系统本地运行，数据不上传云端，敏感法律咨询内容完全保密，无网络依赖',
    color: '#fbbf24', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.25)',
  },
]

const techStack = [
  { module: '前端',     tech: 'Vue 3 + Element Plus',     desc: '响应式问答界面、知识库管理、粒子背景' },
  { module: '后端',     tech: 'Python + FastAPI',          desc: 'RESTful API，高性能异步服务框架' },
  { module: '大模型',   tech: 'DeepSeek-R1 (Ollama)',      desc: '本地推理，支持思维链，131K上下文' },
  { module: '嵌入模型', tech: 'BAAI/BGE-M3',               desc: '中英文混合语义向量编码，支持GPU加速' },
  { module: '向量库',   tech: 'ChromaDB',                  desc: '本地持久化存储，无需独立服务' },
  { module: '检索框架', tech: 'LangChain + BM25',          desc: '混合检索、法律文本专项处理流水线' },
]
</script>

<style scoped>
.about-view {
  padding: 28px 24px;
  height: 100vh;
  overflow-y: auto;
  background: transparent;
}

/* Hero */
.hero {
  text-align: center;
  padding: 32px 20px 36px;
  position: relative;
  margin-bottom: 28px;
}

.hero-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.08) 0%, transparent 60%);
  pointer-events: none;
}

.hero-icon {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(29,78,216,0.5), rgba(59,130,246,0.3));
  border: 1px solid rgba(59,130,246,0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-light);
  margin: 0 auto 20px;
  box-shadow: 0 0 32px var(--accent-glow);
  animation: borderGlow 3s ease-in-out infinite;
}

.hero-title {
  font-size: 26px;
  font-weight: 800;
  background: linear-gradient(135deg, #e2e8f0 30%, #93c5fd);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 10px;
}

.hero-sub {
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.8;
  margin-bottom: 20px;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.htag {
  font-size: 11px;
  padding: 4px 12px;
  border-radius: 99px;
  background: rgba(59,130,246,0.08);
  border: 1px solid rgba(59,130,246,0.2);
  color: var(--accent-light);
  letter-spacing: 0.5px;
}

/* 特性卡片 */
.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.feature-card {
  padding: 20px;
  background: rgba(17,24,39,0.7);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: var(--transition);
}

.feature-card:hover {
  border-color: var(--border-glow);
  transform: translateY(-3px);
  box-shadow: var(--shadow-glow);
}

.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  border: 1px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}

.feature-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.feature-card p {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.7;
}

/* 架构表 */
.dark-card { background: rgba(17,24,39,0.8) !important; backdrop-filter: blur(12px); }

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.arch-table {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.arch-row {
  display: grid;
  grid-template-columns: 80px 180px 1fr;
  gap: 16px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  align-items: center;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

.arch-row:last-child { border-bottom: none; }

.arch-row:not(.header-row):hover {
  background: rgba(59,130,246,0.04);
}

.header-row {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding-bottom: 8px;
  margin-bottom: 4px;
}

.module-tag {
  color: var(--accent-light);
  font-weight: 600;
  font-size: 12px;
}

.tech-name {
  color: var(--text-primary);
  font-size: 12px;
}

.tech-desc {
  color: var(--text-muted);
  font-size: 12px;
}
</style>
