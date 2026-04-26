<script setup lang="ts">
/**
 * 模板库 Hub：聚合入口（建筑模板/气象数据/设备模型）
 * 桌面与移动端均可作为模板模块的统一聚合页
 */
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { OfficeBuilding, Sunny, Setting, ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()
const { t } = useI18n()

interface Card {
  key: string
  icon: any
  title: string
  desc: string
  path: string
  accent: string
}

const cards: Card[] = [
  {
    key: 'buildings',
    icon: OfficeBuilding,
    title: t('dashboard.buildingLib.title'),
    desc: t('dashboard.buildingLib.desc'),
    path: '/library/buildings',
    accent: 'var(--brand-primary)',
  },
  {
    key: 'weather',
    icon: Sunny,
    title: t('dashboard.weather.title'),
    desc: t('dashboard.weather.desc'),
    path: '/library/weather',
    accent: 'var(--color-warning)',
  },
  {
    key: 'equipment',
    icon: Setting,
    title: t('dashboard.equipment.title'),
    desc: t('dashboard.equipment.desc'),
    path: '/library/equipment',
    accent: 'var(--brand-accent)',
  },
]
</script>

<template>
  <div class="library-hub">
    <div class="hub-header">
      <h1>{{ t('library.hubTitle') || '模板库' }}</h1>
      <p>{{ t('library.hubSub') || '在此选择需要查看或管理的模板类别' }}</p>
    </div>
    <div class="hub-grid">
      <button
        v-for="card in cards"
        :key="card.key"
        class="hub-card"
        :style="{ '--accent': card.accent }"
        @click="router.push(card.path)"
      >
        <div class="hub-icon">
          <el-icon :size="28"><component :is="card.icon" /></el-icon>
        </div>
        <div class="hub-text">
          <div class="hub-title">{{ card.title }}</div>
          <div class="hub-desc">{{ card.desc }}</div>
        </div>
        <el-icon class="hub-arrow" :size="18"><ArrowRight /></el-icon>
      </button>
    </div>
  </div>
</template>

<style scoped>
.library-hub {
  padding: 24px 28px;
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}
.hub-header h1 {
  margin: 0 0 4px;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
.hub-header p {
  margin: 0 0 24px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.hub-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.hub-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--surface-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  cursor: pointer;
  text-align: left;
  transition: all var(--motion-fast) var(--easing-standard);
  box-shadow: var(--shadow-xs);
}
.hub-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.hub-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  color: var(--accent);
  flex-shrink: 0;
}
.hub-text { flex: 1; min-width: 0; }
.hub-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 4px;
}
.hub-desc {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: var(--line-height-snug);
}
.hub-arrow { color: var(--text-tertiary); flex-shrink: 0; }
.hub-card:hover .hub-arrow { color: var(--accent); }

@media (max-width: 768px) {
  .library-hub { padding: 16px 12px; }
  .hub-grid { grid-template-columns: 1fr; gap: 12px; }
  .hub-card { padding: 16px; gap: 12px; }
  .hub-icon { width: 48px; height: 48px; }
}
</style>
