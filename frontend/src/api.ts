import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/',
  withCredentials: true, // send httpOnly cookies on every request
})

// Intercept 401s: try silent token refresh once, then let the caller handle it
let _refreshing = false
type _QueueEntry = { resolve: () => void; reject: (e: unknown) => void }
let _refreshQueue: _QueueEntry[] = []

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
        // Queue while a refresh is already in-flight; each entry captures its
        // own `original` so the retry re-executes the correct request.
        return new Promise((resolve, reject) => {
          _refreshQueue.push({ resolve: () => resolve(api(original)), reject })
        })
      }
      original._retry = true
      _refreshing = true
      try {
        await api.post('/auth/refresh')
        const queue = _refreshQueue
        _refreshQueue = []
        queue.forEach(({ resolve }) => resolve())
        return api(original)
      } catch (refreshErr) {
        const queue = _refreshQueue
        _refreshQueue = []
        queue.forEach(({ reject }) => reject(refreshErr))
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

// Returned by /jobs/search — not yet in DB, may carry ranking metadata
export interface JobSearchResult {
  title: string
  company: string
  location?: string
  description?: string
  source: string
  url: string
  // Present only when the user has an uploaded CV
  score?: number
  strong_match?: boolean
  missing_skills?: string[]
}

export interface SearchResponse {
  jobs: JobSearchResult[]
  cv_missing: boolean
  cached: boolean
  total: number
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

export const fetchMe = async () => {
  const { data } = await api.get('/auth/me')
  return data as { email: string }
}

export const logoutApi = async () => {
  await api.post('/auth/logout')
}

// ── Jobs ───────────────────────────────────────────────────────────────────

export interface SearchParams {
  query: string
  location: string
  sources: string[]
  max_results?: number
  posted_within?: string
}

export const searchJobs = async (params: SearchParams): Promise<SearchResponse> => {
  const { data } = await api.post('/jobs/search', params)
  return data
}

export const trackJob = async (
  action: 'save' | 'apply',
  job: JobSearchResult,
  notes?: string,
): Promise<Application> => {
  const { data } = await api.post('/jobs/action', { action, job, notes })
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
