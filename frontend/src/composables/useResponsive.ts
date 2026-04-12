import { ref, onMounted, onUnmounted } from 'vue'

const MOBILE_BREAKPOINT = 768
const SWIPE_THRESHOLD = 50

const isMobile = ref(false)
const sidebarOpen = ref(false)

function update() {
  isMobile.value = window.innerWidth <= MOBILE_BREAKPOINT
  if (!isMobile.value) {
    sidebarOpen.value = false
  }
}

let initialized = false
let touchStartX = 0
let touchStartY = 0

function handleTouchStart(e: TouchEvent) {
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}

function handleTouchEnd(e: TouchEvent) {
  if (!isMobile.value) return
  const dx = e.changedTouches[0].clientX - touchStartX
  const dy = e.changedTouches[0].clientY - touchStartY

  // Only handle horizontal swipes (ignore vertical scrolling)
  if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dy) > Math.abs(dx)) return

  if (dx > 0 && touchStartX < 30 && !sidebarOpen.value) {
    // Swipe right from left edge → open
    sidebarOpen.value = true
  } else if (dx < 0 && sidebarOpen.value) {
    // Swipe left → close
    sidebarOpen.value = false
  }
}

export function useResponsive() {
  if (!initialized) {
    update()
    initialized = true
  }

  onMounted(() => {
    window.addEventListener('resize', update)
    document.addEventListener('touchstart', handleTouchStart, { passive: true })
    document.addEventListener('touchend', handleTouchEnd, { passive: true })
    update()
  })

  onUnmounted(() => {
    window.removeEventListener('resize', update)
    document.removeEventListener('touchstart', handleTouchStart)
    document.removeEventListener('touchend', handleTouchEnd)
  })

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function closeSidebar() {
    sidebarOpen.value = false
  }

  return {
    isMobile,
    sidebarOpen,
    toggleSidebar,
    closeSidebar,
  }
}
