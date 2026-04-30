<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/project'
import { listWeatherFiles, listEquipment, listBuildingTemplates } from '@/api/library'
import { adminListUsers } from '@/api/users'
import {
  FolderOpened,
  OfficeBuilding,
  Sunny,
  Setting,
  User,
} from '@element-plus/icons-vue'

const router = useRouter()
const { t } = useI18n()
const auth = useAuthStore()
const projectStore = useProjectStore()

const stats = ref({ projects: 0, buildings: 0, weather: 0, equipment: 0, activeUsers: undefined as number | undefined })

interface CardMetric {
  value?: number
}

interface Card {
  key: string
  title: string
  desc: string
  icon: any
  color: string
  path: string
  metric?: CardMetric
}

const cards = computed<Card[]>(() => {
  const list: Card[] = [
    {
      key: 'projects',
      title: t('dashboard.projects.title'),
      desc: t('dashboard.projects.desc'),
      icon: FolderOpened,
      color: '#0891b2',
      path: '/projects',
      metric: { value: stats.value.projects },
    },
    {
      key: 'buildings',
      title: t('dashboard.buildingLib.title'),
      desc: t('dashboard.buildingLib.desc'),
      icon: OfficeBuilding,
      color: '#0d9488',
      path: '/library/buildings',
      metric: { value: stats.value.buildings },
    },
    {
      key: 'weather',
      title: t('dashboard.weather.title'),
      desc: t('dashboard.weather.desc'),
      icon: Sunny,
      color: '#f59e0b',
      path: '/library/weather',
      metric: { value: stats.value.weather },
    },
    {
      key: 'equipment',
      title: t('dashboard.equipment.title'),
      desc: t('dashboard.equipment.desc'),
      icon: Setting,
      color: '#7c3aed',
      path: '/library/equipment',
      metric: { value: stats.value.equipment },
    },
  ]
  if (auth.isAdmin) {
    list.push({
      key: 'management',
      title: t('dashboard.account.managementTitle'),
      desc: t('dashboard.account.managementDesc'),
      icon: User,
      color: '#dc2626',
      path: '/admin/users',
      metric: { value: stats.value.activeUsers },
    })
  } else {
    list.push({
      key: 'account',
      title: t('dashboard.account.title'),
      desc: t('dashboard.account.desc'),
      icon: User,
      color: '#ef4444',
      path: '/account',
    })
  }
  return list
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

async function loadStats() {
  try {
    await projectStore.fetchProjects()
    stats.value.projects = projectStore.projects.length
  } catch { /* ignore */ }
  try {
    const { data } = await listBuildingTemplates('all')
    stats.value.buildings = data.length
  } catch { /* ignore */ }
  try {
    const { data } = await listWeatherFiles()
    stats.value.weather = data.length
  } catch { /* ignore */ }
  try {
    const { data } = await listEquipment({ scope: 'all' })
    stats.value.equipment = data.length
  } catch { /* ignore */ }
  if (auth.isAdmin) {
    try {
      const { data } = await adminListUsers({ status: 'active', role: 'all' })
      stats.value.activeUsers = data.filter(user => user.status === 'active').length
    } catch { /* ignore */ }
  }
}

onMounted(loadStats)

function go(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="dashboard">
    <header class="dash-hero">
      <div class="hero-glow" />
      <div class="hero-inner">
        <div class="hero-tag">HVAC Simulation Platform</div>
        <h1 class="hero-title">
          {{ greeting }}，<span class="username">{{ auth.username }}</span>
        </h1>
        <p class="hero-sub">{{ t('dashboard.subtitle') }}</p>
      </div>
    </header>

    <section class="cards-section">
      <h2 class="section-title">模块入口</h2>
      <div class="cards-grid">
        <div
          v-for="c in cards"
          :key="c.key"
          class="entry-card"
          :style="{ '--c': c.color } as any"
          @click="go(c.path)"
        >
          <div class="card-icon"><el-icon :size="24"><component :is="c.icon" /></el-icon></div>
          <div class="card-body">
            <h3>{{ c.title }}</h3>
            <p>{{ c.desc }}</p>
          </div>
          <div v-if="c.metric" class="card-metric">
            <div class="card-metric-value">{{ c.metric.value ?? '-' }}</div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 28px 32px;
  height: 100%;
  overflow-y: auto;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

/* ----- Hero ----- */
.dash-hero {
  position: relative;
  padding: 32px 36px;
  border-radius: 20px;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0c4a6e 100%);
  color: #e2e8f0;
  overflow: hidden;
  margin-bottom: 24px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
}
.hero-glow {
  position: absolute;
  top: -40%; right: -10%;
  width: 480px; height: 480px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.35), transparent 65%);
  filter: blur(20px);
  pointer-events: none;
}
.hero-inner {
  position: relative;
  z-index: 1;
}
.hero-tag {
  display: inline-block;
  padding: 4px 10px;
  background: rgba(6, 182, 212, 0.18);
  color: #22d3ee;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}
.hero-title {
  margin: 0 0 8px 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0;
  color: #f1f5f9;
}
.hero-title .username {
  background: linear-gradient(135deg, #22d3ee, #38bdf8);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hero-sub {
  margin: 0;
  color: #94a3b8;
  font-size: 14px;
}

/* ----- Cards ----- */
.section-title {
  margin: 0 0 14px 0;
  font-size: 16px;
  font-weight: 600;
  color: #475569;
  letter-spacing: -0.01em;
}
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.entry-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.6);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.22s ease;
  position: relative;
  overflow: hidden;
}
.entry-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--c) 8%, transparent), transparent 60%);
  opacity: 0;
  transition: opacity 0.22s;
  pointer-events: none;
}
.entry-card:hover {
  transform: translateY(-3px);
  border-color: var(--c);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}
.entry-card:hover::before { opacity: 1; }

.card-icon {
  width: 44px; height: 44px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  background: color-mix(in srgb, var(--c) 14%, transparent);
  color: var(--c);
  flex-shrink: 0;
}
.card-body { flex: 1; min-width: 0; position: relative; z-index: 1; }
.card-body h3 {
  margin: 0 0 3px 0;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.card-body p {
  margin: 0;
  font-size: 12.5px;
  color: #64748b;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}
.card-metric {
  position: relative;
  z-index: 1;
  min-width: 64px;
  padding-left: 14px;
  border-left: 1px solid rgba(226, 232, 240, 0.78);
  display: flex;
  align-items: center;
  justify-content: center;
  align-self: stretch;
}
.card-metric-value {
  color: #64748b;
  font-size: 20px;
  font-weight: 400;
  line-height: 1;
}

@media (max-width: 768px) {
  .dashboard { padding: 16px; }
  .dash-hero {
    padding: 22px;
  }
  .hero-title {
    font-size: 22px;
  }
  .cards-grid { grid-template-columns: 1fr; }
  .entry-card {
    grid-template-columns: 58px minmax(0, 1fr) 66px;
    gap: 16px;
    min-height: 118px;
    padding: 20px 18px;
    border-radius: 16px;
  }
  .card-icon { width: 58px; height: 58px; border-radius: 14px; }
  .card-body h3 { font-size: 18px; }
  .card-body p { font-size: 14px; line-height: 1.55; }
  .card-metric {
    min-width: 54px;
    padding-left: 16px;
  }
  .card-metric-value { font-size: 28px; }
}

@media (max-width: 420px) {
  .entry-card {
    grid-template-columns: 52px minmax(0, 1fr) 52px;
    gap: 12px;
    min-height: 112px;
    padding: 18px 14px;
  }
  .card-icon { width: 52px; height: 52px; }
  .card-body h3 { font-size: 17px; }
  .card-body p { font-size: 13.5px; }
  .card-metric {
    min-width: 50px;
    padding-left: 10px;
  }
  .card-metric-value { font-size: 26px; }
}
</style>
