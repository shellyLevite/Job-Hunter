import { useCallback, useEffect, useRef, useState } from 'react'
import { uploadCv, fetchLatestCv, type CvRecord } from '../api'

const ACCEPTED = '.pdf,.doc,.docx,.txt'
const MAX_MB = 5

export default function CVPage() {
  const [cv, setCv] = useState<CvRecord | null>(null)
  const [loadingCv, setLoadingCv] = useState(true)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const loadCv = useCallback(async () => {
    try {
      const record = await fetchLatestCv()
      setCv(record)
    } catch {
      setCv(null)
    } finally {
      setLoadingCv(false)
    }
  }, [])

  useEffect(() => { loadCv() }, [loadCv])

  const handleFile = async (file: File) => {
    setUploadError(null)
    setUploadSuccess(false)

    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!['pdf', 'doc', 'docx', 'txt'].includes(ext)) {
      setUploadError('Only PDF, DOC, DOCX and TXT files are allowed.')
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setUploadError(`File must be under ${MAX_MB} MB.`)
      return
    }

    setUploading(true)
    try {
      await uploadCv(file)
      setUploadSuccess(true)
      await loadCv()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Upload failed. Please try again.'
      setUploadError(msg)
    } finally {
      setUploading(false)
    }
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, {
      day: 'numeric', month: 'short', year: 'numeric',
    })

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-6">
      {/* ── Upload card ─────────────────────────────── */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-base font-semibold mb-4 text-white">Upload CV</h3>

        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`
            relative flex flex-col items-center justify-center gap-3
            rounded-xl border-2 border-dashed cursor-pointer
            transition-colors py-12 px-6 text-center select-none
            ${dragging
              ? 'border-indigo-400 bg-indigo-950/40'
              : 'border-gray-700 hover:border-indigo-500 hover:bg-gray-800/40'}
          `}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            onChange={onInputChange}
          />

          {uploading ? (
            <>
              <svg className="animate-spin w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <p className="text-gray-400 text-sm">Uploading…</p>
            </>
          ) : (
            <>
              <svg className="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <div>
                <p className="text-white text-sm font-medium">
                  Drop your CV here, or <span className="text-indigo-400 underline">browse</span>
                </p>
                <p className="text-gray-500 text-xs mt-1">PDF, DOC, DOCX, TXT · max {MAX_MB} MB</p>
              </div>
            </>
          )}
        </div>

        {uploadError && (
          <p className="mt-3 text-sm text-red-400 flex items-center gap-1.5">
            <span>⚠</span> {uploadError}
          </p>
        )}
        {uploadSuccess && (
          <p className="mt-3 text-sm text-green-400 flex items-center gap-1.5">
            <span>✓</span> CV uploaded successfully!
          </p>
        )}
      </div>

      {/* ── Current CV card ─────────────────────────── */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-base font-semibold mb-4 text-white">Current CV</h3>

        {loadingCv ? (
          <p className="text-gray-500 text-sm">Loading…</p>
        ) : cv ? (
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              {/* file icon */}
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-indigo-950 flex items-center justify-center">
                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-white text-sm font-medium truncate">{cv.filename}</p>
                <p className="text-gray-500 text-xs mt-0.5">Uploaded {fmt(cv.created_at)}</p>
              </div>
            </div>

            {cv.signed_url && (
              <a
                href={cv.signed_url}
                target="_blank"
                rel="noreferrer"
                className="flex-shrink-0 flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300 border border-indigo-800 hover:border-indigo-500 px-3 py-1.5 rounded-lg transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                View
              </a>
            )}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No CV uploaded yet. Use the form above to upload one.</p>
        )}
      </div>
    </div>
  )
}
