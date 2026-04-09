import { ref, watch, onUnmounted, type Ref } from 'vue'
import type { SimulationProgressEvent } from '@/types/simulation'

/**
 * Composable for subscribing to real-time simulation progress via WebSocket.
 *
 * @param resultId - Reactive ref to the simulation result ID to track.
 *                   Set to null to disconnect.
 */
export function useSimulationWs(resultId: Ref<string | null>) {
  const status = ref<string>('pending')
  const progress = ref(0)
  const message = ref('')
  const connected = ref(false)

  let ws: WebSocket | null = null

  function connect(id: string) {
    disconnect()

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/ws/simulations/${id}`

    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (event) => {
      try {
        const data: SimulationProgressEvent = JSON.parse(event.data)
        status.value = data.status
        progress.value = data.progress
        message.value = data.message || ''

        // Auto-disconnect on terminal states
        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
          connected.value = false
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      connected.value = false
      ws = null
    }

    ws.onerror = () => {
      connected.value = false
    }
  }

  function disconnect() {
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
  }

  // Auto-connect / disconnect when resultId changes
  watch(
    resultId,
    (newId) => {
      if (newId) {
        connect(newId)
      } else {
        disconnect()
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    disconnect()
  })

  return {
    status,
    progress,
    message,
    connected,
    disconnect,
  }
}
