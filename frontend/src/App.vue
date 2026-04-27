<script setup lang="ts">
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import AppLayout from '@/components/layout/AppLayout.vue'
import GlobalTaskTracker from '@/components/simulation/GlobalTaskTracker.vue'

const route = useRoute()
</script>

<template>
  <el-config-provider :locale="zhCn">
    <router-view v-if="route.meta.plain || route.meta.noSidebar" />
    <AppLayout v-else>
      <router-view />
    </AppLayout>
    <GlobalTaskTracker />
  </el-config-provider>
</template>
