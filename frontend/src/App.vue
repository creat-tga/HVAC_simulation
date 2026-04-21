<script setup lang="ts">
import { useRoute } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import GlobalTaskTracker from '@/components/simulation/GlobalTaskTracker.vue'

const route = useRoute()
</script>

<template>
  <router-view v-if="route.meta.plain || route.meta.noSidebar" />
  <AppLayout v-else>
    <router-view />
  </AppLayout>
  <GlobalTaskTracker />
</template>
