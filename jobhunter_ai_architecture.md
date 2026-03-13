# Jobee — Next Steps

---

### 1. Gmail Inbox → Application Tracker Sync

Read the user's Gmail inbox to detect job application-related emails, infer the status of each application, and let the user review and import them into the Kanban board in one click.

**Trigger options (user chooses):**
- **Manual sync** — button in the UI ("Sync from Gmail")
- **Push notifications** — Gmail Pub/Sub webhook fires whenever a new relevant email arrives (requires a public endpoint; can use a queue or polling fallback in dev)
- **Scheduled** — background job runs every X hours (configurable: 1h / 6h / daily)

**Flow:**
1. User grants Gmail **read-only** scope (Google OAuth already set up — just add the scope)
2. Backend fetches recent emails and filters by patterns that signal job activity:
   - "Thank you for applying…", "We received your application…" → `applied`
   - "We'd like to schedule an interview…", "Interview invitation…" → `interview`
   - "Unfortunately…", "We will not be moving forward…" → `rejected`
   - "We are pleased to offer…", "Offer letter…" → `offer`
3. LLM (or regex fallback) extracts: **company name**, **role title**, **status**, **email date**
4. Backend returns a **preview list** — not saved yet — showing each detected application with its inferred status
5. User sees a review UI: can **edit** any field (company, role, status), **remove** individual rows they don't want, then clicks **"Import All"**
6. One API call creates/updates all confirmed rows in `applications` with the correct status

**Endpoints to add:**
```
POST /auth/google/gmail-connect        -- request Gmail read scope
GET  /integrations/gmail/preview       -- fetch & parse inbox, return preview list (not saved)
POST /integrations/gmail/import        -- save the confirmed list as application records
POST /integrations/gmail/webhook       -- Gmail Pub/Sub push endpoint
```

**DB addition:**
```
applications
  + source          text   -- 'manual' | 'gmail_sync'
  + gmail_message_id text  -- for dedup; skip re-importing same message
```

**Notes:**
- Never store full email bodies — extract fields and discard
- Use `gmail_message_id` to deduplicate: skip any message already imported
- Store the Gmail `history_id` so incremental syncs only fetch new messages
- Make the entire feature opt-in; users who don't connect Gmail see no difference
- Conflict resolution: if an application for the same company + role already exists, show a merge prompt rather than creating a duplicate

---

### 2. Better and More Job Queries

Expand scraping coverage and query quality so users see more relevant, fresher listings.

**Improvements:**
- **More sources** — add scrapers for Glassdoor, Wellfound (AngelList), Remotive, and local job boards (e.g. Drushim, AllJobs for Israeli market)
- **Smarter queries** — generate query variants from the user's CV (synonyms, related titles) instead of a single keyword; e.g. "Software Engineer" → also queries "SWE", "Backend Developer", "Python Developer"
- **Location flexibility** — support remote + hybrid filters per source
- **Deduplication** — hash job title + company + location to skip re-scraping duplicates across sources
- **Freshness** — store `scraped_at` per job and prefer listings posted within the last 7 days; re-scrape stale results on demand

**Endpoints to extend:**
```
GET /jobs/search   -- add `sources[]`, `date_range`, `remote_only` query params
```

---

### 3. Tailor CV Button

A one-click feature that rewrites (or annotates) the user's CV to better match a specific job description, boosting ATS pass-through rates.

**Flow:**
1. User clicks **Tailor CV** on any job card
2. Backend sends the CV text + job description to the LLM with a tailoring prompt
3. LLM returns a rewritten CV (or a diff of suggested changes)
4. Frontend shows a side-by-side: original vs. tailored
5. User can download the tailored version as a PDF or copy it to clipboard

**Endpoints to add:**
```
POST /cv/tailor/{job_id}      -- returns tailored CV text
GET  /cv/tailored/{job_id}    -- retrieve a previously tailored version
```

**DB addition:**
```
tailored_cvs
  id           uuid
  user_id      uuid
  job_id       uuid
  content      text
  created_at   timestamp
```

**Notes:**
- Cache the tailored version per (user, job) pair — regenerate only if the base CV changes
- Highlight changed sections in the diff view with color coding
- Keep the original CV untouched; tailored versions are always separate documents

---

### 4. Dismiss Job Button

Let users quickly hide jobs they are not interested in so they never resurface in search results or the job list.

**Flow:**
1. User clicks **Dismiss** (✕) on a job card
2. Job is soft-deleted from the user's feed via a `dismissed_jobs` join table
3. All future searches automatically exclude dismissed jobs for that user
4. Optional **Undo** toast for 5 seconds after dismissal

**Endpoint to add:**
```
POST   /jobs/{job_id}/dismiss    -- mark job as dismissed
DELETE /jobs/{job_id}/dismiss    -- undo dismissal
GET    /jobs/dismissed           -- list dismissed jobs (management page)
```

**DB addition:**
```
dismissed_jobs
  user_id   uuid
  job_id    uuid
  dismissed_at  timestamp
  PRIMARY KEY (user_id, job_id)
```

**Notes:**
- Filter dismissed jobs at the query level (not post-fetch) to keep pagination correct
- Show a small "Dismissed Jobs" section in settings where users can restore jobs

---

### 5. Total UI Change

A complete visual redesign to make Jobee feel like a polished product rather than an internal tool.

**Key changes:**
- **Design system** — adopt a component library (Shadcn/ui + Tailwind) for consistency; replace all ad-hoc inline styles
- **Layout** — sidebar navigation instead of a flat top bar; collapsible on mobile
- **Job cards** — richer cards showing company logo, salary range, match score bar, posted date, and quick-action buttons (Save / Apply / Tailor / Dismiss) inline
- **Kanban board** — drag-and-drop columns with card previews; color-coded by stage; swimlane grouping by company
- **Dark mode** — system-preference aware via `prefers-color-scheme`, togglable in settings
- **Empty states & skeletons** — replace blank screens with illustrated empty states and skeleton loaders during fetches
- **Responsive** — full mobile layout for job browsing on the go
- **Micro-interactions** — subtle hover/focus animations, success toasts, progress indicators for long AI operations (scraping, tailoring, interview prep)

**Tech path:**
- Migrate to Shadcn/ui + Tailwind (already compatible with the Vite + React setup)
- Introduce a global `ThemeProvider` context
- Split large page components (`JobsPage`, `KanbanBoard`) into smaller, focused components under `src/components/`

---

## Priority Order

| # | Feature               | Effort | Impact |
|---|-----------------------|--------|--------|
| 1 | Dismiss Job Button    | Low    | High   |
| 2 | Better Job Queries    | Medium | High   |
| 3 | Tailor CV Button      | Medium | High   |
| 4 | Auto Mailing          | High   | High   |
| 5 | Total UI Change       | High   | High   |
