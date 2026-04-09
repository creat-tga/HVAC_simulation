<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CircleCloseFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  status: string
  progress: number
  message: string
  connected: boolean
}>()

const emit = defineEmits<{
  cancel: []
}>()

const { t } = useI18n()

const progressStatus = computed(() => {
  if (props.status === 'completed') return 'success'
  if (props.status === 'failed') return 'exception'
  if (props.status === 'cancelled') return 'exception'
  return undefined
})

const statusType = computed(() => {
  switch (props.status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'cancelled': return 'warning'
    case 'running': return 'primary'
    default: return 'info'
  }
})

const canCancel = computed(() => {
  return ['pending', 'running'].includes(props.status)
})
</script>

<template>
  <div class="simulation-progress">
    <div class="progress-header">
      <el-tag :type="statusType" effect="dark" size="small">
        {{ t(`simulation.statusLabels.${status}`, status) }}
      </el-tag>
      <span v-if="connected" class="ws-badge">
        <span class="ws-dot" /> {{ t('simulation.progress.realtime') }}
      </span>
    </div>

    <el-progress
      :percentage="progress"
      :status="progressStatus"
      :stroke-width="20"
      :text-inside="true"
      class="progress-bar"
    />

    <div class="progress-footer">
      <span class="progress-message">{{ message }}</span>
      <el-button
        v-if="canCancel"
        type="danger"
        size="small"
        text
        :icon="CircleCloseFilled"
        @click="emit('cancel')"
      >
        {{ t('simulation.progress.cancel') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.simulation-progress {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 16px 20px;
  margin: 16px 0;
}

.progress-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.ws-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #059669;
}

.ws-dot {
  width: 6px;
  height: 6px;
  background: #10b981;
  border-radius: 50%;
  display: inline-block;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.progress-bar {
  margin-bottom: 8px;
}

.progress-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 24px;
}

.progress-message {
  font-size: 13px;
  color: #64748b;
}
</style>
