import { useCallback, useEffect, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { fetchJobs, createApplication, type Job, type AppStatus } from '../api'

const PAGE_SIZE = 25
const SOURCES: Record<string, string> = { linkedin: '🔵 LinkedIn', indeed: '🟠 Indeed' }

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [adding, setAdding] = useState<string | null>(null)
  const [added, setAdded] = useState<Set<string>>(new Set())
  const [trackError, setTrackError] = useState<string | null>(null)

  const parentRef = useRef<HTMLDivElement>(null)

  // Load a page of jobs
  const loadPage = useCallback(async (pageOffset: number) => {
    setLoadingMore(true)
    const page = await fetchJobs(PAGE_SIZE, pageOffset)
    setJobs((prev) => pageOffset === 0 ? page : [...prev, ...page])
    setHasMore(page.length === PAGE_SIZE)
    setLoadingMore(false)
  }, [])

  // Initial load
  useEffect(() => { loadPage(0) }, [loadPage])

  // Filter locally (only among fetched jobs)
  const filtered = search
    ? jobs.filter(
        (j) =>
          j.title.toLowerCase().includes(search.toLowerCase()) ||
          j.company.toLowerCase().includes(search.toLowerCase())
      )
    : jobs

  // Virtualizer
  const virtualizer = useVirtualizer({
    count: hasMore ? filtered.length + 1 : filtered.length, // +1 for sentinel
    getScrollElement: () => parentRef.current,
    estimateSize: () => 96, // px per row estimate
    overscan: 5,
  })

  // Load next page when sentinel becomes visible
  const virtualItems = virtualizer.getVirtualItems()
  useEffect(() => {
    if (!virtualItems.length) return
    const last = virtualItems[virtualItems.length - 1]
    if (last.index >= filtered.length && hasMore && !loadingMore) {
      const nextOffset = offset + PAGE_SIZE
      setOffset(nextOffset)
      loadPage(nextOffset)
    }
  }, [virtualItems, filtered.length, hasMore, loadingMore, offset, loadPage])

  const track = async (job: Job, status: AppStatus) => {
    setAdding(job.id)
    setTrackError(null)
    try {
      await createApplication(job.id, status)
      setAdded((prev) => new Set(prev).add(job.id))
    } catch {
      setTrackError('Could not add — already tracked or server error.')
    } finally {
      setAdding(null)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Track error */}
      {trackError && (
        <div className="flex-shrink-0 mb-2 bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-2 text-sm">
          {trackError}
        </div>
      )}
      {/* Search */}
      <div className="flex-shrink-0 mb-3 flex items-center gap-3">
        <input
          type="text"
          placeholder="Search jobs or companies…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-gray-800 text-white rounded-xl px-4 py-2.5 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-gray-500 text-sm"
        />
        <span className="text-gray-500 text-xs whitespace-nowrap">{filtered.length} loaded</span>
      </div>

      {/* Virtual list */}
      <div ref={parentRef} className="flex-1 overflow-y-auto">
        <div
          style={{ height: virtualizer.getTotalSize(), position: 'relative' }}
        >
          {virtualItems.map((vItem) => {
            const job = filtered[vItem.index]

            // Sentinel row
            if (!job) {
              return (
                <div
                  key="sentinel"
                  data-index={vItem.index}
                  ref={virtualizer.measureElement}
                  style={{ position: 'absolute', top: vItem.start, left: 0, right: 0 }}
                  className="flex items-center justify-center py-4 text-gray-500 text-sm"
                >
                  {loadingMore ? 'Loading more…' : ''}
                </div>
              )
            }

            return (
              <div
                key={job.id}
                data-index={vItem.index}
                ref={virtualizer.measureElement}
                style={{ position: 'absolute', top: vItem.start, left: 0, right: 0, padding: '0 0 8px 0' }}
              >
                <div className="bg-gray-900 rounded-xl px-4 py-3 flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-gray-500">{SOURCES[job.source] ?? job.source}</span>
                      {job.location && <span className="text-xs text-gray-600">· {job.location}</span>}
                    </div>
                    <p className="text-white font-semibold mt-0.5 truncate">{job.title}</p>
                    <p className="text-gray-400 text-sm">{job.company}</p>
                    {job.description && (
                      <p className="text-gray-500 text-xs mt-1 line-clamp-1">{job.description}</p>
                    )}
                  </div>

                  <div className="flex flex-col gap-2 flex-shrink-0">
                    {added.has(job.id) ? (
                      <span className="text-green-400 text-xs font-semibold">✓ Tracked</span>
                    ) : (
                      <>
                        <button
                          onClick={() => track(job, 'saved')}
                          disabled={adding === job.id}
                          className="bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => track(job, 'applied')}
                          disabled={adding === job.id}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50"
                        >
                          Applied
                        </button>
                      </>
                    )}
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-gray-500 hover:text-gray-300 text-center"
                    >
                      Open ↗
                    </a>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
