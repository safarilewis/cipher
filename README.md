# Cipher

Cipher is a resume-replacement developer profile platform. Instead of a static PDF, users build a live profile from:

- GitHub repository evidence
- LeetCode progress snapshots
- Structured profile sections (experience, education, projects, etc.)
- AI-generated analysis that must be reviewed before publishing

Profiles are private by default and are only publicly visible after explicit publication.

## What the app does

1. User signs in with GitHub in the frontend.
2. Frontend signs a short-lived backend JWT (`HS256`) and calls the API.
3. User connects GitHub and/or LeetCode sources.
4. User curates profile sections.
5. User generates analysis.
6. User reviews analysis.
7. User publishes and shares a public profile at `/u/[slug]`.

Free-tier source refreshes are rate-limited (`FREE_TIER_REFRESH_DAYS`, default `14`).

## Repository structure

- `backend/` — FastAPI API, SQLAlchemy models, ingestion services, analysis orchestration, tests
- `frontend/` — Next.js App Router app, Auth.js login, onboarding/dashboard/public profile UI
- `docker-compose.yml` — local Postgres + Redis + backend service

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic Settings, Uvicorn
- **Frontend:** Next.js 15, React 19, TypeScript, Auth.js (next-auth v5 beta)
- **Data:** PostgreSQL (default), SQLite fallback for quick local runs
- **AI providers:** OpenAI or Anthropic, with deterministic fallback if keys are missing

## Quick start (Docker + local frontend)

Start backend dependencies and API:

```bash
docker compose up --build
```

Services:

- Backend API: `http://localhost:8000`
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

Start frontend in a second terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Frontend: `http://localhost:3000`

## Manual local development

### Prerequisites

- Python 3.11+
- Node.js 20+
- Optional: Docker (for Postgres/Redis)

### 1) Backend

```bash
cd backend
cp .env.example .env
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Backend docs: `http://localhost:8000/docs`

### 2) Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `DATABASE_URL` | No | SQLAlchemy connection string. Defaults to SQLite if unset. |
| `REDIS_URL` | No | Redis URL. |
| `BACKEND_SESSION_SECRET` | Yes | Shared secret used to verify frontend-signed backend JWTs. |
| `AUTH_TRUST_DEV_HEADERS` | No | Trust `x-cipher-user-*` dev headers when `true` (local/manual testing only). |
| `ANALYSIS_PROVIDER` | No | `openai` or `anthropic` (default `openai`). |
| `OPENAI_API_KEY` | No | Enables OpenAI analysis. |
| `OPENAI_MODEL` | No | OpenAI model name (default `gpt-5.2`). |
| `ANTHROPIC_API_KEY` | No | Enables Anthropic analysis. |
| `ANTHROPIC_MODEL` | No | Anthropic model name (default `claude-sonnet-4-20250514`). |
| `FRONTEND_ORIGIN` | Yes | Allowed CORS origin for frontend. |
| `FREE_TIER_REFRESH_DAYS` | No | Source refresh cooldown window (default `14`). |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
| --- | --- | --- |
| `NEXTAUTH_URL` | Yes | Frontend URL (local: `http://localhost:3000`). |
| `AUTH_URL` | Yes | Auth.js URL (usually same as `NEXTAUTH_URL`). |
| `AUTH_SECRET` | Yes | Auth.js session secret. |
| `AUTH_GITHUB_ID` | Yes | GitHub OAuth app client ID. |
| `AUTH_GITHUB_SECRET` | Yes | GitHub OAuth app client secret. |
| `BACKEND_URL` | Yes | Backend URL (local: `http://localhost:8000`). |
| `BACKEND_SESSION_SECRET` | Yes | Must exactly match backend `BACKEND_SESSION_SECRET`. |

## Auth model

- Frontend authenticates users with GitHub via Auth.js.
- Frontend generates a backend bearer token (`sub`, `email`, `name`) signed with `BACKEND_SESSION_SECRET`.
- Backend validates that token and resolves/creates the corresponding user.

> `BACKEND_SESSION_SECRET` must match between frontend and backend in every environment.

## API overview

Base URL: `http://localhost:8000`

### Health

- `GET /health` — service health check

### Profile

- `GET /profile` — current user profile
- `PATCH /profile` — update profile fields (`name`, `headline`, `slug`, `career_stage_override`)
- `GET /profile/sections` — list profile sections
- `POST /profile/sections` — create section
- `PUT /profile/sections/{section_id}` — update section
- `DELETE /profile/sections/{section_id}` — delete section

Section kinds:

- `education`
- `experience`
- `certification`
- `bootcamp`
- `project`

### Sources

- `GET /sources` — list connected accounts and refresh metadata
- `POST /sources/github` — connect/sync GitHub source
- `GET /sources/github/repositories` — list imported repositories
- `POST /sources/github/repositories/selection` — choose up to 20 repositories for analysis
- `POST /sources/leetcode` — connect/sync LeetCode source
- `GET /sources/leetcode/latest` — latest LeetCode snapshot
- `DELETE /sources/{kind}` — disconnect `github` or `leetcode`

### Analysis & publishing

- `GET /analysis/latest` — latest generated analysis
- `POST /analysis` — create and run analysis
- `POST /analysis/{evaluation_id}/review` — mark a ready analysis as reviewed
- `POST /analysis/publish` — publish profile (requires reviewed analysis)
- `POST /analysis/unpublish` — unpublish profile

### Public

- `GET /public/profiles/{slug}` — public profile payload (only for published profiles)

## Tests and checks

Backend tests:

```bash
cd backend
pytest
```

Frontend build:

```bash
cd frontend
npm run build
```

Frontend tests:

```bash
cd frontend
npm run test
```

Frontend lint script exists (`npm run lint`), but Next.js may prompt for ESLint setup if a config is not yet initialized.

## Deployment

### Backend (Render)

`backend/render.yaml` defines a Render Blueprint with:

- Web service: `cipher-api`
- Managed Postgres: `cipher-postgres`
- Managed Redis: `cipher-redis`

Set at minimum:

- `FRONTEND_ORIGIN`
- `BACKEND_SESSION_SECRET`
- AI provider keys (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`) as needed

### Frontend (Vercel)

Deploy `frontend/` as a Next.js app (see `frontend/vercel.json`).

Set:

- `NEXTAUTH_URL`
- `AUTH_URL`
- `AUTH_SECRET`
- `AUTH_GITHUB_ID`
- `AUTH_GITHUB_SECRET`
- `BACKEND_URL`
- `BACKEND_SESSION_SECRET` (must match backend)

## License

AGPL
