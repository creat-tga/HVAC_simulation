<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ParticleBg from '@/components/layout/ParticleBg.vue'
import BreadcrumbNav from '@/components/layout/BreadcrumbNav.vue'
import { useResponsive } from '@/composables/useResponsive'

const { isMobile, sidebarOpen, closeSidebar } = useResponsive()
const route = useRoute()

// Close sidebar on navigation in mobile
watch(() => route.fullPath, () => {
  if (isMobile.value) closeSidebar()
})
</script>

<template>
  <el-container class="app-layout" direction="vertical">
    <AppHeader />
    <el-container class="app-body">
      <!-- Desktop sidebar -->
      <AppSidebar v-if="!isMobile" />

      <!-- Mobile drawer -->
      <el-drawer
        v-if="isMobile"
        v-model="sidebarOpen"
        direction="ltr"
        :size="260"
        :show-close="false"
        :with-header="false"
        class="mobile-drawer"
      >
        <AppSidebar class="mobile-sidebar" />
      </el-drawer>

      <!-- Overlay when drawer is open -->
      <div v-if="isMobile && sidebarOpen" class="mobile-overlay" @click="closeSidebar" />

      <el-main>
        <ParticleBg />
        <BreadcrumbNav />
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
  height: 100dvh;
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
  min-height: 100%;
}

/* Mobile */
.mobile-sidebar {
  width: 100% !important;
  border-right: none;
}

.mobile-overlay {
  position: fixed;
  inset: 0;
  z-index: 1999;
  background: rgba(0, 0, 0, 0.3);
}

@media (max-width: 768px) {
  .main-content {
    padding: 12px;
  }
}
</style>
