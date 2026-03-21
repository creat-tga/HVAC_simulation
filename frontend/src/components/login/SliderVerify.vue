<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  success: []
}>()

const verified = ref(false)
const dragging = ref(false)
const offsetX = ref(0)
const trackWidth = ref(0)
const trackRef = ref<HTMLElement | null>(null)
const startX = ref(0)

const THRESHOLD = 0.9 // 90% of track width to succeed

function onMouseDown(e: MouseEvent) {
  if (verified.value) return
  dragging.value = true
  startX.value = e.clientX
  if (trackRef.value) {
    trackWidth.value = trackRef.value.offsetWidth - 44
  }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function onTouchStart(e: TouchEvent) {
  if (verified.value) return
  dragging.value = true
  startX.value = e.touches[0].clientX
  if (trackRef.value) {
    trackWidth.value = trackRef.value.offsetWidth - 44
  }
  document.addEventListener('touchmove', onTouchMove, { passive: false })
  document.addEventListener('touchend', onTouchEnd)
}

function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  const dx = e.clientX - startX.value
  offsetX.value = Math.max(0, Math.min(dx, trackWidth.value))
}

function onTouchMove(e: TouchEvent) {
  if (!dragging.value) return
  e.preventDefault()
  const dx = e.touches[0].clientX - startX.value
  offsetX.value = Math.max(0, Math.min(dx, trackWidth.value))
}

function onMouseUp() {
  finishDrag()
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
}

function onTouchEnd() {
  finishDrag()
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
}

function finishDrag() {
  dragging.value = false
  if (trackWidth.value > 0 && offsetX.value / trackWidth.value >= THRESHOLD) {
    verified.value = true
    offsetX.value = trackWidth.value
    emit('success')
  } else {
    offsetX.value = 0
  }
}
</script>

<template>
  <div class="slider-verify" ref="trackRef">
    <div class="slider-track" :class="{ verified }">
      <div class="slider-fill" :style="{ width: offsetX + 'px' }" />
      <span class="slider-hint" v-if="!verified">{{ '请拖动滑块完成验证' }}</span>
      <span class="slider-hint success" v-else>✓ {{ '验证通过' }}</span>
    </div>
    <div
      class="slider-thumb"
      :class="{ dragging, verified }"
      :style="{ left: offsetX + 'px' }"
      @mousedown="onMouseDown"
      @touchstart="onTouchStart"
    >
      <span v-if="!verified">→</span>
      <span v-else>✓</span>
    </div>
  </div>
</template>

<style scoped>
.slider-verify {
  position: relative;
  width: 100%;
  height: 44px;
  user-select: none;
}

.slider-track {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 44px;
  background: #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.slider-track.verified {
  background: #f0f9eb;
}

.slider-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: #d9ecff;
  transition: none;
}

.slider-track.verified .slider-fill {
  background: #e1f3d8;
}

.slider-hint {
  position: relative;
  z-index: 1;
  font-size: 14px;
  color: #999;
  pointer-events: none;
}

.slider-hint.success {
  color: #67c23a;
  font-weight: 600;
}

.slider-thumb {
  position: absolute;
  top: 0;
  width: 44px;
  height: 44px;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  font-size: 18px;
  color: #409eff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
  z-index: 2;
  transition: background 0.3s;
}

.slider-thumb.dragging {
  cursor: grabbing;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

.slider-thumb.verified {
  background: #67c23a;
  border-color: #67c23a;
  color: #fff;
  cursor: default;
}
</style>
