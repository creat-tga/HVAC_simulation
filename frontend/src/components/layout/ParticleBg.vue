<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const canvasRef = ref<HTMLCanvasElement>()
let animationId = 0

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
}

onMounted(() => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  let w = 0
  let h = 0
  const particles: Particle[] = []
  const PARTICLE_COUNT = 60
  const CONNECT_DIST = 180
  const SPEED = 0.5

  function resize() {
    w = canvas!.parentElement!.clientWidth
    h = canvas!.parentElement!.clientHeight
    canvas!.width = w
    canvas!.height = h
  }

  function init() {
    resize()
    particles.length = 0
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * SPEED,
        vy: (Math.random() - 0.5) * SPEED,
        r: Math.random() * 2 + 0.8,
      })
    }
  }

  function draw() {
    ctx!.clearRect(0, 0, w, h)
    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < CONNECT_DIST) {
          const opacity = (1 - dist / CONNECT_DIST) * 0.25
          ctx!.strokeStyle = `rgba(64, 158, 255, ${opacity})`
          ctx!.lineWidth = 0.8
          ctx!.beginPath()
          ctx!.moveTo(particles[i].x, particles[i].y)
          ctx!.lineTo(particles[j].x, particles[j].y)
          ctx!.stroke()
        }
      }
    }
    // Draw particles
    for (const p of particles) {
      ctx!.fillStyle = 'rgba(64, 158, 255, 0.4)'
      ctx!.beginPath()
      ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx!.fill()
    }
  }

  function update() {
    for (const p of particles) {
      p.x += p.vx
      p.y += p.vy
      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1
    }
  }

  function animate() {
    update()
    draw()
    animationId = requestAnimationFrame(animate)
  }

  init()
  animate()

  const ro = new ResizeObserver(resize)
  ro.observe(canvas.parentElement!)
  onBeforeUnmount(() => {
    cancelAnimationFrame(animationId)
    ro.disconnect()
  })
})
</script>

<template>
  <canvas ref="canvasRef" class="particle-bg" />
</template>

<style scoped>
.particle-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
</style>
