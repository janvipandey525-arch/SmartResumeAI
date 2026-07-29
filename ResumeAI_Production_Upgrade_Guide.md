# ResumeAI — Production Upgrade Guide

**From a front-end demo to a real, deployed, AI-powered full-stack application.**

Prepared for: Aditya · TY B.Sc. Computer Science major project
Date: July 2026

---

## 1. Where you are today (honest starting point)

You've actually built more than most student projects: a clean, responsive multi-page UI (landing, auth, dashboard, resume builder, template picker, ATS analyzer, profile) in **vanilla HTML/CSS/JavaScript**, plus a genuinely clever **client-side ATS engine** (`window.ATS`) that scores resumes on keyword match, section coverage, action verbs, quantified impact, and readability, and reads PDF/DOCX/TXT in the browser via `pdf.js` and `mammoth.js`.

Two things stop it being "production":

1. **There is no backend.** All data — accounts, resumes, scores — lives in the browser's `localStorage`. Passwords are stored in **plaintext**, nothing is shared across devices, and clearing the browser wipes everything. This is the single most important thing to fix.
2. **There is no actual AI.** Despite the name "ResumeAI," the scoring is smart deterministic text-matching. You've decided to add real AI — good call, it's the biggest differentiator you can add.

This guide gives you an opinionated, production-grade-but-student-achievable stack, the exact prebuilt libraries to use, the folder structure, how to add real AI, and a phased roadmap so you can actually finish it. Everything here can be built and deployed for **₹0** using free tiers.

---

## 2. The recommended stack at a glance

Since you asked me to pick, here's the full stack I'd build this on and why each piece:

| Layer | Recommendation | Why this one |
|---|---|---|
| **Backend framework** | **Python + FastAPI** | Modern, fast, minimal boilerplate. Auto-generates interactive API docs (Swagger UI) — evaluators love this. Python is the native language of AI. |
| **Database** | **PostgreSQL** (hosted on **Neon**, free) | The industry-standard relational DB. Neon's free tier never expires and scales to zero when idle. |
| **ORM / DB toolkit** | **SQLAlchemy 2.0** + **Alembic** | SQLAlchemy is the standard Python ORM; Alembic handles schema migrations (versioned DB changes — a real production skill). |
| **Data validation** | **Pydantic v2** | Built into FastAPI. Validates every request/response with type hints. Prevents a huge class of bugs. |
| **Auth** | **JWT** (self-implemented) or **fastapi-users** (prebuilt) | JWT = stateless login tokens. Roll it yourself to learn, or use `fastapi-users` to get login/register/password-reset for free. |
| **Password hashing** | **bcrypt** (via `passlib`) | Never store plaintext. This alone fixes your biggest security hole. |
| **AI** | **Google Gemini API** (free tier: Gemini 2.5 Flash) | ~250 requests/day free, **no credit card**. Best free option for a student in 2026. |
| **Frontend (Phase 1)** | **Keep your vanilla HTML/CSS/JS** | Reuse all your work; just swap `localStorage` for `fetch()` calls to the API. Fastest path to a working full-stack app. |
| **Frontend (Phase 2)** | **React + Vite + Tailwind CSS + shadcn/ui** | The rebuild that impresses evaluators and teaches the most in-demand skill. |
| **Containerization** | **Docker** + **docker-compose** | Reproducible environment; run Postgres locally with one command. A must-show for "production." |
| **Hosting** | **Vercel** (frontend) + **Render** (backend) + **Neon** (DB) | All have real free tiers in 2026. |
| **Version control / CI** | **Git + GitHub** + **GitHub Actions** | Clean commit history and automated tests are things evaluators actively look for. |
| **Testing** | **pytest** + **httpx** | Automated tests = instant credibility for a "production" claim. |

> **Alternative if you'd rather stay in one language:** Node.js + **NestJS** (TypeScript) is the closest equivalent to FastAPI's structure, and you already know JavaScript. But for *this* project I recommend Python because the AI ecosystem is Python-first and FastAPI's auto-docs are a genuine evaluator-pleaser. NestJS is the fallback, not the default.

---

## 3. Architecture — how the pieces fit together

Right now everything happens in the browser. The production shape splits responsibilities into a **client** (what the user sees) and a **server** (the source of truth), talking over an HTTP **REST API**:

```
┌─────────────────────────┐        HTTPS / JSON        ┌──────────────────────────────┐
│      FRONTEND (client)  │  ───────────────────────▶  │        BACKEND (FastAPI)     │
│  Phase 1: your HTML/JS  │   POST /auth/login          │                              │
│  Phase 2: React + Vite  │   GET  /resumes             │  ┌────────────────────────┐  │
│                         │  ◀───────────────────────   │  │  Routers (endpoints)   │  │
│  - renders UI           │       JSON responses        │  ├────────────────────────┤  │
│  - holds JWT token      │                             │  │  Services (logic):     │  │
│  - calls the API        │                             │  │   • ATS engine (ported)│  │
└─────────────────────────┘                             │  │   • AI service (Gemini)│  │
                                                        │  │   • Auth service       │  │
                                                        │  ├────────────────────────┤  │
                                                        │  │  Models (SQLAlchemy)   │  │
                                                        │  └───────────┬────────────┘  │
                                                        └──────────────┼───────────────┘
                                                                       │
                                          ┌────────────────────────────┼───────────────────────┐
                                          ▼                            ▼                        ▼
                                  ┌───────────────┐          ┌──────────────────┐      ┌────────────────┐
                                  │  PostgreSQL   │          │  Google Gemini   │      │  (optional)    │
                                  │  (Neon)       │          │  API (AI)        │      │  file storage  │
                                  │  users,       │          │  resume feedback │      │  for PDFs      │
                                  │  resumes,     │          │  bullet rewrites │      └────────────────┘
                                  │  ats_reports  │          │  JD tailoring    │
                                  └───────────────┘          └──────────────────┘
```

**The golden rule that makes it "production":** the frontend never touches the database or the AI key directly. It only calls your API. Your API key and DB password live **on the server, in environment variables**, never in the browser. (Your current design exposes nothing sensitive, but the moment you add an AI key, it must live server-side — a key in frontend JS can be stolen and run up a bill.)

---

## 4. Backend deep-dive (FastAPI)

### 4.1 Why FastAPI

- **Auto-generated docs.** Every endpoint you write appears in an interactive Swagger UI at `/docs` — you can literally demo your whole API to your examiner in a browser without Postman. This is a huge, free credibility win.
- **Type-safe.** Pydantic validates inputs; you get clear errors instead of mystery crashes.
- **Async & fast.** Comparable to Node/Go for I/O-bound work (which is exactly what calling an AI API is).
- **Small.** A working API is ~100 lines. Django is heavier and more opinionated; save it for when you need its admin panel.

### 4.2 The libraries you install (your "prebuilt things" list)

```txt
# requirements.txt — the backend's prebuilt building blocks
fastapi                # web framework
uvicorn[standard]      # ASGI server that runs FastAPI
sqlalchemy             # ORM (database <-> Python objects)
alembic                # database migrations
psycopg[binary]        # PostgreSQL driver
pydantic               # data validation (comes with FastAPI)
pydantic-settings      # load config from environment variables
python-jose[cryptography]   # create/verify JWT tokens
passlib[bcrypt]        # hash passwords securely
python-multipart       # handle file uploads (resume PDFs)
google-genai           # official Google Gemini SDK
pypdf                  # read PDF text server-side
python-docx            # read DOCX text server-side
httpx                  # HTTP client (also used in tests)
pytest                 # testing framework
python-dotenv          # load .env in local dev
```

Optional but strong "prebuilt" upgrades:

- **`fastapi-users`** — drop-in user management (register, login, JWT, password reset, email verification). Saves you days if you don't want to hand-roll auth.
- **`slowapi`** — rate limiting, so nobody can spam your AI endpoint and burn your free quota.
- **`fastapi-mail`** — send verification / password-reset emails.

### 4.3 Recommended folder structure

A flat `main.py` works for a toy; evaluators want to see **separation of concerns**. Use this layout:

```
resumeai-backend/
├── app/
│   ├── main.py                 # creates the FastAPI app, mounts routers, CORS
│   ├── core/
│   │   ├── config.py           # settings from env vars (pydantic-settings)
│   │   └── security.py         # password hashing + JWT create/verify
│   ├── db/
│   │   ├── base.py             # SQLAlchemy engine + session
│   │   └── models.py           # User, Resume, AtsReport tables
│   ├── schemas/                # Pydantic request/response models
│   │   ├── user.py
│   │   ├── resume.py
│   │   └── ats.py
│   ├── routers/                # API endpoints, grouped by feature
│   │   ├── auth.py             # /auth/register, /auth/login
│   │   ├── resumes.py          # CRUD for resumes
│   │   └── ats.py              # /ats/analyze  (deterministic + AI)
│   ├── services/               # business logic (the interesting part)
│   │   ├── ats_engine.py       # your window.ATS logic, ported to Python
│   │   └── ai_service.py       # all Gemini calls live here
│   └── deps.py                 # shared dependencies (get_db, get_current_user)
├── alembic/                    # migration scripts (auto-generated)
├── tests/
│   ├── test_auth.py
│   └── test_ats.py
├── .env.example                # documents required env vars (NO real secrets)
├── .gitignore                  # must include .env
├── requirements.txt
├── Dockerfile
└── docker-compose.yml          # runs the API + a local Postgres together
```

### 4.4 Auth flow (fixing your biggest security hole)

Your current login compares a plaintext password from `localStorage`. The production flow:

1. **Register** → server hashes the password with bcrypt → stores only the hash.
2. **Login** → server verifies the password against the hash → returns a **JWT** (a signed token).
3. **Every protected request** → frontend sends `Authorization: Bearer <token>` → a FastAPI dependency (`get_current_user`) decodes the token and loads the user.

That's the whole model. It's ~60 lines with `python-jose` + `passlib`, or zero lines with `fastapi-users`. Rolling it yourself once is worth it for the learning and for something concrete to explain in your viva.

---

## 5. Database design

Move your three `localStorage` blobs (`resumeai_account`, `resumeai_resume`, `resumeai_last_score`) into three real tables:

```
users
─────
id            (PK)
full_name
email         (unique, indexed)
username      (unique)
password_hash          ← never the raw password
created_at

resumes
───────
id            (PK)
user_id       (FK → users.id)
title
personal_info (JSON: name, email, phone, address)
education     (JSON)
skills        (text / JSON array)
projects      (text)
experience    (text)
certifications(text)
template_id
created_at, updated_at

ats_reports
───────────
id            (PK)
user_id       (FK → users.id)
resume_id     (FK → resumes.id, nullable — could be an uploaded file)
job_description (text)
score         (int)
grade         (char)
breakdown     (JSON: the per-dimension scores)
matched_keywords (JSON)
missing_keywords (JSON)
ai_feedback   (text)          ← the new AI-generated advice
created_at
```

Now your dashboard's "Resumes Created" and "ATS Score" stats come from real `COUNT` and latest-row queries instead of a single number in the browser. Users can log in on any device and see their history — that's the tangible payoff of a backend, and a great thing to demo.

**Migrations:** use **Alembic**. Instead of editing the DB by hand, you change `models.py`, run `alembic revision --autogenerate`, and it writes a versioned migration. Being able to say "my schema changes are version-controlled" is a genuine production talking point.

---

## 6. Adding real AI (the part that earns the name)

Keep your existing deterministic ATS engine — **do not throw it away.** The winning design is a **hybrid**:

- **Deterministic engine (ported to `ats_engine.py`)** → gives a fast, free, explainable **numeric score** and keyword lists. It always works, costs nothing, and you can defend exactly how every point is calculated.
- **AI layer (`ai_service.py` → Gemini)** → gives **qualitative, human-like value** the rule engine can't: rewriting weak bullet points, tailoring a resume to a specific job description, generating a professional summary, and explaining *why* in plain English.

This hybrid is genuinely impressive because you can show the examiner both "here's the objective score, computed deterministically" **and** "here's the AI acting like a career coach" — and explain the trade-offs of each. That kind of design judgment is exactly what earns top marks.

### 6.1 AI features worth building (in priority order)

1. **AI resume feedback** — send resume text + the deterministic score, get back 3–5 specific, prioritized improvements in natural language.
2. **Bullet-point rewriter** — user pastes a weak bullet ("responsible for the website"), gets 2–3 strong, quantified rewrites ("Built and maintained a 5-page company website, cutting load time 35%").
3. **Job-description tailoring** — given a resume + a JD, suggest which skills to emphasize and what's missing.
4. **AI summary generator** — auto-write the professional summary from the rest of the resume.
5. **(Stretch) Cover-letter draft** — generate a first-draft cover letter for a given job.

### 6.2 Which AI provider — and why Gemini

For a student in 2026, **Google Gemini's free tier is the best starting point**: Gemini 2.5 Flash gives ~**250 requests/day** and 250K tokens/min with **no credit card required**. Gemini 2.5 Flash-Lite goes up to ~1,000 requests/day. That is plenty for building, demoing, and a class of real users.

Alternatives, in case you hit limits or want redundancy:

- **Groq** — free, no card, extremely fast inference (Llama / Gemma models), ~30 req/min. Great backup.
- **OpenRouter** — one API key, ~28 free models to experiment with.
- **OpenAI / Anthropic Claude** — higher quality on the hardest tasks, but both require a credit card and only give small trial credit. Fine to add later behind the same abstraction.

> **Two important notes for real users:** (1) On Gemini's *free* tier, Google may use prompts to improve its products — so tell users not to paste highly sensitive data, or move to a paid tier before real launch. (2) Always call the AI **from your backend**, never the browser, so your API key stays secret.

### 6.3 Design it so you can swap providers

Put every AI call behind one interface in `ai_service.py` (e.g. a `generate_feedback(resume_text, score)` function). Your routers call *that*, not Gemini directly. If Google changes limits (they cut free quotas in Dec 2025 with little warning), you swap the provider in **one file** instead of hunting through your codebase. This "provider abstraction" is itself a production pattern worth mentioning.

---

## 7. Frontend — my recommendation

You asked me to pick, so here's a two-phase plan that keeps you shipping instead of stuck rebuilding:

### Phase 1 — Keep your vanilla frontend, wire it to the API (do this first)

Your HTML/CSS/JS is clean and already works. The only change: everywhere `script.js` currently reads/writes `localStorage`, call your API instead.

- `Storage.setAccount(...)` on signup → `POST /auth/register`
- login form → `POST /auth/login`, save the returned JWT in memory (or a cookie)
- resume builder "Generate" → `POST /resumes`
- ATS "Analyze" → `POST /ats/analyze` (backend runs both the ported engine **and** Gemini)
- dashboard stats → `GET /resumes/stats`

This gets you a **real, complete full-stack app fast**, teaches you the client–server model, and doesn't waste the UI you already built. For a lot of examiners, this alone clears the "production backend" bar.

### Phase 2 — Rebuild the UI in React (for top marks / real polish)

Once the backend is solid, rebuild the frontend in **React + Vite + Tailwind CSS**, using **shadcn/ui** for ready-made accessible components, **React Router** for navigation, and **TanStack Query** for talking to your API (it handles loading/error/caching states for you). React is the single most in-demand frontend skill, and "I migrated a vanilla app to a component-based React SPA backed by a REST API" is a strong story to tell.

- Use **Vite + React** (a Single-Page App) rather than Next.js — it's simpler and everything you need is behind a login anyway, so you don't need Next's server-side rendering. Choose **Next.js** only if you want SEO on the public landing page or want to learn SSR specifically.

**If you're short on time, ship Phase 1 and treat Phase 2 as a clearly-labelled "v2."** A finished Phase-1 app beats a half-finished React rewrite every time.

---

## 8. Production concerns (the stuff that separates "project" from "product")

These are the things evaluators quietly look for, and each is small on its own:

- **Environment variables & secrets.** DB URL and `GEMINI_API_KEY` go in a `.env` file that is **git-ignored**; commit a `.env.example` with the *names* only. Never hardcode a key. Loaded via `pydantic-settings`.
- **CORS.** Add FastAPI's `CORSMiddleware` so your frontend domain is allowed to call the API.
- **Docker.** A `Dockerfile` for the API and a `docker-compose.yml` that also spins up Postgres means anyone can run your whole project with `docker compose up`. Demo this — it looks very professional.
- **Testing.** A handful of `pytest` tests (register → login → analyze) proves the app works and is a genuine differentiator in a student project.
- **CI with GitHub Actions.** A workflow that runs your tests on every push. A green checkmark on your repo is a great visual for evaluators.
- **Rate limiting & validation.** `slowapi` on the AI endpoint protects your free quota; Pydantic already validates every payload.
- **Error handling & logging.** Return proper HTTP status codes (401 unauthorized, 404 not found, 422 validation) instead of crashing. FastAPI does most of this for you.
- **A real README + architecture diagram + ER diagram.** Documentation is scored. Include setup steps, the diagram from Section 3, and a screenshot of the Swagger docs.

---

## 9. Deployment — all free in 2026

| Piece | Host | Free-tier reality (mid-2026) |
|---|---|---|
| **Database** | **Neon** | Free serverless Postgres, **no expiry**, scales to zero when idle. Best choice. |
| **Backend API** | **Render** | 750 hrs/month, 512 MB RAM. Note: free services **cold-start** (~30–50s) after inactivity — fine for a demo, mention it. |
| **Frontend** | **Vercel** or **Netlify** | Free, fast, perfect for static HTML or a React/Vite build. |

Alternatives: **Railway** (~$5 free credit/month, always-on, no cold starts — nicer demo but credit-limited); **Google Cloud Run** (very generous but needs a card); **Koyeb** (1 free always-on service). Avoid Render's *database* free tier for anything you want to keep — it **expires after 90 days**; that's why the DB goes on Neon, not Render.

> Demo tip: because Render's free API cold-starts, open the Swagger `/docs` URL a minute *before* your presentation so it's already warm.

---

## 10. Phased roadmap (a realistic build order)

**Milestone 0 — Setup (½ day)**
Create the GitHub repo, `resumeai-backend/` folder, virtualenv, install `requirements.txt`, "hello world" FastAPI running at `/docs`.

**Milestone 1 — Database + models (1–2 days)**
Spin up Neon, write `models.py` (users, resumes, ats_reports), wire SQLAlchemy, set up Alembic, run your first migration.

**Milestone 2 — Auth (1–2 days)**
`POST /auth/register` (bcrypt hash) and `POST /auth/login` (returns JWT). Add `get_current_user`. **This kills the plaintext-password problem.**

**Milestone 3 — Port the ATS engine (1 day)**
Translate your `window.ATS` JS logic into `services/ats_engine.py`. Add `pypdf` / `python-docx` to read uploaded files server-side. Expose `POST /ats/analyze`.

**Milestone 4 — Resume CRUD (1 day)**
Create / read / update / delete resumes tied to the logged-in user. Dashboard stats endpoint.

**Milestone 5 — Connect Phase-1 frontend (1–2 days)**
Replace every `localStorage` call in `script.js` with `fetch()` to the API. **Now it's a real full-stack app.**

**Milestone 6 — Add AI (2–3 days)**
`ai_service.py` + Gemini. Ship feedback + bullet rewriter first. Store `ai_feedback` in `ats_reports`.

**Milestone 7 — Dockerize + test + deploy (2–3 days)**
Dockerfile, docker-compose, a few pytest tests, GitHub Actions, then deploy (Neon + Render + Vercel). You now have a **live URL** to put on your resume.

**Milestone 8 (optional) — React rebuild (1–2 weeks)**
Migrate the UI to React + Vite + Tailwind + shadcn/ui for the polished "v2."

Milestones 0–7 are the whole production project. Milestone 8 is the cherry on top.

---

## 11. How to score high with evaluators

Concrete things to prepare, because a great project shown badly loses marks:

- **Live Swagger `/docs`** — walk through hitting endpoints live. Instant "this is real."
- **Architecture diagram + ER diagram** — put Section 3's diagram and your table schema in the report and on a slide.
- **The hybrid AI story** — explain *why* you kept a deterministic engine *and* added AI, and the trade-offs (cost, explainability, quality). Design reasoning scores higher than features.
- **Security narrative** — "I moved from plaintext passwords in localStorage to bcrypt hashes + JWT auth" is a perfect before/after.
- **Clean git history** — commit per milestone with clear messages, not one giant "final" commit.
- **A live deployed URL** — most student projects only run on the author's laptop. Yours runs on the internet.
- **README with setup steps + screenshots** — documentation is graded and easy marks.

---

## 12. Cost reality check

Everything above is **₹0** to build and demo:

- Neon Postgres — free, no expiry
- Render backend — free (with cold starts)
- Vercel frontend — free
- Gemini AI — free (~250 requests/day, no card)
- GitHub + GitHub Actions — free for public repos

You only spend money if this gets real traffic and you outgrow the free tiers — a good problem to have, and by then you'll know exactly what to upgrade.

---

## 13. One-paragraph summary

Build a **FastAPI** backend with **PostgreSQL (Neon)** via **SQLAlchemy + Alembic**, secure it with **bcrypt + JWT**, port your existing ATS engine to a Python **service** and layer **Google Gemini** (free tier) on top for real AI feedback, and keep your current HTML/JS frontend for v1 by swapping `localStorage` for API calls — then optionally rebuild it in **React + Vite + Tailwind**. Containerize with **Docker**, test with **pytest**, and deploy free on **Render + Vercel + Neon**. That is a genuine, deployable, production-shaped, AI-powered application — and every technical choice in it is one you can explain and defend.

---

## Sources (verified July 2026)

- [Gemini API Free Tier Complete Guide — AI Free API](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-complete-guide)
- [Free LLM APIs in 2026: 13 Providers Compared — Dmytro Klymentiev](https://klymentiev.com/blog/free-llm-api)
- [7 Free Backend Hosting Platforms for APIs, Tested (2026) — SnapDeploy](https://snapdeploy.dev/blog/free-backend-hosting-2026-apis-servers)
- [Best Managed PostgreSQL Hosting in 2026 — PandaStack](https://pandastack.io/blog/best-postgresql-hosting-2026)
- [LLM API Pricing 2026: OpenAI, Gemini, Claude — IntuitionLabs](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
