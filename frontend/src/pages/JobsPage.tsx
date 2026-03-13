import { useState } from "react"
import { searchJobs, trackJob, type JobSearchResult, type SearchResponse } from "../api"

const ALL_SOURCES = ["linkedin"]

const TIME_FILTERS = [
  { label: "24 hours",  value: "r86400" },
  { label: "3 days",    value: "r259200" },
  { label: "7 days",    value: "r604800" },
  { label: "30 days",   value: "r2592000" },
]

export default function JobsPage() {
  const [query, setQuery]           = useState("")
  const [location, setLocation]     = useState("")
  const [postedWithin, setPostedWithin] = useState("r604800")

  const [results, setResults]       = useState<JobSearchResult[]>([])
  const [cvMissing, setCvMissing]   = useState(false)
  const [loading, setLoading]       = useState(false)
  const [searched, setSearched]     = useState(false)
  const [error, setError]           = useState<string | null>(null)

  const [tracked, setTracked]       = useState<Map<string, string>>(new Map())
  const [tracking, setTracking]     = useState<string | null>(null)

  const handleSearch = async () => {
    setLoading(true)
    setError(null)
    setResults([])
    setSearched(false)
    try {
      const res: SearchResponse = await searchJobs({
        query,
        location,
        sources: ALL_SOURCES,
        posted_within: postedWithin || undefined,
      })
      setResults(res.jobs)
      setCvMissing(res.cv_missing)
      setSearched(true)
    } catch {
      setError("Search failed — check your connection or try again.")
    } finally {
      setLoading(false)
    }
  }

  const handleTrack = async (job: JobSearchResult, action: "save" | "apply") => {
    setTracking(job.url)
    try {
      await trackJob(action, job)
      setTracked((prev) => new Map(prev).set(job.url, action))
    } catch {
      // silent fail
    } finally {
      setTracking(null)
    }
  }

  return (
    <div className="flex flex-col h-full gap-4">

      {/* ---- Search bar ---- */}
      <div className="flex-shrink-0 bg-gray-900 rounded-2xl p-4 flex flex-col gap-3">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Job title, skills, keywords…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1 bg-gray-800 text-white rounded-xl px-4 py-2.5 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-gray-500 text-sm"
          />
          <input
            type="text"
            placeholder="Location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-36 bg-gray-800 text-white rounded-xl px-4 py-2.5 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-gray-500 text-sm"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors whitespace-nowrap"
          >
            {loading ? "Searching…" : "Search"}
          </button>
        </div>

        {/* ---- Posted within pills ---- */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-gray-500 text-xs mr-1">Posted:</span>
          {TIME_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setPostedWithin(f.value)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                postedWithin === f.value
                  ? "bg-indigo-600 border-indigo-500 text-white font-semibold"
                  : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* ---- CV missing banner ---- */}
      {cvMissing && results.length > 0 && (
        <div className="flex-shrink-0 bg-yellow-900/30 border border-yellow-700/50 text-yellow-300 rounded-xl px-4 py-2.5 text-sm">
          💡 Upload your CV to get personalized match scores for each job.
        </div>
      )}

      {/* ---- Error ---- */}
      {error && (
        <div className="flex-shrink-0 bg-red-900/40 border border-red-700 text-red-300 rounded-xl px-4 py-2.5 text-sm">
          {error}
        </div>
      )}

      {/* ---- Loading ---- */}
      {loading && (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-400 text-sm gap-3">
          <svg className="animate-spin h-6 w-6 text-indigo-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span>Scraping jobs and ranking them for you…</span>
          <span className="text-gray-600 text-xs">This may take up to 30 seconds on the first search.</span>
        </div>
      )}

      {/* ---- Empty states ---- */}
      {!loading && !searched && (
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
          Enter a search above to find jobs.
        </div>
      )}
      {!loading && searched && results.length === 0 && (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          No jobs found. Try different keywords or location.
        </div>
      )}

      {/* ---- Results ---- */}
      {!loading && results.length > 0 && (
        <div className="flex-1 overflow-y-auto flex flex-col gap-2">
          <p className="text-gray-500 text-xs flex-shrink-0">{results.length} results</p>
          {results.map((job) => {
            const jobTracked = tracked.get(job.url)
            const isTracking = tracking === job.url

            return (
              <div key={job.url} className="bg-gray-900 rounded-xl px-4 py-3 flex items-start gap-4">
                {/* Left: job info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-gray-500 capitalize">{job.source}</span>
                    {job.location && (
                      <span className="text-xs text-gray-600">· {job.location}</span>
                    )}
                    {job.strong_match && (
                      <span className="bg-green-700/40 text-green-300 text-xs font-semibold px-2 py-0.5 rounded-full">
                        ⚡ Strong Match
                      </span>
                    )}
                    {job.score !== undefined && !job.strong_match && job.score > 0 && (
                      <span className="text-gray-500 text-xs">
                        {Math.round(job.score * 100)}% match
                      </span>
                    )}
                  </div>

                  <p className="text-white font-semibold mt-0.5 truncate">{job.title}</p>
                  <p className="text-gray-400 text-sm">{job.company}</p>

                  {job.description && (
                    <p className="text-gray-500 text-xs mt-1 line-clamp-2">{job.description}</p>
                  )}

                  {job.missing_skills && job.missing_skills.length > 0 && (
                    <p className="text-gray-600 text-xs mt-1">
                      Missing: {job.missing_skills.slice(0, 5).join(", ")}
                      {job.missing_skills.length > 5 && ` +${job.missing_skills.length - 5} more`}
                    </p>
                  )}
                </div>

                {/* Right: actions */}
                <div className="flex flex-col gap-2 flex-shrink-0 items-end">
                  {jobTracked ? (
                    <span className="text-green-400 text-xs font-semibold">
                      ✓ {jobTracked === "save" ? "Saved" : "Applied"}
                    </span>
                  ) : (
                    <>
                      <button
                        onClick={() => handleTrack(job, "save")}
                        disabled={isTracking}
                        className="bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50 transition-colors"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => handleTrack(job, "apply")}
                        disabled={isTracking}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50 transition-colors"
                      >
                        Applied
                      </button>
                    </>
                  )}
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-indigo-400 hover:text-indigo-300 border border-indigo-700 hover:border-indigo-500 px-2.5 py-1 rounded-lg transition-colors"
                  >
                    Open ↗
                  </a>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
