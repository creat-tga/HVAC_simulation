import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { title: '首页' },
    },
    {
      path: '/projects/:projectId',
      name: 'project',
      component: () => import('@/views/ProjectView.vue'),
      meta: { title: '项目详情' },
    },
    {
      path: '/projects/:projectId/buildings/:buildingId',
      name: 'building',
      component: () => import('@/views/BuildingView.vue'),
      meta: { title: '建筑配置' },
    },
    {
      path: '/projects/:projectId/buildings/:buildingId/load',
      name: 'loadCalc',
      component: () => import('@/views/LoadCalcView.vue'),
      meta: { title: '负荷计算' },
    },
    {
      path: '/projects/:projectId/buildings/:buildingId/system',
      name: 'systemSelect',
      component: () => import('@/views/SystemSelectView.vue'),
      meta: { title: '系统选型' },
    },
    {
      path: '/projects/:projectId/buildings/:buildingId/simulation',
      name: 'simulation',
      component: () => import('@/views/SimulationView.vue'),
      meta: { title: '仿真模拟' },
    },
    {
      path: '/projects/:projectId/buildings/:buildingId/report/:resultId',
      name: 'report',
      component: () => import('@/views/ReportView.vue'),
      meta: { title: '报表分析' },
    },
  ],
})

router.beforeEach((to) => {
  const title = (to.meta.title as string) || 'HVAC仿真平台'
  document.title = `${title} - HVAC仿真平台`

  // Auth guard
  const token = localStorage.getItem('hvac_token')
  if (!to.meta.public && !token) {
    return { name: 'login' }
  }
})

export default router
