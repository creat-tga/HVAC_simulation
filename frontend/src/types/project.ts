export interface Project {
  id: string
  name: string
  description: string | null
  location: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  location?: string
}

export interface ProjectUpdate {
  name?: string
  description?: string
  location?: string
}
