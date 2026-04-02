export default function PrivacyPage() {
  return (
    <div className="min-h-screen w-full bg-gray-950 text-gray-300 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold text-white mb-2">Privacy Policy</h1>
      <p className="text-gray-500 text-sm mb-8">Last updated: April 2, 2026</p>

      <section className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-2">1. What we collect</h2>
        <p>
          JobHunter AI collects your Google account email address when you sign in with Google.
          If you connect your Gmail account, we read your emails solely to identify job application
          status updates (e.g. interview invitations, rejections). We do not store the full content
          of your emails.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-2">2. How we use your data</h2>
        <ul className="list-disc list-inside space-y-1">
          <li>To authenticate you and maintain your session.</li>
          <li>To display and manage your job applications on your Kanban board.</li>
          <li>To match job listings against your uploaded CV using AI.</li>
          <li>To parse Gmail messages for job application updates (only when you explicitly connect Gmail).</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-2">3. Data sharing</h2>
        <p>
          We do not sell, rent, or share your personal data with third parties. Your data is stored
          securely in Supabase and is only accessible by you.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-2">4. Google API data</h2>
        <p>
          JobHunter AI's use of information received from Google APIs adheres to the{' '}
          <a
            href="https://developers.google.com/terms/api-services-user-data-policy"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-400 underline"
          >
            Google API Services User Data Policy
          </a>
          , including the Limited Use requirements.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-2">5. Data retention</h2>
        <p>
          Your data is retained as long as your account is active. You may request deletion of your
          account and all associated data at any time by contacting us.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-2">6. Contact</h2>
        <p>
          For any privacy-related questions, contact us at:{' '}
          <a href="mailto:levite2002@gmail.com" className="text-indigo-400 underline">
            levite2002@gmail.com
          </a>
        </p>
      </section>
    </div>
    </div>
  )
}
