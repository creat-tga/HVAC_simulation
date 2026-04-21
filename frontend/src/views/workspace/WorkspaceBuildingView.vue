<script setup lang="ts">
/**
 * Workspace > Building stage. Wraps ProjectView (project-level building list + load simulation).
 */
import ProjectView from '@/views/ProjectView.vue'
</script>

<template>
  <div class="ws-building-wrapper">
    <ProjectView />
  </div>
</template>

<style scoped>
.ws-building-wrapper {
  width: 100%;
  min-width: 0;
}
.ws-building-wrapper :deep(.el-table) {
  width: 100%;
}
.ws-building-wrapper :deep(.el-table__body-wrapper),
.ws-building-wrapper :deep(.el-table__header-wrapper) {
  overflow-x: auto;
}
</style>
