import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Project } from '@/types/project'
import type { Building } from '@/types/building'
import { getProjects } from '@/api/projects'
import { getBuildings } from '@/api/buildings'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const buildings = ref<Building[]>([])
  const loading = ref(false)

  async function fetchProjects() {
    loading.value = true
    try {
      const { data } = await getProjects()
      projects.value = data
    } finally {
      loading.value = false
    }
  }

  async function fetchBuildings(projectId: string) {
    loading.value = true
    try {
      const { data } = await getBuildings(projectId)
      buildings.value = data
    } finally {
      loading.value = false
    }
  }

  function setCurrentProject(project: Project | null) {
    currentProject.value = project
  }

  return {
    projects,
    currentProject,
    buildings,
    loading,
    fetchProjects,
    fetchBuildings,
    setCurrentProject,
  }
})
