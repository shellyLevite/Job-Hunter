# Jobee — Next Steps & Roadmap

## What's Already Built

- Google OAuth 2.0 (httpOnly cookie-based JWTs)
- CV upload → Supabase Storage + parsed content
- LinkedIn scraper (guest API, pagination, concurrent description fetch)
- Indeed scraper
- On-demand search: user sets filters → scrapers run live → results cached 15 min
- AI ranking: CV skills extracted once (1 h cache) + batch job-skill extraction (10/call) → sorted by score
- "Strong Match" tag for score ≥ threshold
- CV-missing banner when user has no uploaded CV
- Job saved to DB only on user action (save / apply)
- Application tracking (Kanban board)
- React frontend (Jobs page with search + filters, Kanban, Login)

---

## Next Steps

---

### 1. Interview Prep

AI-generated practice questions tailored to a specific job + the user's own CV. High-value, sticky feature that no basic job board offers.

**Features:**
- Generate 10–15 questions from the job description + user CV
- Categorize: behavioral, technical, role-specific
- User types an answer → gets AI feedback + score
- Sessions are saved so the user can revisit them

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

### 3. Tests

No tests exist right now. This is a growing liability.

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

### 4. Gmail Integration — Auto-create Applications

Parse the user's Gmail inbox to automatically detect job-related emails and create application records.

**Flow:**
1. User grants Gmail read scope (Google OAuth is already set up)
2. A background job polls the inbox for emails matching patterns like:
   - "Thank you for applying to..."
   - "Your application at..."
   - "We received your application..."
3. Extract company name, role, and date via LLM or regex
4. Create or update a row in `applications` with status `applied`

**API endpoints to add:**
```
POST /auth/google/gmail-connect    -- request Gmail scope
GET  /integrations/gmail/sync      -- trigger manual sync
```

**Notes:**
- Store the Gmail `history_id` so incremental syncs are cheap
- Never store the full email body — extract fields and discard
- Make this opt-in

---

## Priority Order

| # | Feature                 | Effort | Impact |
|---|-------------------------|--------|--------|
| 1 | Interview prep          | Medium | High   |
| 2 | Tests                   | Medium | High   |
| 3 | Gmail integration       | High   | Medium |
