# Jobee — AI-Powered Job Hunter

> Find jobs, track applications, and let AI do the heavy lifting.

Jobee is a full-stack job-hunting platform that combines real-time LinkedIn scraping, AI-driven CV matching, Gmail inbox parsing, and a drag-and-drop Kanban board — all in one place. Built with **FastAPI**, **Supabase**, and **React + TypeScript**.

---

## Features

### 🔍 AI Job Search
- Scrapes **LinkedIn** in real time based on your query, location, and time filters (24h / 7d / 30d)
- Results are cached for 15 minutes to avoid redundant scraping
- When a CV is uploaded, every result is **ranked by match score** using an LLM-powered semantic matcher
- Match score, matched keywords, and skill gaps are shown on each job card

### 📄 CV Upload & Parsing
- Upload your CV as **PDF, DOCX, or TXT** (up to 5 MB)
- Text is extracted server-side and stored in Supabase Storage
- The extracted text is used as context for all AI-matching and tailoring features

### 📬 Gmail Sync (AI-Powered)
- Connect Gmail with **read-only OAuth** — Jobee never stores email bodies
- Fetches job-related emails and uses an LLM to extract: company, role, and application status
- Detected statuses: `applied`, `interview`, `offer`, `rejected`
- Shows a **review modal** with editable rows before anything is saved
- Full deduplication via `gmail_message_id` — re-syncing never creates duplicates
- Already-imported items are flagged so you can skip or re-import them

### 🗂 Kanban Application Tracker
- Drag-and-drop board with columns: **Saved → Applied → Interview → Offer → Rejected**
- Built with `@dnd-kit` — smooth, accessible drag interactions
- Add notes, update status, and delete applications directly from the board
- Applications created from job search or Gmail sync all flow into the same board

### 🔐 Authentication
- JWT-based auth backed by **Supabase Auth**
- Google OAuth for sign-in and Gmail token management
- All endpoints protected; tokens refreshed transparently

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Database & Auth | Supabase (PostgreSQL + Auth + Storage) |
| AI / Matching | OpenAI API (embeddings + chat completions) |
| Scraping | Playwright, BeautifulSoup (LinkedIn) |
| Frontend | React 18, TypeScript, Vite |
| Drag & Drop | @dnd-kit/core, @dnd-kit/sortable |
| Deployment | Vercel (frontend), any ASGI host (backend) |

---

## Project Structure

```
app/
  main.py               # FastAPI app, CORS, router registration
  schemas.py            # Shared Pydantic schemas
  api/
    auth.py             # JWT auth + Google OAuth
    cv.py               # CV upload, text extraction, signed URLs
    jobs.py             # LinkedIn scraping, AI ranking, save/apply actions
    applications.py     # CRUD for the Kanban board
    integrations.py     # Gmail preview & import endpoints
  core/
    config.py           # Settings (env vars via pydantic-settings)
  db/
    session.py          # Supabase client factory
    crud.py             # All DB queries
  services/
    matcher.py          # LLM-based CV ↔ job matching engine
    gmail_parser.py     # Gmail OAuth token refresh + email parsing
    scraper/
      base.py           # Abstract scraper interface
      linkedin.py       # LinkedIn scraper (Playwright)

frontend/src/
  api.ts                # Typed API client (all fetch calls)
  App.tsx               # Route layout
  AuthContext.tsx        # Global auth state
  pages/
    LoginPage.tsx        # Google sign-in
    JobsPage.tsx         # Search + results + track actions
    KanbanBoard.tsx      # Drag-and-drop board + Gmail sync modal
    CVPage.tsx           # CV upload & management
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project
- An [OpenAI](https://platform.openai.com) API key
- Google OAuth credentials (for sign-in + Gmail)

### Backend

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
JWT_SECRET=your-supabase-jwt-secret
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
STORAGE_BUCKET=cvs
CORS_ORIGINS=http://localhost:5173
```

```bash
uvicorn app.main:app --reload
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App at http://localhost:5173
```

---

## API Overview

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/google` | Exchange Google token, return JWT |
| `POST` | `/cv/upload` | Upload CV file |
| `GET` | `/cv/` | Get current CV metadata + signed URL |
| `POST` | `/jobs/search` | Scrape jobs, optionally rank by CV |
| `POST` | `/jobs/action` | Save or apply to a job |
| `GET` | `/applications/` | List all applications (Kanban data) |
| `PATCH` | `/applications/{id}` | Update status or notes |
| `DELETE` | `/applications/{id}` | Delete an application |
| `GET` | `/integrations/gmail/status` | Check Gmail connection |
| `GET` | `/integrations/gmail/preview` | Parse inbox, return preview list |
| `POST` | `/integrations/gmail/import` | Save confirmed items as applications |

---

## Roadmap

- [ ] **Tailor CV** — one-click LLM rewrite of your CV against a specific job description
- [ ] **More job sources** — Glassdoor, Wellfound, Remotive, local boards
- [ ] **Dismiss jobs** — hide uninteresting listings permanently
- [ ] **Interview prep** — AI-generated Q&A based on job description + your CV
- [ ] **Full UI redesign** — Shadcn/ui + Tailwind, dark mode, mobile layout

---

## License

MIT
