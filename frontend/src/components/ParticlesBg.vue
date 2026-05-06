<template>
  <canvas ref="canvasRef" class="particles-canvas" />
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const canvasRef = ref(null)
let animId = null
let particles = []
let meteors = []
let mouse = { x: -9999, y: -9999 }

const CONFIG = {
  count: 110,
  color: '99, 155, 255',
  lineColor: '99, 155, 255',
  speed: 0.28,
  radius: 1.8,
  lineDistance: 145,
  // 鼠标排斥力
  repelRadius: 100,
  repelStrength: 0.06,
  // 流星配置
  meteorCount: 3,
  meteorSpeed: 4,
}

// 粒子颜色变体（蓝紫系）
const COLORS = [
  '99, 155, 255',   // 蓝
  '139, 92, 246',   // 紫
  '59, 200, 246',   // 青
  '255, 255, 255',  // 白（少量）
]

class Particle {
  constructor(w, h) {
    this.w = w
    this.h = h
    this.reset()
  }
  reset() {
    this.x = Math.random() * this.w
    this.y = Math.random() * this.h
    this.vx = (Math.random() - 0.5) * CONFIG.speed
    this.vy = (Math.random() - 0.5) * CONFIG.speed
    this.r = Math.random() * CONFIG.radius + 0.4
    this.baseAlpha = Math.random() * 0.45 + 0.15
    this.alpha = this.baseAlpha
    this.color = COLORS[Math.floor(Math.random() * COLORS.length)]
    // 呼吸闪烁参数
    this.breathPhase = Math.random() * Math.PI * 2
    this.breathSpeed = 0.012 + Math.random() * 0.018
  }
  move() {
    // 鼠标排斥
    const dx = this.x - mouse.x
    const dy = this.y - mouse.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist < CONFIG.repelRadius && dist > 0) {
      const force = (CONFIG.repelRadius - dist) / CONFIG.repelRadius
      this.vx += (dx / dist) * force * CONFIG.repelStrength
      this.vy += (dy / dist) * force * CONFIG.repelStrength
    }

    // 速度阻尼，防止无限加速
    this.vx *= 0.997
    this.vy *= 0.997

    this.x += this.vx
    this.y += this.vy

    if (this.x < 0 || this.x > this.w) this.vx *= -1
    if (this.y < 0 || this.y > this.h) this.vy *= -1

    // 呼吸闪烁
    this.breathPhase += this.breathSpeed
    this.alpha = this.baseAlpha + Math.sin(this.breathPhase) * 0.12
  }
}

class Meteor {
  constructor(w, h) {
    this.w = w
    this.h = h
    this.reset()
  }
  reset() {
    // 从上方或左方随机射入
    this.x = Math.random() * this.w * 1.5
    this.y = -20
    this.len = 80 + Math.random() * 120
    this.speed = CONFIG.meteorSpeed + Math.random() * 3
    this.alpha = 0.6 + Math.random() * 0.4
    this.angle = Math.PI / 4 + (Math.random() - 0.5) * 0.3
    this.active = false
    this.timer = Math.random() * 300  // 随机延迟出现
  }
  tick() {
    if (!this.active) {
      this.timer--
      if (this.timer <= 0) this.active = true
      return false
    }
    this.x += Math.cos(this.angle) * this.speed
    this.y += Math.sin(this.angle) * this.speed
    // 超出屏幕则重置
    if (this.x > this.w + 100 || this.y > this.h + 100) {
      this.reset()
    }
    return true
  }
  draw(ctx) {
    if (!this.active) return
    const ex = this.x - Math.cos(this.angle) * this.len
    const ey = this.y - Math.sin(this.angle) * this.len
    const gradient = ctx.createLinearGradient(ex, ey, this.x, this.y)
    gradient.addColorStop(0, `rgba(200, 220, 255, 0)`)
    gradient.addColorStop(1, `rgba(200, 220, 255, ${this.alpha})`)
    ctx.beginPath()
    ctx.strokeStyle = gradient
    ctx.lineWidth = 1.5
    ctx.moveTo(ex, ey)
    ctx.lineTo(this.x, this.y)
    ctx.stroke()
  }
}

onMounted(() => {
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')

  const onMouseMove = (e) => {
    mouse.x = e.clientX
    mouse.y = e.clientY
  }
  const onMouseLeave = () => {
    mouse.x = -9999
    mouse.y = -9999
  }

  const resize = () => {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    particles = Array.from({ length: CONFIG.count }, () =>
      new Particle(canvas.width, canvas.height)
    )
    meteors = Array.from({ length: CONFIG.meteorCount }, () =>
      new Meteor(canvas.width, canvas.height)
    )
  }

  const draw = () => {
    const { width: w, height: h } = canvas
    ctx.clearRect(0, 0, w, h)

    // ── 连线（带渐变色） ──────────────────────────────────────────────────────
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < CONFIG.lineDistance) {
          const alpha = (1 - dist / CONFIG.lineDistance) * 0.22
          const lineGrad = ctx.createLinearGradient(
            particles[i].x, particles[i].y,
            particles[j].x, particles[j].y,
          )
          lineGrad.addColorStop(0, `rgba(${particles[i].color}, ${alpha})`)
          lineGrad.addColorStop(1, `rgba(${particles[j].color}, ${alpha})`)
          ctx.beginPath()
          ctx.strokeStyle = lineGrad
          ctx.lineWidth = 0.7
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.stroke()
        }
      }
    }

    // ── 粒子（带光晕） ────────────────────────────────────────────────────────
    particles.forEach(p => {
      p.move()
      // 外层柔和光晕
      const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4)
      glow.addColorStop(0, `rgba(${p.color}, ${p.alpha * 0.5})`)
      glow.addColorStop(1, `rgba(${p.color}, 0)`)
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r * 4, 0, Math.PI * 2)
      ctx.fillStyle = glow
      ctx.fill()
      // 核心实心粒子
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${p.color}, ${p.alpha})`
      ctx.fill()
    })

    // ── 流星 ──────────────────────────────────────────────────────────────────
    meteors.forEach(m => {
      m.tick()
      m.draw(ctx)
    })

    animId = requestAnimationFrame(draw)
  }

  window.addEventListener('resize', resize)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseleave', onMouseLeave)
  resize()
  draw()

  onUnmounted(() => {
    cancelAnimationFrame(animId)
    window.removeEventListener('resize', resize)
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseleave', onMouseLeave)
  })
})
</script>

<style scoped>
.particles-canvas {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.85;
}
</style>
