# Cipher

**A portfolio that's alive — one you can ask questions, and that answers with accurate evidence cited from a developers portfolio.**

A portfolio is usually a static page you read top to bottom and take on faith. Cipher makes it *alive*: a portfolio generated from a developer's actual work — the code in their repositories, their activity over time, and their structured profile sections — that you can **interrogate directly** instead of just reading. Ask it the questions people actually have ("has this developer built retrieval systems?", "is this person ready for a backend role?") and it answers with **accurate, source-linked evidence** rather than claims. Every answer traces to a specific source — a repo, a file, a commit — and the long-term goal is a portfolio that a person *or an autonomous agent* can query and trust without manual back and forth with a candidate.

Portfolios are private by default and only become publicly visible after explicit review and publication.

---

## Why this exists

A portfolio or resume is read-only and unverifiable: a list of assertions you take on faith, frozen the moment it's written. The current generation of AI hiring tools mostly makes that worse — they summarize claims faster rather than verifying them. Cipher's thesis is the opposite. The value isn't a prettier static page; it's a portfolio that can **answer questions on demand**, where every answer is grounded in evidence the developer actually produced and is only worth acting on because it traces back to that evidence. Making portfolios *alive and answerable from accurate evidence* drives both what the system does today and where it's going.

---

## Status at a glance

This README distinguishes what is **shipped and running in this repository** from the **product vision still being built**. Legend:

- ✅ **Shipped** — implemented and covered by the codebase/tests
- 🟡 **Partial** — a foundation exists, but the full capability is not there yet
- 🚧 **Planned** — not yet implemented; described here to set direction

| Capability | Status |
| --- | --- |
| GitHub sign-in + source ingestion (GitHub repos, LeetCode) | ✅ |
| Repository selection (up to 20) and structured profile sections | ✅ |
| Code retrieval (Voyage embeddings + pgvector) with file-context fallback | ✅ |
| Career-stage inference and cohort-relative scoring | ✅ |
| Schema-validated evaluation (skill model, recruiter aid, role fit, interview questions) | ✅ |
| Deterministic score aggregation (weighted, confidence-adjusted) | ✅ |
| Review-before-publish workflow + live public portfolio at `/u/[slug]` | ✅ |
| **Ask the portfolio questions** (`/ask`) — recruiter Q&A with cited evidence | ✅ answers draw on the evaluation + profile evidence (code-grounded answers are a separate roadmap item) |
| Semantic search across published portfolios | ✅ |
| Authorship verification (commit history / `git blame` attribution) | 🟡 commit counts filter by author; no line-level attribution yet |
| Anti-gaming / provenance (copied, tutorial, AI-generated code detection) | 🚧 |
| Score calibration (labeled reference set, measured variance) | 🚧 |
| Code-grounded Q&A with cited commits and diffs | 🚧 |
| Agent-queryable / MCP endpoint with provenance | 🚧 |
| Local-first analysis (VS Code, full local git history) | 🚧 |

---

## What it does today ✅

1. Sign in with GitHub.
2. Connect sources — GitHub repositories and/or a LeetCode snapshot.
3. Select up to 20 repositories for review and curate structured profile sections (experience, education, projects, etc.).
4. Generate a structured, evidence-grounded evaluation.
5. Review the analysis — nothing is published unattended.
6. Publish a **live portfolio at `/u/[slug]`** that visitors can read *and question*.

Free-tier source refreshes are rate-limited (`FREE_TIER_REFRESH_DAYS`, default `14`).

The portfolio is more than a page. Once published it is **answerable**: anyone can ask it direct questions (`POST /public/profiles/{slug}/ask`) — "is this person a fit for a backend role?", "what's the strongest evidence here?" — and get a structured answer with cited evidence and verification questions, not a canned bio. Published portfolios are also **semantically searchable** (`GET /public/search`), so they can be found by what the work actually shows. Today the answering reasons over the **generated evaluation and profile sections**; grounding answers directly in *authored code with cited commits and diffs* is the next step on the roadmap below.

---

## How the answers stay accurate ✅

A portfolio that answers questions is only useful if the answers are trustworthy. That accuracy comes from the analysis pipeline behind every portfolio — deliberately more than a single LLM call, and all of the following is implemented today:

- **Code is retrieved, not dumped.** Selected repositories are chunked and embedded (Voyage) into a pgvector index. At analysis time the system retrieves the most relevant code per review dimension — architecture, code quality, algorithms, and tests — so the model reasons over actual implementation rather than metadata alone. A file-context fallback is used when embeddings are unavailable.
- **Assessment is calibrated to career stage.** An inference step classifies the developer as student, new-grad, early, mid, or senior from profile and activity signals, and scoring is **cohort-relative** — a student is measured against student peers, not against senior engineers.
- **Output is structured and source-cited.** The model returns a schema-validated skill model (code quality, delivery, algorithms) plus a recruiter decision aid, role-fit mapping, and tailored interview questions. The rubric requires every claim to cite a repo, file, profile section, or stat, and to return `null` rather than a guess when evidence is absent.
- **Scores are aggregated deterministically.** The overall score is a fixed weighted combination of dimension scores (code quality 0.50, delivery 0.35, algorithms 0.15) computed in code, not by the model — with confidence downgraded when dimensions are missing.
- **Portfolios are discoverable by their evidence.** Published portfolios are embedded so they surface in semantic search based on what the work actually shows, not the keywords someone typed.

---

## Roadmap 🚧

These are the core of where Cipher is headed. They're listed in rough dependency order — authorship verification is the foundation the rest build on.

- **Authorship verification.** 🟡 The goal: attribute code to the developer via commit history and `git blame`, so the evaluation reflects what they actually wrote — not vendored dependencies, forked examples, or a teammate's commits. This is the foundation everything else depends on.
  - *Today:* commit counts can already be filtered to the connected user's GitHub login (`fetch_commit_count(..., author=...)`), but embeddings and code review still run over the full repository tree without line-level attribution.
  - *Needed:* per-file/per-line authorship attribution, exclusion of vendored/generated/teammate code from the evidence set, and threading attribution through into retrieval and scoring.
- **Anti-gaming / provenance.** Detect copied, tutorial-derived, and AI-generated code and discount it, so "real code evidence" means verified original work. *Nothing in the current pipeline attempts this; today's hygiene checks only flag committed env/secret files and generated-artifact paths.*
- **Score calibration.** A labeled reference set and measured run-to-run variance, so numeric scores carry honest confidence intervals. *Today scores are deterministic in aggregation but uncalibrated — confidence is heuristic, not measured.*
- **Answers grounded in authored code.** The portfolio can already answer questions; the next step is grounding those answers directly in the developer's *authored* code, with cited commits and diffs — so "has this developer implemented X?" is answered from real implementation, not just the evaluation summary. *Today the Q&A endpoint answers from the evaluation/profile payload, not from retrieved authored code.*
- **Agent-queryable portfolios.** Expose the same answerable, evidence-backed portfolio through a structured / MCP endpoint so hiring agents — not just people — can query a candidate programmatically and receive claims with provenance. *No MCP or agent endpoint exists yet; only the human-facing portfolio and search APIs are implemented.*
- **Local-first analysis.** A VS Code path that runs verification against full local git history — line-accurate, rate-limit-free, and usable for private codebases. *Not started; analysis currently runs server-side against the GitHub API.*

---

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic Settings, Uvicorn
- **Frontend:** Next.js 15, React 19, TypeScript, Auth.js (next-auth v5 beta)
- **Data:** PostgreSQL with pgvector (SQLite fallback for quick local runs), Redis
- **Embeddings:** Voyage
- **Analysis providers:** OpenAI or Anthropic, with a deterministic fallback when no key is set

## Repository structure

- `backend/` — FastAPI API, SQLAlchemy models, ingestion services, analysis orchestration, tests
- `frontend/` — Next.js App Router app, Auth.js login, onboarding / dashboard / public profile UI
- `docker-compose.yml` — local Postgres (pgvector) + Redis + backend service

---

## Quick start (Docker + local frontend)

Start backend dependencies and the API:

```bash
