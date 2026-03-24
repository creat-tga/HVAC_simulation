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
  background: #f1f5f9;
}

.app-body {
  flex: 1;
  overflow: hidden;
}

.app-body :deep(.el-main) {
  overflow: hidden;
  position: relative;
  background: transparent;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.main-content {
  position: relative;
  z-index: 1;
  flex: 1;
  overflow: auto;
  padding: 20px;
}
</style>
