<script setup lang="ts">
defineProps<{
  prevLabel?: string
  nextLabel?: string
  nextDisabled?: boolean
}>()

const emit = defineEmits<{
  prev: []
  next: []
}>()
</script>

<template>
  <div class="step-nav">
    <el-button v-if="prevLabel" @click="emit('prev')">
      ← {{ prevLabel }}
    </el-button>
    <span v-else />
    <el-button
      v-if="nextLabel"
      type="primary"
      :disabled="nextDisabled"
      @click="emit('next')"
    >
      {{ nextLabel }} →
    </el-button>
  </div>
</template>

<style scoped>
.step-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

@media (max-width: 768px) {
  .step-nav {
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
  }

  .step-nav :deep(.el-button) {
    flex: 1;
    min-width: 0;
  }
}
</style>
