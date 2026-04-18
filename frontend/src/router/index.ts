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
      meta: { title: '工程管理' },
    },
    {
      path: '/projects/:projectId',
      name: 'project',
      component: () => import('@/views/ProjectView.vue'),
      meta: { title: '项目概览' },
    },
    {
      path: '/projects/:projectId/buildings/:buildingId',
      component: () => import('@/components/layout/BuildingLayout.vue'),
      children: [
        {
          path: '',
          name: 'building',
          component: () => import('@/views/BuildingView.vue'),
          meta: { title: '建筑信息', step: 1 },
        },
        {
          path: 'load',
          name: 'loadCalc',
          component: () => import('@/views/LoadCalcView.vue'),
          meta: { title: '建筑负荷仿真', step: 2 },
        },
        {
          path: 'system',
          name: 'systemSelect',
          component: () => import('@/views/SystemSelectView.vue'),
          meta: { title: '系统方案', step: 3 },
        },
        {
          path: 'simulation',
          name: 'simulation',
          component: () => import('@/views/SimulationView.vue'),
          meta: { title: '能耗仿真', step: 4 },
        },
        {
          path: 'report/:resultId?',
          name: 'report',
          component: () => import('@/views/ReportView.vue'),
          meta: { title: '结果展示', step: 5 },
        },
      ],
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
