import { useCallback, useEffect, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  closestCenter,
  useDroppable,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  fetchApplications,
  updateApplication,
  deleteApplication,
  checkGmailStatus,
  fetchGmailPreview,
  importGmailApplications,
  type Application,
  type AppStatus,
  type GmailPreviewItem,
  type GmailImportItem,
} from '../api'

const COLUMNS: { id: AppStatus; label: string; color: string }[] = [
  { id: 'saved',     label: '🔖 Saved',      color: 'bg-gray-700' },
  { id: 'applied',   label: '📤 Applied',    color: 'bg-blue-800' },
  { id: 'interview', label: '🎙 Interview',  color: 'bg-yellow-700' },
  { id: 'offer',     label: '🎉 Offer',      color: 'bg-green-800' },
  { id: 'rejected',  label: '❌ Rejected',   color: 'bg-red-900' },
]

// ── Gmail Sync Modal ──────────────────────────────────────────────────────────

type EditableItem = Omit<GmailPreviewItem, 'already_imported'>

type ModalPhase =
  | { phase: 'checking' }
  | { phase: 'not_connected' }
  | { phase: 'fetching' }
  | { phase: 'preview'; items: EditableItem[]; skippedCount: number }
  | { phase: 'importing' }
  | { phase: 'done'; created: number }
  | { phase: 'error'; message: string }

function PreviewTable({
  items: init,
  skippedCount,
  onImport,
  onRefetch,
}: {
  items: EditableItem[]
  skippedCount: number
  onImport: (items: GmailImportItem[]) => void
  onRefetch: () => void
}) {
  const [items, setItems] = useState<EditableItem[]>(init)

  const update = (idx: number, field: keyof EditableItem, value: string) =>
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)))

  const remove = (idx: number) => setItems((prev) => prev.filter((_, i) => i !== idx))

  if (items.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 py-10">
        <p className="text-gray-400 text-center text-sm">
          {skippedCount > 0
            ? `All ${skippedCount} detected email${skippedCount !== 1 ? 's were' : ' was'} already imported.`
            : 'No new job application emails found in your inbox.'}
        </p>
        <button onClick={onRefetch} className="text-indigo-400 hover:text-indigo-300 text-sm">
          Refresh
        </button>
      </div>
    )
  }

  return (
    <>
      {skippedCount > 0 && (
        <p className="text-gray-500 text-xs mb-2">
          {skippedCount} email{skippedCount !== 1 ? 's' : ''} already imported — showing only new
          ones.
        </p>
      )}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-800">
              <th className="text-left pb-2 pr-3 font-medium">Company</th>
              <th className="text-left pb-2 pr-3 font-medium">Role</th>
              <th className="text-left pb-2 pr-3 font-medium">Status</th>
              <th className="text-left pb-2 pr-3 font-medium">Date</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {items.map((item, i) => (
              <tr key={item.message_id}>
                <td className="py-2 pr-3">
                  <input
                    value={item.company}
                    onChange={(e) => update(i, 'company', e.target.value)}
                    className="w-full bg-gray-800 text-white rounded px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </td>
                <td className="py-2 pr-3">
                  <input
                    value={item.role}
                    onChange={(e) => update(i, 'role', e.target.value)}
                    className="w-full bg-gray-800 text-white rounded px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </td>
                <td className="py-2 pr-3">
                  <select
                    value={item.status}
                    onChange={(e) => update(i, 'status', e.target.value as AppStatus)}
                    className="bg-gray-800 text-white rounded px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="applied">Applied</option>
                    <option value="interview">Interview</option>
                    <option value="offer">Offer</option>
                    <option value="rejected">Rejected</option>
                    <option value="saved">Saved</option>
                  </select>
                </td>
                <td className="py-2 pr-3 text-gray-400 text-xs whitespace-nowrap">
                  {new Date(item.email_date).toLocaleDateString()}
                </td>
                <td className="py-2">
                  <button
                    onClick={() => remove(i)}
                    className="text-red-500 hover:text-red-400 text-xs"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-800 flex-shrink-0">
        <span className="text-gray-500 text-xs">
          {items.length} application{items.length !== 1 ? 's' : ''} to import
        </span>
        <button
          onClick={() => onImport(items)}
          className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-5 py-2 rounded-lg text-sm"
        >
          Import All
        </button>
      </div>
    </>
  )
}

function GmailSyncModal({
  onClose,
  onImported,
  autoFetch = false,
}: {
  onClose: () => void
  onImported: (count: number) => void
  autoFetch?: boolean
}) {
  const [phase, setPhase] = useState<ModalPhase>(
    autoFetch ? { phase: 'fetching' } : { phase: 'checking' },
  )

  const doFetch = useCallback(async () => {
    setPhase({ phase: 'fetching' })
    try {
      const preview = await fetchGmailPreview()
      const skippedCount = preview.filter((i) => i.already_imported).length
      const items: EditableItem[] = preview
        .filter((i) => !i.already_imported)
        .map(({ already_imported: _skip, ...rest }) => rest)
      setPhase({ phase: 'preview', items, skippedCount })
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to fetch Gmail preview.'
      setPhase({ phase: 'error', message: msg })
    }
  }, [])

  const checkAndFetch = useCallback(async () => {
    setPhase({ phase: 'checking' })
    try {
      const { connected } = await checkGmailStatus()
      if (connected) {
        await doFetch()
      } else {
        setPhase({ phase: 'not_connected' })
      }
    } catch {
      setPhase({ phase: 'error', message: 'Failed to check Gmail connection.' })
    }
  }, [doFetch])

  useEffect(() => {
    if (autoFetch) {
      void doFetch()
    } else {
      void checkAndFetch()
    }
  }, [autoFetch, doFetch, checkAndFetch])

  const handleImport = async (items: GmailImportItem[]) => {
    setPhase({ phase: 'importing' })
    try {
      const result = await importGmailApplications(items)
      onImported(result.created)
      setPhase({ phase: 'done', created: result.created })
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Import failed.'
      setPhase({ phase: 'error', message: msg })
    }
  }

  const spinner = (label: string) => (
    <div className="flex-1 flex items-center justify-center text-gray-400 py-10 text-sm">
      {label}
    </div>
  )

  const isBusy = phase.phase === 'importing' || phase.phase === 'checking' || phase.phase === 'fetching'

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={isBusy ? undefined : onClose}
    >
      <div
        className="bg-gray-900 rounded-2xl p-6 w-full max-w-2xl shadow-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 className="text-white font-bold text-lg">Sync from Gmail</h2>
          <button
            onClick={onClose}
            disabled={isBusy}
            className="text-gray-500 hover:text-white text-2xl leading-none disabled:opacity-30 disabled:cursor-not-allowed"
          >
            ×
          </button>
        </div>

        {/* Body */}
        {phase.phase === 'checking' && spinner('Checking Gmail connection…')}

        {phase.phase === 'not_connected' && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 py-10">
            <p className="text-gray-300 text-center text-sm max-w-sm">
              Connect your Gmail account so Jobee can detect job applications from your inbox
              automatically.
            </p>
            <a
              href="/auth/google/gmail-connect"
              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-6 py-2.5 rounded-lg text-sm"
            >
              Connect Gmail
            </a>
          </div>
        )}

        {phase.phase === 'fetching' && spinner('Scanning your inbox…')}

        {phase.phase === 'preview' && (
          <PreviewTable
            items={phase.items}
            skippedCount={phase.skippedCount}
            onImport={handleImport}
            onRefetch={doFetch}
          />
        )}

        {phase.phase === 'importing' && spinner('Importing applications…')}

        {phase.phase === 'done' && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 py-10">
            <p className="text-green-400 font-semibold text-lg">✓ Done!</p>
            <p className="text-gray-300 text-sm">
              Imported {phase.created} new application{phase.created !== 1 ? 's' : ''}.
            </p>
            <button
              onClick={onClose}
              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-6 py-2.5 rounded-lg text-sm"
            >
              Close
            </button>
          </div>
        )}

        {phase.phase === 'error' && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 py-10">
            <p className="text-red-400 text-sm text-center">{phase.message}</p>
            <button
              onClick={() => void checkAndFetch()}
              className="text-indigo-400 hover:text-indigo-300 text-sm"
            >
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Card ─────────────────────────────────────────────────────────────────────

function AppCard({
  app,
  onDelete,
  onEdit,
  isDragging = false,
}: {
  app: Application
  onDelete: (id: string) => void
  onEdit: (app: Application) => void
  isDragging?: boolean
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: app.id })
  const style = { transform: CSS.Transform.toString(transform), transition }
  const job = app.jobs

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`bg-gray-800 rounded-xl p-4 shadow cursor-grab active:cursor-grabbing select-none ${isDragging ? 'opacity-50' : ''}`}
    >
      <p className="text-white font-semibold text-sm leading-tight">{job?.title ?? '(unknown role)'}</p>
      <p className="text-gray-400 text-xs mt-0.5">{job?.company}</p>
      {job?.location && <p className="text-gray-500 text-xs">{job.location}</p>}
      {app.notes && <p className="text-gray-400 text-xs mt-2 italic line-clamp-2">{app.notes}</p>}
      <div className="flex gap-2 mt-3">
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => onEdit(app)}
          className="text-xs text-indigo-400 hover:text-indigo-300"
        >
          Edit
        </button>
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => onDelete(app.id)}
          className="text-xs text-red-400 hover:text-red-300"
        >
          Delete
        </button>
        {job?.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            onPointerDown={(e) => e.stopPropagation()}
            className="ml-auto text-xs text-gray-500 hover:text-gray-300"
          >
            View ↗
          </a>
        )}
      </div>
    </div>
  )
}

// ── Edit Modal ────────────────────────────────────────────────────────────────

function EditModal({ app, onClose, onSave }: { app: Application; onClose: () => void; onSave: (a: Application) => void }) {
  const [notes, setNotes] = useState(app.notes ?? '')
  const [appliedAt, setAppliedAt] = useState(app.applied_at ? app.applied_at.slice(0, 10) : '')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await updateApplication(app.id, {
        notes: notes || undefined,
        applied_at: appliedAt ? new Date(appliedAt).toISOString() : undefined,
      })
      onSave(updated)
      onClose()
    } catch {
      setSaveError('Failed to save changes. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-900 rounded-2xl p-6 w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-white font-bold text-lg mb-4">Edit Application</h2>
        <p className="text-gray-300 font-medium">{app.jobs?.title}</p>
        <p className="text-gray-500 text-sm mb-4">{app.jobs?.company}</p>

        <label className="block text-gray-400 text-sm mb-1">Notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="w-full bg-gray-800 text-white rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500 mb-4 resize-none"
          placeholder="Add notes…"
        />

        <label className="block text-gray-400 text-sm mb-1">Applied date</label>
        <input
          type="date"
          value={appliedAt}
          onChange={(e) => setAppliedAt(e.target.value)}
          className="w-full bg-gray-800 text-white rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500 mb-6"
        />

        {saveError && (
          <p className="text-red-400 text-xs mb-3">{saveError}</p>
        )}
        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="text-gray-400 hover:text-white text-sm px-4 py-2">Cancel</button>
          <button
            onClick={save}
            disabled={saving}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold px-5 py-2 rounded-lg disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Droppable Column ─────────────────────────────────────────────────────────

function DroppableColumn({
  col,
  colApps,
  activeId,
  onDelete,
  onEdit,
}: {
  col: typeof COLUMNS[number]
  colApps: Application[]
  activeId: string | null
  onDelete: (id: string) => void
  onEdit: (app: Application) => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: col.id })

  return (
    <div className="flex-1 min-w-0 flex flex-col h-full">
      {/* Column header */}
      <div className={`${col.color} rounded-xl px-3 py-2 mb-3 flex items-center justify-between flex-shrink-0`}>
        <span className="text-white font-semibold text-sm">{col.label}</span>
        <span className="bg-black/30 text-white text-xs rounded-full px-2 py-0.5">{colApps.length}</span>
      </div>

      <SortableContext items={colApps.map((a) => a.id)} strategy={verticalListSortingStrategy}>
        <div
          ref={setNodeRef}
          className={`flex-1 rounded-xl transition-colors ${
            isOver ? 'ring-2 ring-indigo-500/60 bg-indigo-950/20' : ''
          }`}
          style={{ overflowY: 'auto', scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}
        >
          <div className="space-y-3 pr-1 pb-2">
            {colApps.map((app) => (
              <AppCard
                key={app.id}
                app={app}
                onDelete={onDelete}
                onEdit={onEdit}
                isDragging={app.id === activeId}
              />
            ))}
            {colApps.length === 0 && (
              <div className="border-2 border-dashed border-gray-700 rounded-xl h-16 flex items-center justify-center text-gray-600 text-xs">
                Drop here
              </div>
            )}
          </div>
        </div>
      </SortableContext>
    </div>
  )
}

// ── Main Board ────────────────────────────────────────────────────────────────

export default function KanbanBoard() {
  const [apps, setApps] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [editingApp, setEditingApp] = useState<Application | null>(null)
  const [gmailModalOpen, setGmailModalOpen] = useState(false)
  const [autoFetch, setAutoFetch] = useState(false)

  useEffect(() => {
    fetchApplications()
      .then((data) => setApps(data))
      .catch(() => setError('Failed to load applications.'))
      .finally(() => setLoading(false))

    // Auto-open Gmail modal after OAuth redirect
    const params = new URLSearchParams(window.location.search)
    if (params.get('gmail_connected') === '1') {
      setAutoFetch(true)
      setGmailModalOpen(true)
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  const refreshApps = () =>
    fetchApplications()
      .then(setApps)
      .catch((err) => console.error('Failed to refresh applications after Gmail import:', err))

  const byStatus = (status: AppStatus) => apps.filter((a) => a.status === status)

  const handleDragStart = ({ active }: DragStartEvent) => setActiveId(active.id as string)

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    setActiveId(null)
    if (!over) return
    const draggedId = active.id as string
    const targetId = over.id as string

    const col = COLUMNS.find((c) => c.id === targetId)
    const newStatus: AppStatus | undefined = col ? col.id : apps.find((a) => a.id === targetId)?.status

    if (!newStatus) return
    const app = apps.find((a) => a.id === draggedId)
    if (!app || app.status === newStatus) return

    const snapshot = apps
    setApps((prev) => prev.map((a) => a.id === draggedId ? { ...a, status: newStatus } : a))
    try {
      await updateApplication(draggedId, { status: newStatus })
    } catch {
      setApps(snapshot)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Remove this application?')) return
    try {
      await deleteApplication(id)
      setApps((prev) => prev.filter((a) => a.id !== id))
    } catch {
      // Delete failed — UI state is unchanged
    }
  }

  const handleSave = (updated: Application) => {
    setApps((prev) => prev.map((a) => a.id === updated.id ? updated : a))
  }

  const openGmailModal = () => {
    setAutoFetch(false)
    setGmailModalOpen(true)
  }

  const activeApp = apps.find((a) => a.id === activeId)

  if (loading) return <div className="text-gray-400 p-8">Loading applications…</div>
  if (error) return <div className="text-red-400 p-8">{error}</div>

  return (
    <div className="flex flex-col h-full">
      {/* Board header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <h2 className="text-xl font-bold text-white">Application Tracker</h2>
        <button
          onClick={openGmailModal}
          className="flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white text-sm px-3 py-1.5 rounded-lg transition-colors"
        >
          ✉ Sync from Gmail
        </button>
      </div>

      {/* Gmail sync modal */}
      {gmailModalOpen && (
        <GmailSyncModal
          onClose={() => setGmailModalOpen(false)}
          onImported={(count) => {
            setGmailModalOpen(false)
            if (count > 0) void refreshApps()
          }}
          autoFetch={autoFetch}
        />
      )}

      {/* Edit modal */}
      {editingApp && (
        <EditModal app={editingApp} onClose={() => setEditingApp(null)} onSave={handleSave} />
      )}

      <DndContext collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="flex gap-3 flex-1 min-h-0">
          {COLUMNS.map((col) => (
            <DroppableColumn
              key={col.id}
              col={col}
              colApps={byStatus(col.id)}
              activeId={activeId}
              onDelete={handleDelete}
              onEdit={setEditingApp}
            />
          ))}
        </div>

        <DragOverlay>
          {activeApp && (
            <div className="bg-gray-800 rounded-xl p-4 shadow-2xl opacity-90">
              <p className="text-white font-semibold text-sm">{activeApp.jobs?.title}</p>
              <p className="text-gray-400 text-xs mt-0.5">{activeApp.jobs?.company}</p>
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
