const BACKEND = import.meta.env.VITE_API_URL ?? ''

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <span className="text-indigo-400 font-bold text-xl">Job Hunter</span>
        <a
          href={`${BACKEND}/auth/google/login`}
          className="flex items-center gap-2 bg-white hover:bg-gray-100 text-gray-800 font-semibold rounded-lg px-4 py-2 text-sm transition-colors"
        >
          <GoogleIcon />
          Sign in with Google
        </a>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-16 text-center">
        <h1 className="text-5xl font-extrabold text-white mb-4">Job Hunter</h1>
        <p className="text-indigo-400 text-lg font-medium mb-6">Your AI-powered job search companion</p>

        <p className="text-gray-300 max-w-xl text-base leading-relaxed mb-10">
          Job Hunter helps you organise and automate your entire job search in one place.
          Upload your CV, browse open positions, and let AI match you with the best opportunities.
          Track every application on a visual Kanban board, and automatically import status updates
          straight from your Gmail inbox — so you never miss an interview invitation or deadline.
        </p>

        {/* Feature highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-2xl w-full mb-12">
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="text-2xl mb-2">📋</div>
            <h3 className="font-semibold text-white mb-1">Kanban Board</h3>
            <p className="text-gray-400 text-sm">Visualise every stage of your applications from applied to offer.</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="text-2xl mb-2">🤖</div>
            <h3 className="font-semibold text-white mb-1">AI Matching</h3>
            <p className="text-gray-400 text-sm">Upload your CV and get instant AI-powered job match scores.</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="text-2xl mb-2">📧</div>
            <h3 className="font-semibold text-white mb-1">Gmail Integration</h3>
            <p className="text-gray-400 text-sm">Automatically detect application updates from your inbox.</p>
          </div>
        </div>

        <a
          href={`${BACKEND}/auth/google/login`}
          className="flex items-center justify-center gap-3 bg-white hover:bg-gray-100 text-gray-800 font-semibold rounded-xl py-3 px-8 text-base transition-colors shadow-lg"
        >
          <GoogleIcon />
          Get started with Google
        </a>
      </main>

      {/* Footer */}
      <footer className="flex-shrink-0 border-t border-gray-800 px-6 py-4 text-center text-gray-500 text-sm">
        <span>© {new Date().getFullYear()} Job Hunter.&nbsp;</span>
        <a href="/privacy" className="text-indigo-400 hover:text-indigo-300 underline transition-colors">
          Privacy Policy
        </a>
      </footer>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
      <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908C16.658 14.013 17.64 11.705 17.64 9.2z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" />
      <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z" />
    </svg>
  )
}
