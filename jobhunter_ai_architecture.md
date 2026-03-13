# Jobee — Next Steps & Roadmap

## What's Already Built

- JWT authentication (register / login)
- CV upload & parsing
- LinkedIn & Indeed scrapers (basic)
- Job matching engine (skill similarity score)
- Application tracking (Kanban board)
- Scheduler (periodic scraping)
- React frontend (Jobs page, Kanban, Login)

---

## Next Steps

---

### 1. Google OAuth

Replace (or supplement) the current email/password login with Google Sign-In.

**Why:** Reduces friction at signup, no password management, and opens the door to Gmail integration later.

**How:**
- Add `google-auth-oauthlib` to the backend
- Create `/auth/google` and `/auth/google/callback` endpoints
- Store `google_id` + `google_refresh_token` on the user row
- Update the frontend login page to show a "Sign in with Google" button
- Keep existing JWT flow — just issue a JWT after the Google callback

**DB change:**
```
users:
  + google_id              string (nullable)
  + google_refresh_token   text (nullable, encrypted)
```

---

### 2. Better LinkedIn Scraping

The current LinkedIn scraper is fragile and misses a lot of listings.

**Problems to fix:**
- Selectors break on LinkedIn layout changes
- No pagination — only first page of results
- No retry/backoff on rate-limit responses
- Duplicate jobs sneaking in across runs

**Improvements:**
- Switch to a more resilient selector strategy (data attributes > CSS classes)
- Add pagination loop with configurable max pages
- Add exponential backoff + random delay between requests
- Fingerprint jobs by `(title + company + location)` hash before inserting
- Optionally integrate the LinkedIn unofficial API or a proxy service (e.g. Apify actor) as a fallback

---

### 3. Free CV Storage

Currently CVs are saved to the local `uploads/` folder, which won't survive a server restart/redeploy.

**Options (all free tier):**

| Service           | Free tier | Notes                            |
|-------------------|-----------|----------------------------------|
| Cloudinary        | 25 GB     | Easy SDK, PDF support            |
| Supabase Storage  | 1 GB      | Pairs well with Postgres         |
| Backblaze B2      | 10 GB     | S3-compatible                    |

**Recommended:** Supabase Storage — free, S3-compatible, and consistent with a future Supabase DB migration.

**Changes needed:**
- Add `supabase-py` (or `boto3` for B2)
- Replace local file save in `app/api/cv.py` with an upload call
- Store the returned public URL in `cvs.file_path` instead of a local path
- Add an env var `STORAGE_BUCKET` to `app/core/config.py`

---

### 4. Scheduled Scraping — No Duplicates

The scheduler runs but duplicate jobs still appear in the DB.

**Plan:**
- Add a `source_id` column to `jobs` — a hash of `(title + company + location + source)`
- Use `INSERT ... ON CONFLICT (source_id) DO NOTHING` in the upsert
- Log a count of new vs. skipped jobs per run
- Store `last_scraped_at` per source so the scheduler can skip sources that ran recently
- Add a dead-letter log for jobs that failed to parse (don't silently drop them)

**DB change:**
```
jobs:
  + source_id   string UNIQUE   -- hash for deduplication
  + scraped_at  timestamp
```

---

### 5. Gmail Integration — Auto-create Applications

Parse the user's Gmail inbox to automatically detect job-related emails and create application records.

**Flow:**
1. User grants Gmail read scope during (or after) Google OAuth
2. A background job polls the inbox periodically for emails matching patterns like:
   - "Thank you for applying to…"
   - "Your application at…"
   - "We received your application…"
3. Extract company name, role, and date from the email body (LLM or regex)
4. Create or update a row in `applications` with status `applied`

**API endpoints to add:**
```
POST /auth/google/gmail-connect    -- request Gmail scope
GET  /integrations/gmail/sync      -- trigger manual sync
```

**Notes:**
- Store the Gmail `history_id` so incremental syncs are cheap
- Never store the full email body — extract fields and discard
- Make this opt-in; not every user will want it

---

### 6. Interview Prep

Give users AI-generated practice questions tailored to a specific job they matched with.

**Features:**
- Generate 10–15 interview questions from the job description + user CV
- Categorize questions: behavioral, technical, role-specific
- Let the user type an answer and get AI feedback on it
- Save a "prep session" so the user can revisit it

**Endpoints:**
```
POST /interview/prep/{job_id}     -- generate questions for a job
POST /interview/answer            -- submit answer, get AI feedback
GET  /interview/sessions          -- list past prep sessions
```

**DB:**
```
interview_sessions
  id           uuid
  user_id      uuid
  job_id       uuid
  questions    jsonb   -- [{question, category, model_answer}]
  created_at   timestamp

interview_answers
  id             uuid
  session_id     uuid
  question_index int
  user_answer    text
  feedback       text
  score          float
  created_at     timestamp
```

---

### 7. Tests

No tests exist right now. This is risky as the codebase grows.

**Priority order:**
1. **Unit tests** for the matcher (`app/services/matcher.py`) — pure functions, easy to cover
2. **Unit tests** for scraper parsers — mock the HTML, assert extracted fields
3. **Integration tests** for API endpoints — use `httpx.AsyncClient` + a test DB
4. **E2E test** for the full scrape → match pipeline

**Tooling:**
- `pytest` + `pytest-asyncio` for async tests
- `httpx` for API integration tests
- `respx` for mocking external HTTP calls (LinkedIn, OpenAI)
- `factory-boy` for generating test DB fixtures

**Target:** at minimum 80% coverage on `app/services/` and `app/api/`

---

### 8. Per-User Jobs Mechanism

Right now jobs are global. There is no clear model for how each logged-in user sees their own relevant jobs.

**The problem:**
- Scraped jobs sit in one shared `jobs` table
- Matching runs but there is no clean way to surface "my jobs" vs. "all jobs"
- New users who join after a scrape run never get matches for jobs already in the DB

**Proposed model:**

```
jobs  (shared, global)
  └── job_matches  (per user)
        user_id, job_id, score, missing_skills, seen, saved, dismissed
```

**Rules:**
- When a new scrape run finishes → trigger matching for ALL active users
- When a new user signs up → run matching immediately against all existing jobs in the DB
- User can `dismiss` a job (hide it forever), `save` it, or `apply` (moves to Kanban)
- The frontend "Jobs" page only shows `job_matches` for the logged-in user, ordered by score

**Endpoint changes:**
```
GET  /jobs/feed           -- user's personalized ranked feed (replaces GET /jobs/matches)
POST /jobs/{id}/dismiss   -- hide a job for this user
POST /jobs/{id}/save      -- save for later
```

**DB change:**
```
job_matches:
  + seen        boolean  default false
  + saved       boolean  default false
  + dismissed   boolean  default false
```

---

## Rough Priority Order

| # | Feature                    | Effort | Impact |
|---|----------------------------|--------|--------|
| 1 | No-duplicate scraping      | Low    | High   |
| 2 | Per-user jobs mechanism    | Medium | High   |
| 3 | Free CV storage            | Low    | Medium |
| 4 | Better LinkedIn scraping   | Medium | High   |
| 5 | Tests                      | Medium | High   |
| 6 | Google OAuth               | Medium | Medium |
| 7 | Gmail integration          | High   | Medium |
| 8 | Interview prep             | High   | Medium |
