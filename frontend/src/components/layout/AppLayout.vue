<script setup lang="ts">
import AppHeader from '@/components/layout/AppHeader.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ParticleBg from '@/components/layout/ParticleBg.vue'
</script>

<template>
  <el-container class="app-layout" direction="vertical">
    <AppHeader />
    <el-container class="app-body">
      <AppSidebar />
      <el-main>
        <ParticleBg />
        <div class="main-content">
          <slot />
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100vh;
  background: #f0f2f5;
}

.app-body {
  flex: 1;
  overflow: hidden;
}

.app-body :deep(.el-main) {
  overflow: hidden;
  position: relative;
  background: linear-gradient(160deg, #f0f2f5 0%, #e8ecf1 50%, #f0f2f5 100%);
  display: flex;
  flex-direction: column;
}

.main-content {
  position: relative;
  z-index: 1;
  flex: 1;
  overflow: auto;
}
</style>
