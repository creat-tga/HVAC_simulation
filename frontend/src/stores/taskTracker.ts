import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSimulationStatus, cancelSimulation } from '@/api/simulation'

export interface TrackedTask {
  resultId: string
  buildingId: string
  buildingName: string
  simulationType: 'load' | 'energy'
  status: string
  progress: number
  errorMessage: string
}

export const useTaskTrackerStore = defineStore('taskTracker', () => {
  const tasks = ref<Map<string, TrackedTask>>(new Map())
  const collapsed = ref(true)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const activeTasks = computed(() =>
    [...tasks.value.values()].filter(t => ['pending', 'running'].includes(t.status))
  )

  const completedTasks = computed(() =>
    [...tasks.value.values()].filter(t => ['completed', 'failed', 'cancelled'].includes(t.status))
  )

  const hasActiveTasks = computed(() => activeTasks.value.length > 0)

  function addTask(info: {
    resultId: string
    buildingId: string
    buildingName: string
    simulationType: 'load' | 'energy'
  }) {
    tasks.value.set(info.resultId, {
      ...info,
      status: 'pending',
      progress: 0,
      errorMessage: '',
    })
    // Trigger reactivity
    tasks.value = new Map(tasks.value)
    startPolling()
  }

  function updateTask(resultId: string, data: Partial<TrackedTask>) {
    const task = tasks.value.get(resultId)
    if (task) {
      Object.assign(task, data)
      tasks.value = new Map(tasks.value)
    }
  }

  function removeTask(resultId: string) {
    tasks.value.delete(resultId)
    tasks.value = new Map(tasks.value)
    if (!hasActiveTasks.value) stopPolling()
  }

  function clearCompleted() {
    for (const t of completedTasks.value) {
      tasks.value.delete(t.resultId)
    }
    tasks.value = new Map(tasks.value)
  }

  async function cancelTask(resultId: string) {
    const task = tasks.value.get(resultId)
    if (!task) return
    try {
      await cancelSimulation(task.buildingId, resultId)
      updateTask(resultId, { status: 'cancelled', progress: 0 })
    } catch {
      // ignore cancel errors
    }
  }

  async function pollAll() {
    for (const task of activeTasks.value) {
      try {
        const { data } = await getSimulationStatus(task.buildingId, task.resultId)
        updateTask(task.resultId, {
          status: data.status,
          progress: data.progress ?? 0,
          errorMessage: data.error_message || '',
        })
      } catch {
        // ignore poll errors
      }
    }
    if (!hasActiveTasks.value) stopPolling()
  }

  function startPolling() {
    if (pollTimer) return
    pollTimer = setInterval(pollAll, 3000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function $reset() {
    stopPolling()
    tasks.value = new Map()
    collapsed.value = true
  }

  return {
    tasks,
    collapsed,
    activeTasks,
    completedTasks,
    hasActiveTasks,
    addTask,
    updateTask,
    removeTask,
    cancelTask,
    clearCompleted,
    startPolling,
    stopPolling,
    $reset,
  }
})
