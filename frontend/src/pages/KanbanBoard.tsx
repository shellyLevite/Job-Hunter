import { useEffect, useState } from 'react'
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
  type Application,
  type AppStatus,
} from '../api'

const COLUMNS: { id: AppStatus; label: string; color: string }[] = [
  { id: 'saved',     label: '🔖 Saved',      color: 'bg-gray-700' },
  { id: 'applied',   label: '📤 Applied',    color: 'bg-blue-800' },
  { id: 'interview', label: '🎙 Interview',  color: 'bg-yellow-700' },
  { id: 'offer',     label: '🎉 Offer',      color: 'bg-green-800' },
  { id: 'rejected',  label: '❌ Rejected',   color: 'bg-red-900' },
]

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
          className={`flex-1 overflow-y-auto space-y-3 pr-1 rounded-xl transition-colors ${
            isOver ? 'ring-2 ring-indigo-500/60 bg-indigo-950/20' : ''
          }`}
        >
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

  useEffect(() => {
    fetchApplications()
      .then((data) => setApps(data))
      .catch(() => setError('Failed to load applications.'))
      .finally(() => setLoading(false))
  }, [])

  const byStatus = (status: AppStatus) => apps.filter((a) => a.status === status)

  const handleDragStart = ({ active }: DragStartEvent) => setActiveId(active.id as string)

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    setActiveId(null)
    if (!over) return
    const draggedId = active.id as string
    const targetId = over.id as string

    // Determine the target column
    const col = COLUMNS.find((c) => c.id === targetId)
    const newStatus: AppStatus | undefined = col ? col.id : apps.find((a) => a.id === targetId)?.status

    if (!newStatus) return
    const app = apps.find((a) => a.id === draggedId)
    if (!app || app.status === newStatus) return

    // Optimistic update — roll back on API failure so the board stays consistent
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

  const activeApp = apps.find((a) => a.id === activeId)

  if (loading) return <div className="text-gray-400 p-8">Loading applications…</div>
  if (error) return <div className="text-red-400 p-8">{error}</div>

  return (
    <>
      {editingApp && (
        <EditModal app={editingApp} onClose={() => setEditingApp(null)} onSave={handleSave} />
      )}
      <DndContext collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="flex gap-3 h-full">
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
    </>
  )
}
