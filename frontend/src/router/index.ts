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
          path: 'library',
          name: 'libraryHub',
          component: () => import('@/views/library/LibraryHubView.vue'),
          meta: { title: '模板库' },
        },
        {
          path: 'library/buildings',
          name: 'libBuildings',
          component: () => import('@/views/library/BuildingTemplateLibrary.vue'),
          meta: { title: '建筑模板库', mobileBack: '/library' },
        },
        {
          path: 'library/weather',
          name: 'libWeather',
          component: () => import('@/views/library/WeatherLibrary.vue'),
          meta: { title: '气象数据库', mobileBack: '/library' },
        },
        {
          path: 'library/equipment',
          name: 'libEquipment',
          component: () => import('@/views/library/EquipmentLibrary.vue'),
          meta: { title: '设备模型库', mobileBack: '/library' },
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
          meta: { title: '系统管理', requiresAdmin: true, mobileBack: '/account' },
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
          meta: { title: '建筑搭建', mobileBack: '/projects' },
        },
        {
          path: 'buildings/:buildingId',
          name: 'building',
          component: () => import('@/views/BuildingView.vue'),
          meta: { title: '建筑信息', mobileBack: (r: any) => `/projects/${r.params.projectId}/building`, mobileCustomTopbar: true, mobileNoTitle: true },
        },
        {
          path: 'buildings/:buildingId/load',
          name: 'loadCalc',
          component: () => import('@/views/LoadCalcView.vue'),
          meta: { title: '建筑负荷仿真', mobileBack: (r: any) => `/projects/${r.params.projectId}/buildings/${r.params.buildingId}` },
        },

        // System section
        {
          path: 'system',
          name: 'workspaceSystem',
          component: () => import('@/views/workspace/WorkspaceSystemView.vue'),
          meta: { title: '系统方案', mobileBack: '/projects' },
        },
        {
          path: 'system-schemes',
          name: 'systemSchemeList',
          component: () => import('@/views/SystemSchemeListView.vue'),
          meta: { title: '系统方案', mobileBack: (r: any) => `/projects/${r.params.projectId}/system` },
        },
        {
          path: 'system-schemes/:schemeId',
          name: 'systemSchemeDetail',
          component: () => import('@/views/SystemSchemeDetailView.vue'),
          meta: {
            title: '系统方案详情',
            mobileBack: (r: any) => `/projects/${r.params.projectId}/system-schemes`,
            // 移动端：详情页自带顶栏（含 step 切换 + 保存），隐藏全局 TopActionBar
            mobileCustomTopbar: true,
          },
        },
        // Legacy: still routed for backward compatibility (redirects to list)
        {
          path: 'buildings/:buildingId/system',
          name: 'systemSelect',
          redirect: (to) => `/projects/${to.params.projectId}/system-schemes`,
        },
        {
          path: 'buildings/:buildingId/simulation',
          name: 'simulation',
          component: () => import('@/views/SimulationView.vue'),
          meta: { title: '能耗仿真', mobileBack: (r: any) => `/projects/${r.params.projectId}/system` },
        },

        // Visualization section
        {
          path: 'visualization',
          name: 'workspaceViz',
          component: () => import('@/views/workspace/WorkspaceVisualizationView.vue'),
          meta: { title: '可视化', mobileBack: '/projects' },
        },
        {
          path: 'visualization/loads',
          name: 'workspaceVizLoads',
          component: () => import('@/views/workspace/VisualizationLoadsView.vue'),
          meta: { title: '负荷可视化', mobileBack: (r: any) => `/projects/${r.params.projectId}/visualization` },
        },
        {
          path: 'visualization/energy',
          name: 'workspaceVizEnergy',
          component: () => import('@/views/workspace/VisualizationEnergyView.vue'),
          meta: { title: '能耗可视化', mobileBack: (r: any) => `/projects/${r.params.projectId}/visualization` },
        },
        {
          path: 'buildings/:buildingId/report/:resultId?',
          name: 'report',
          component: () => import('@/views/ReportView.vue'),
          meta: { title: '结果展示', mobileBack: (r: any) => `/projects/${r.params.projectId}/visualization` },
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
