import { useState } from 'react'
import { useAuth } from './AuthContext'
import LoginPage from './pages/LoginPage'
import KanbanBoard from './pages/KanbanBoard'
import JobsPage from './pages/JobsPage'
import CVPage from './pages/CVPage'

type Tab = 'board' | 'jobs' | 'cv'

export default function App() {
  const { userEmail, isLoading, logout } = useAuth()
  const [tab, setTab] = useState<Tab>('board')

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-950 text-gray-400">
        Loading…
      </div>
    )
  }

  if (!userEmail) return <LoginPage />

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-white overflow-hidden">
      <header className="flex-shrink-0 bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <span className="text-indigo-400 font-bold text-lg">JobHunter AI</span>
          <nav className="flex gap-1">
            <button
              onClick={() => setTab('board')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === 'board' ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              My Applications
            </button>
            <button
              onClick={() => setTab('jobs')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === 'jobs' ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Browse Jobs
            </button>
            <button
              onClick={() => setTab('cv')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === 'cv' ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              My CV
            </button>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-gray-400 text-sm">{userEmail}</span>
          <button
            onClick={() => void logout()}
            className="text-gray-500 hover:text-red-400 text-sm transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="flex-1 flex flex-col min-h-0 px-6 pt-5 pb-4 w-full">
        {tab === 'board' ? (
          <>
            <h2 className="flex-shrink-0 text-xl font-bold mb-4">Application Tracker</h2>
            <div className="flex-1 min-h-0">
              <KanbanBoard />
            </div>
          </>
        ) : tab === 'jobs' ? (
          <>
            <div className="flex-1 min-h-0 overflow-y-auto">
              <JobsPage />
            </div>
          </>
        ) : (
          <>
            <h2 className="flex-shrink-0 text-xl font-bold mb-4">My CV</h2>
            <div className="flex-1 min-h-0 overflow-y-auto">
              <CVPage />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
