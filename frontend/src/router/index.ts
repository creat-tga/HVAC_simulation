import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', public: true, plain: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '注册', public: true, plain: true },
    },

    // Home area: left sidebar layout for global modules
    {
      path: '/',
      component: () => import('@/components/layout/HomeLayout.vue'),
      meta: { noSidebar: true },
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('@/views/HomeDashboard.vue'),
          meta: { title: '主页' },
        },
        {
          path: 'projects',
          name: 'projectsList',
          component: () => import('@/views/HomeView.vue'),
          meta: { title: '工程管理' },
        },
        {
          path: 'library/buildings',
          name: 'libBuildings',
          component: () => import('@/views/library/BuildingTemplateLibrary.vue'),
          meta: { title: '建筑模板库' },
        },
        {
          path: 'library/weather',
          name: 'libWeather',
          component: () => import('@/views/library/WeatherLibrary.vue'),
          meta: { title: '气象数据库' },
        },
        {
          path: 'library/equipment',
          name: 'libEquipment',
          component: () => import('@/views/library/EquipmentLibrary.vue'),
          meta: { title: '设备模型库' },
        },
        {
          path: 'account',
          name: 'account',
          component: () => import('@/views/AccountView.vue'),
          meta: { title: '账户管理' },
        },
        {
          path: 'admin/users',
          name: 'adminUsers',
          component: () => import('@/views/AdminUsersView.vue'),
          meta: { title: '系统管理', requiresAdmin: true },
        },
      ],
    },

    // Project workspace (its own left sidebar)
    {
      path: '/projects/:projectId',
      component: () => import('@/components/layout/ProjectWorkspaceLayout.vue'),
      meta: { workspace: true, noSidebar: true },
      children: [
        { path: '', redirect: (to) => `/projects/${to.params.projectId}/building` },

        // Building section
        {
          path: 'building',
          name: 'workspaceBuilding',
          component: () => import('@/views/workspace/WorkspaceBuildingView.vue'),
          meta: { title: '建筑搭建' },
        },
        {
          path: 'buildings/:buildingId',
          name: 'building',
          component: () => import('@/views/BuildingView.vue'),
          meta: { title: '建筑信息' },
        },
        {
          path: 'buildings/:buildingId/load',
          name: 'loadCalc',
          component: () => import('@/views/LoadCalcView.vue'),
          meta: { title: '建筑负荷仿真' },
        },

        // System section
        {
          path: 'system',
          name: 'workspaceSystem',
          component: () => import('@/views/workspace/WorkspaceSystemView.vue'),
          meta: { title: '系统方案' },
        },
        {
          path: 'buildings/:buildingId/system',
          name: 'systemSelect',
          component: () => import('@/views/SystemSelectView.vue'),
          meta: { title: '系统方案' },
        },
        {
          path: 'buildings/:buildingId/simulation',
          name: 'simulation',
          component: () => import('@/views/SimulationView.vue'),
          meta: { title: '能耗仿真' },
        },

        // Visualization section
        {
          path: 'visualization',
          name: 'workspaceViz',
          component: () => import('@/views/workspace/WorkspaceVisualizationView.vue'),
          meta: { title: '可视化' },
        },
        {
          path: 'visualization/loads',
          name: 'workspaceVizLoads',
          component: () => import('@/views/workspace/VisualizationLoadsView.vue'),
          meta: { title: '负荷可视化' },
        },
        {
          path: 'visualization/energy',
          name: 'workspaceVizEnergy',
          component: () => import('@/views/workspace/VisualizationEnergyView.vue'),
          meta: { title: '能耗可视化' },
        },
        {
          path: 'buildings/:buildingId/report/:resultId?',
          name: 'report',
          component: () => import('@/views/ReportView.vue'),
          meta: { title: '结果展示' },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const title = (to.meta.title as string) || 'HVAC仿真平台'
  document.title = `${title} - HVAC仿真平台`

  const token = localStorage.getItem('hvac_token')
  if (!to.meta.public && !token) {
    return { name: 'login' }
  }

  if (to.meta.requiresAdmin) {
    const role = localStorage.getItem('hvac_role')
    if (role !== 'admin') {
      return { name: 'home' }
    }
  }
})

export default router
