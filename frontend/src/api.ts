import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/',
  withCredentials: true, // send httpOnly cookies on every request
})

// Intercept 401s: try silent token refresh once, then let the caller handle it
let _refreshing = false
let _refreshQueue: Array<() => void> = []

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    // Only attempt refresh on 401 for non-auth endpoints to avoid infinite loops
    if (
      err.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes('/auth/')
    ) {
      if (_refreshing) {
        // Queue while a refresh is already in-flight
        return new Promise((resolve) => {
          _refreshQueue.push(() => resolve(api(original)))
        })
      }
      original._retry = true
      _refreshing = true
      try {
        await api.post('/auth/refresh')
        _refreshQueue.forEach((cb) => cb())
        _refreshQueue = []
        return api(original)
      } catch {
        _refreshQueue = []
        // Refresh failed — caller receives the original 401
      } finally {
        _refreshing = false
      }
    }
    return Promise.reject(err)
  }
)

export default api

// ── Types ──────────────────────────────────────────────────────────────────

export type AppStatus = 'saved' | 'applied' | 'interview' | 'rejected' | 'offer'

export interface Job {
  id: string
  title: string
  company: string
  location?: string
  description?: string
  source: string
  url: string
  created_at: string
}

export interface Application {
  id: string
  user_id: string
  job_id: string
  status: AppStatus
  notes?: string
  applied_at?: string
  created_at: string
  updated_at: string
  jobs?: Job
}

// ── Auth ───────────────────────────────────────────────────────────────────

export const login = async (email: string, password: string) => {
  const { data } = await api.post('/auth/login', { email, password })
  return data as { email: string }
}

export const register = async (email: string, password: string) => {
  const { data } = await api.post('/auth/register', { email, password })
  return data as { email: string }
}

export const fetchMe = async () => {
  const { data } = await api.get('/auth/me')
  return data as { email: string }
}

export const logoutApi = async () => {
  await api.post('/auth/logout')
}

// ── Jobs ───────────────────────────────────────────────────────────────────

export const fetchJobs = async (limit = 25, offset = 0): Promise<Job[]> => {
  const { data } = await api.get('/jobs/', { params: { limit, offset } })
  return data
}

export const fetchMatches = async () => {
  const { data } = await api.get('/jobs/matches')
  return data
}

// ── Applications ───────────────────────────────────────────────────────────

export const fetchApplications = async (): Promise<Application[]> => {
  const { data } = await api.get('/applications/')
  return data
}

export const createApplication = async (job_id: string, status: AppStatus = 'saved'): Promise<Application> => {
  const { data } = await api.post('/applications/', { job_id, status })
  return data
}

export const updateApplication = async (
  id: string,
  patch: { status?: AppStatus; notes?: string; applied_at?: string }
): Promise<Application> => {
  const { data } = await api.patch(`/applications/${id}`, patch)
  return data
}

export const deleteApplication = async (id: string) => {
  await api.delete(`/applications/${id}`)
}

// ── CV ─────────────────────────────────────────────────────────────────────

export interface CvRecord {
  storage_path: string
  filename: string
  signed_url: string
  created_at: string
}

export const uploadCv = async (file: File): Promise<{ storage_path: string; signed_url: string }> => {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/cv/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const fetchLatestCv = async (): Promise<CvRecord> => {
  const { data } = await api.get('/cv/latest')
  return data
}
