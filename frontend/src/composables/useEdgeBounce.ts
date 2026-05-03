import { nextTick, onMounted, onUnmounted, watch, type Ref } from 'vue'

interface EdgeBounceOptions {
  maxOffset?: number
  resistance?: number
  refreshThreshold?: number
  onRefresh?: () => void
}

const MOBILE_QUERY = '(max-width: 768px)'

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function roundProgress(value: number) {
  return Math.round(value * 100) / 100
}

function easeOutCubic(value: number) {
  return 1 - Math.pow(1 - value, 3)
}

function isScrollable(el: HTMLElement) {
  return el.scrollHeight > el.clientHeight + 1
}

function atTop(el: HTMLElement) {
  return el.scrollTop <= 0
}

function atBottom(el: HTMLElement) {
  return el.scrollTop + el.clientHeight >= el.scrollHeight - 1
}

export function useEdgeBounce(target: Ref<HTMLElement | null>, options: EdgeBounceOptions = {}) {
  const maxOffset = options.maxOffset ?? 36
  const resistance = options.resistance ?? 0.36
  const refreshThreshold = options.refreshThreshold ?? 76
  let mediaQuery: MediaQueryList | null = null
  let cleanup: (() => void) | null = null
  let startX = 0
  let startY = 0
  let offset = 0
  let dragging = false
  let refreshReady = false

  function setRefreshReady(value: boolean) {
    refreshReady = value
    document.body.classList.toggle('is-edge-refresh-ready', value)
  }

  function setRefreshProgress(progress: number) {
    const normalized = roundProgress(clamp(progress, 0, 1))
    const eased = roundProgress(easeOutCubic(normalized))
    const rootStyle = document.documentElement.style
    document.body.classList.toggle('is-edge-refresh-active', normalized > 0)
    rootStyle.setProperty('--edge-refresh-progress', String(normalized))
    rootStyle.setProperty('--edge-refresh-opacity', String(roundProgress(normalized * 0.96)))
    rootStyle.setProperty('--edge-refresh-rotate', `${Math.round(eased * 180)}deg`)
    rootStyle.setProperty('--edge-refresh-y', `${Math.round(-42 + eased * 58)}px`)
  }

  function clearRefreshIndicator() {
    document.body.classList.remove('is-edge-refresh-active')
    document.body.classList.remove('is-edge-refresh-ready')
    const rootStyle = document.documentElement.style
    rootStyle.removeProperty('--edge-refresh-progress')
    rootStyle.removeProperty('--edge-refresh-opacity')
    rootStyle.removeProperty('--edge-refresh-rotate')
    rootStyle.removeProperty('--edge-refresh-y')
  }

  function reset(el: HTMLElement) {
    offset = 0
    setRefreshReady(false)
    setRefreshProgress(0)
    el.style.setProperty('--edge-bounce-transition', '260ms')
    el.style.setProperty('--edge-bounce-y', '0px')
  }

  function attach(el: HTMLElement | null) {
    cleanup?.()
    cleanup = null
    if (!el) return

    el.classList.add('mobile-edge-bounce')

    const onTouchStart = (event: TouchEvent) => {
      if (!mediaQuery?.matches || event.touches.length !== 1) return
      startX = event.touches[0].clientX
      startY = event.touches[0].clientY
      offset = 0
      dragging = true
      setRefreshReady(false)
      setRefreshProgress(0)
      el.style.setProperty('--edge-bounce-transition', '0ms')
    }

    const onTouchMove = (event: TouchEvent) => {
      if (!dragging || !mediaQuery?.matches || event.touches.length !== 1 || !isScrollable(el)) return

      const dx = event.touches[0].clientX - startX
      const dy = event.touches[0].clientY - startY
      if (Math.abs(dx) > Math.abs(dy)) return

      const pullingFromTop = atTop(el) && dy > 0
      const pullingFromBottom = atBottom(el) && dy < 0
      if (!pullingFromTop && !pullingFromBottom) {
        if (offset !== 0) reset(el)
        return
      }

      event.preventDefault()
      offset = clamp(dy * resistance, -maxOffset, maxOffset)
      setRefreshProgress(options.onRefresh && pullingFromTop ? offset / refreshThreshold : 0)
      setRefreshReady(Boolean(options.onRefresh && pullingFromTop && offset >= refreshThreshold))
      el.style.setProperty('--edge-bounce-transition', '0ms')
      el.style.setProperty('--edge-bounce-y', `${offset}px`)
    }

    const onTouchEnd = () => {
      const shouldRefresh = refreshReady
      dragging = false
      if (offset !== 0) reset(el)
      if (shouldRefresh) {
        window.setTimeout(() => options.onRefresh?.(), 80)
      }
    }

    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchmove', onTouchMove, { passive: false })
    el.addEventListener('touchend', onTouchEnd, { passive: true })
    el.addEventListener('touchcancel', onTouchEnd, { passive: true })

    cleanup = () => {
      el.classList.remove('mobile-edge-bounce')
      el.style.removeProperty('--edge-bounce-transition')
      el.style.removeProperty('--edge-bounce-y')
      clearRefreshIndicator()
      el.removeEventListener('touchstart', onTouchStart)
      el.removeEventListener('touchmove', onTouchMove)
      el.removeEventListener('touchend', onTouchEnd)
      el.removeEventListener('touchcancel', onTouchEnd)
    }
  }

  onMounted(() => {
    mediaQuery = window.matchMedia(MOBILE_QUERY)
    void nextTick(() => attach(target.value))
  })

  watch(target, (el) => attach(el))

  onUnmounted(() => {
    cleanup?.()
    cleanup = null
  })
}