<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTaskTrackerStore, type TrackedTask } from '@/stores/taskTracker'
import { Close, ArrowDown, ArrowUp, Check, CircleClose, VideoPause } from '@element-plus/icons-vue'

const tracker = useTaskTrackerStore()
const router = useRouter()
const { t } = useI18n()

const visible = computed(() => tracker.tasks.size > 0)

const activeCount = computed(() => tracker.activeTasks.length)
const doneCount = computed(() => tracker.completedTasks.length)

function statusType(status: string) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'warning'
  if (status === 'running') return 'primary'
  return 'info'
}

function statusIcon(status: string) {
  if (status === 'completed') return Check
  if (status === 'failed' || status === 'cancelled') return CircleClose
  return null
}

function typeLabel(task: TrackedTask) {
  return task.simulationType === 'load'
    ? t('taskTracker.typeLoad')
    : t('taskTracker.typeEnergy')
}

function goToBuilding(task: TrackedTask) {
  const route = router.currentRoute.value
  const projectId = route.params.projectId as string
  if (projectId) {
    if (task.simulationType === 'load') {
      router.push(`/projects/${projectId}/buildings/${task.buildingId}/load`)
    } else {
      router.push(`/projects/${projectId}/buildings/${task.buildingId}/simulation`)
    }
  }
}

function handleCancel(task: TrackedTask) {
  tracker.cancelTask(task.resultId)
}
</script>

<template>
  <Transition name="tracker-slide">
    <div v-if="visible" class="global-task-tracker">
      <!-- Header bar -->
      <div class="tracker-header" @click="tracker.collapsed = !tracker.collapsed">
        <div class="tracker-summary">
          <span class="tracker-dot" :class="{ active: tracker.hasActiveTasks }" />
          <span class="tracker-title">{{ t('taskTracker.title') }}</span>
          <el-tag v-if="tracker.hasActiveTasks" type="primary" size="small" effect="plain" round>
            {{ activeCount }}
          </el-tag>
          <el-tag v-else-if="doneCount > 0" type="success" size="small" effect="plain" round>
            {{ doneCount }}
          </el-tag>
        </div>
        <div class="tracker-actions">
          <el-icon
            v-if="tracker.completedTasks.length > 0 && !tracker.hasActiveTasks"
            :title="t('taskTracker.clearDone')"
            @click.stop="tracker.clearCompleted()"
          >
            <Close />
          </el-icon>
          <el-icon>
            <component :is="tracker.collapsed ? ArrowUp : ArrowDown" />
          </el-icon>
        </div>
      </div>

      <!-- Expanded task list -->
      <Transition name="tracker-expand">
        <div v-if="!tracker.collapsed" class="tracker-body">
          <!-- Active tasks -->
          <div
            v-for="task in tracker.activeTasks"
            :key="task.resultId"
            class="tracker-item"
          >
            <div class="item-header">
              <div class="item-info" @click="goToBuilding(task)">
                <span class="item-name">{{ task.buildingName }}</span>
                <span class="item-type">{{ typeLabel(task) }}</span>
              </div>
              <el-button
                type="danger"
                size="small"
                text
                circle
                :icon="VideoPause"
                :title="t('taskTracker.cancel')"
                @click="handleCancel(task)"
              />
            </div>
            <el-progress
              :percentage="task.progress"
              :stroke-width="6"
              :show-text="true"
              color="#409eff"
            />
          </div>

          <!-- Completed tasks -->
          <div
            v-for="task in tracker.completedTasks"
            :key="task.resultId"
            class="tracker-item completed"
            @click="goToBuilding(task)"
          >
            <div class="item-header">
              <div class="item-info">
                <el-icon :class="'status-' + task.status" style="margin-right: 4px">
                  <component :is="statusIcon(task.status)" />
                </el-icon>
                <span class="item-name">{{ task.buildingName }}</span>
                <span class="item-type">{{ typeLabel(task) }}</span>
              </div>
              <el-tag :type="statusType(task.status)" size="small" effect="plain">
                {{ t(`simulation.statusLabels.${task.status}`, task.status) }}
              </el-tag>
            </div>
            <div v-if="task.errorMessage && task.status === 'failed'" class="item-error">
              {{ task.errorMessage }}
            </div>
          </div>

          <div v-if="tracker.tasks.size === 0" class="tracker-empty">
            {{ t('taskTracker.noTasks') }}
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.global-task-tracker {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 360px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(0, 0, 0, 0.04);
  z-index: 2000;
  overflow: hidden;
}

.tracker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
  border-bottom: 1px solid #e2e8f0;
  user-select: none;
}

.tracker-header:hover {
  background: linear-gradient(135deg, #f1f5f9 0%, #e0e7ff 100%);
}

.tracker-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.tracker-title {
  letter-spacing: -0.01em;
}

.tracker-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
  flex-shrink: 0;
}

.tracker-dot.active {
  background: #10b981;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
  50% { opacity: 0.8; box-shadow: 0 0 0 4px rgba(16, 185, 129, 0); }
}

.tracker-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #64748b;
}

.tracker-actions .el-icon {
  cursor: pointer;
  font-size: 16px;
  transition: color 0.15s;
}

.tracker-actions .el-icon:hover {
  color: #334155;
}

.tracker-body {
  max-height: 320px;
  overflow-y: auto;
  padding: 4px 0;
}

.tracker-item {
  padding: 10px 16px;
  transition: background 0.15s;
  border-bottom: 1px solid #f1f5f9;
}

.tracker-item:last-child {
  border-bottom: none;
}

.tracker-item.completed {
  cursor: pointer;
}

.tracker-item.completed:hover {
  background: #f8fafc;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.item-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
  cursor: pointer;
}

.item-name {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-type {
  font-size: 11px;
  color: #94a3b8;
  flex-shrink: 0;
}

.status-completed {
  color: #10b981;
}

.status-failed,
.status-cancelled {
  color: #ef4444;
}

.item-error {
  font-size: 12px;
  color: #ef4444;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tracker-empty {
  padding: 20px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

/* Transitions */
.tracker-slide-enter-active,
.tracker-slide-leave-active {
  transition: all 0.3s ease;
}

.tracker-slide-enter-from,
.tracker-slide-leave-to {
  transform: translateY(20px);
  opacity: 0;
}

.tracker-expand-enter-active,
.tracker-expand-leave-active {
  transition: all 0.2s ease;
}

.tracker-expand-enter-from,
.tracker-expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
