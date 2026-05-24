# cipher

cipher is a resume-replacement developer profile platform. Instead of a static PDF, users build a live profile from:

- GitHub repository evidence
- LeetCode progress snapshots
- Structured manual career sections (experience, education, projects, and more)
- AI-generated analysis that must be reviewed before publishing

Profiles are private by default and only become public after explicit user publication.
Free-tier profile source refreshes are limited to once every 14 days after the initial connection.

## Repository layout

- `backend/` - FastAPI API, SQLAlchemy models, source ingestion, and analysis orchestration
- `frontend/` - Next.js App Router app, GitHub auth flow, onboarding, dashboard, and public profile route
- `website-draft/` - archived/experimental marketing site draft
- `docker-compose.yml` - local Postgres, Redis, and backend services

## Tech stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Pydantic Settings, Uvicorn
- Frontend: Next.js 15, React 19, TypeScript, Auth.js (next-auth v5 beta)
- Data: PostgreSQL (default in `.env.example`), SQLite fallback for quick local runs
- AI: OpenAI Responses API (with deterministic fallback when no API key is set)

## How it works

1. User authenticates with GitHub in the frontend.
2. Frontend calls backend APIs using a signed HS256 bearer token.
3. User connects GitHub and LeetCode sources.
4. User adds profile sections (education, experience, project, etc.).
5. User triggers analysis generation.
6. User marks analysis as reviewed.
7. User publishes profile and gets a public URL at `/u/[slug]`.

Public profile API responses only include users that are both published and have a reviewed, ready analysis.

## Quick start (Docker-first)

This path gives you a running backend with Postgres + Redis quickly.

```bash
docker compose up --build
```

Services:

- Backend API: http://localhost:8000
- Postgres: localhost:5432
- Redis: localhost:6379

Then run the frontend separately:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Frontend runs at http://localhost:3000.

## Local development (manual)

### Prerequisites

- Python 3.11+
- Node.js 20+
# cipher
- Optional: Docker (for local Postgres/Redis)
cipher is a resume-replacement developer profile platform. Instead of a static PDF, users build a live profile from:
### 1) Start infra

```bash
| `DATABASE_URL` | No | SQLAlchemy URL. Defaults to SQLite if unset. Example: `postgresql+psycopg://cipher:cipher@localhost:5432/cipher` |
| `AUTH_TRUST_DEV_HEADERS` | No | If `true`, backend can trust dev headers (`x-cipher-user-*`) for local/manual testing. Set `false` outside local dev. |

- Python web service (`cipher-api`)
- Managed Postgres (`cipher-postgres`)
- Managed Redis (`cipher-redis`)
cd backend
cp .env.example .env
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

API docs become available at http://localhost:8000/docs.

### 3) Run frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `DATABASE_URL` | No | SQLAlchemy URL. Defaults to SQLite if unset. Example: `postgresql+psycopg://cipher:cipher@localhost:5432/cipher` |
| `REDIS_URL` | No | Redis connection string. |
| `BACKEND_SESSION_SECRET` | Yes | Shared secret used to verify frontend-signed backend JWTs. |
| `AUTH_TRUST_DEV_HEADERS` | No | If `true`, backend can trust dev headers (`x-cipher-user-*`) for local/manual testing. Set `false` outside local dev. |
| `OPENAI_API_KEY` | No | Enables OpenAI analysis generation. If missing, fallback deterministic analysis is used. |
| `OPENAI_MODEL` | No | OpenAI model name. Default: `gpt-5.2`. |
| `FRONTEND_ORIGIN` | Yes | Allowed CORS origin for frontend. Default: `http://localhost:3000`. |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
| --- | --- | --- |
| `NEXTAUTH_URL` | Yes | Frontend base URL (local: `http://localhost:3000`). |
| `AUTH_SECRET` | Yes | Auth.js secret for session signing. |
| `AUTH_GITHUB_ID` | Yes | GitHub OAuth app client ID. |
| `AUTH_GITHUB_SECRET` | Yes | GitHub OAuth app client secret. |
| `BACKEND_URL` | Yes | Backend base URL (local: `http://localhost:8000`). |
| `BACKEND_SESSION_SECRET` | Yes | Must exactly match backend `BACKEND_SESSION_SECRET`. |

## Auth model

- User signs in through GitHub using Auth.js.
- Frontend mints a short backend JWT using `BACKEND_SESSION_SECRET` and sends it as `Authorization: Bearer <token>`.
- Backend validates the token and resolves/creates a user record.

Important: the secret must match between frontend and backend in every environment.

## API overview

Base URL: `http://localhost:8000`

- `GET /health` - health check
- `GET /profile` - current user profile
- `PATCH /profile` - update name/headline/slug
- `GET /profile/sections` - list manual sections
- `POST /profile/sections` - create section
- `PUT /profile/sections/{section_id}` - update section
- `DELETE /profile/sections/{section_id}` - delete section
- `GET /sources` - list connected sources
- `POST /sources/github` - sync GitHub source
- `POST /sources/leetcode` - sync LeetCode source
- `DELETE /sources/{kind}` - disconnect a source
- `GET /sources/leetcode/latest` - latest LeetCode snapshot
- `GET /analysis/latest` - latest generated analysis
- `POST /analysis` - create + run analysis
- `POST /analysis/{evaluation_id}/review` - mark analysis reviewed
- `POST /analysis/publish` - publish profile
- `POST /analysis/unpublish` - unpublish profile
- `GET /public/profiles/{slug}` - public profile payload

## Testing and checks

Backend tests:

```bash
cd backend
pytest
```

Frontend production build check:

```bash
cd frontend
npm run build
```

Optional frontend lint/test commands:

```bash
cd frontend
npm run lint
npm run test
```

## Deployment

### Backend (Render)

The repo includes `backend/render.yaml` for Render Blueprint-based setup:

- Python web service (`cipher-api`)
- Managed Postgres (`cipher-postgres`)
- Managed Redis (`cipher-redis`)

Set these securely in Render:

- `FRONTEND_ORIGIN`
- `BACKEND_SESSION_SECRET`
- `OPENAI_API_KEY` (optional)

### Frontend (Vercel)

Deploy `frontend/` as a Next.js project using `vercel.json` defaults.

Set env vars in Vercel:

- `NEXTAUTH_URL`
- `AUTH_SECRET`
- `AUTH_GITHUB_ID`
- `AUTH_GITHUB_SECRET`
- `BACKEND_URL`
- `BACKEND_SESSION_SECRET` (must match Render backend)

## Notes and limitations

- There are no migration files yet; schema is initialized on backend startup.
- Redis is provisioned and configured, with room for queue/worker expansion.
- If OpenAI is unavailable, analysis still works via deterministic fallback output.

## License

No license file is currently included. Add a `LICENSE` file before open-source distribution.
