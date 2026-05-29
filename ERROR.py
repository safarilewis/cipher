{
    "id": "d46a376d02c04f218aa40c8d2bcfe7a3",
    "status": "ready",
    "summary": "A first-year Minerva University student (CS & Finance, 2025–2029) with an unusually deep pre-university coding history stretching back to 2022 through the ALX Africa software engineering programme. The public portfolio spans 48 repositories across C, Python, JavaScript, and TypeScript, with 2,412 total commits. Recent work (early 2026) shows a clear shift toward production-shaped full-stack and AI-integrated applications — including a live deployed app (Stranded), a full-stack developer profile platform (Cipher), and an AI job assistant (adpt) — which is well above typical freshman-year output. No professional experience is listed; all evidence is project and coursework-based.",
    "skill_model": {
        "code_quality": "The strongest code quality signal comes from the cipher repository: the backend separates concerns into api/, services/, core/, models/, and schemas/ subdirectories under backend/app/, with a docker-compose.yml that correctly wires Postgres, Redis, and the backend service (cipher, docker-compose.yml). The pyproject.toml pins FastAPI >=0.115, SQLAlchemy 2.x, pydantic-settings, python-jose, and OpenAI/Anthropic clients, with a dev extras group for pytest (cipher, backend/pyproject.toml). The adpt frontend shows client-side caching with entity-cache and view-cache modules and graceful API fallback logic (adpt, app/(app)/applications/page.tsx). The adpt-api monorepo correctly separates API and worker processes with shared packages (adpt-api, structure). The stranded useAudio.js hook is a clean implementation of audio fade and ducking using React refs and interval management (stranded, src/hooks/useAudio.js). Weaknesses: commit messages are frequently uninformative ('added some stuff', 'final', 'changes'); a .env file was committed in applied-ai-system-project; and test coverage visible in the selected files is present but limited in scope.",
        "delivery": "The profile shows 2,412 commits across 48 repos spanning 4 years, with the most recent push 2026-05-28 confirming active engagement (cipher, pushed_at). At least four projects show evidence of deployment: Stranded is live at stranded-zeta.vercel.app (stranded, README), adpt uses Fly.io/Supabase (adpt-api, README), cipher uses Docker + Render (cipher, backend/render.yaml referenced in structure), and adpt is deployed as a Next.js app. The adpt-api commit history shows rapid iterative deployment work within a single day — healthz endpoint, Railway/Fly config fixes, and a working discovery agent (adpt-api, recent_commits). The burst-and-done pattern (many commits in one session, then silence) limits confidence that these are maintained systems, but for a student, completing and deploying four systems in one semester is strong evidence of delivery follow-through.",
        "algorithms": "DSA evidence is drawn entirely from the 2022–2023 ALX Africa coursework period. The safarilewis/sorting_algorithms repo (C, 2022) is an explicit sorting algorithms implementation, and safarilewis/alx-interview (Python, 41 commits, 2023) suggests structured algorithm practice. The alx-higher_level_programming repo (486 commits) covers Python fundamentals that include data structure usage. No repo-based DSA evidence appears in the 2025–2026 activity window; recent work is entirely product/application oriented. The cortex_ai repository contains a custom force-directed graph simulation in useForceGraph.ts implementing O(n²) repulsion, spring attraction for edges, and velocity damping (cortex_ai, resources/knowledge-graph/hooks/useForceGraph.ts), which is a concrete algorithmic implementation above typical coursework level. Source: repo_evidence."
    },
    "skill_model_v2": {
        "code_quality": {
            "score": 68,
            "confidence": "medium",
            "stage_context": "Scored against student/new-grad peers; production patterns observed are unusually mature for a current freshman.",
            "basis": [
                "cipher backend uses layered FastAPI structure with api/, services/, core/, models/, schemas/ separation (cipher, backend/app/)",
                "docker-compose.yml wires Postgres 16, Redis 7, and backend with proper depends_on and volume mounts (cipher, docker-compose.yml)",
                "pyproject.toml declares Python 3.11+ dependency pinning with dev extras for pytest and pytest-asyncio (cipher, backend/pyproject.toml)",
                "adpt frontend demonstrates caching patterns: getCachedApplication/setCachedApplication and view-cache staleness checks (adpt, app/(app)/applications/[id]/page.tsx)",
                "adpt-api uses monorepo layout with apps/api, apps/workers, and packages/config + packages/shared separation (adpt-api, package.json)",
                "stranded/src/hooks/useAudio.js implements fade-in/fade-out audio ducking with ref-based interval management and autoplay error handling (stranded, src/hooks/useAudio.js)",
                "applied-ai-system-project committed a .env file — a hygiene caution (applied-ai-system-project, .env)",
                "commit messages across cipher and applied-ai-system-project are largely non-descriptive ('added some stuff', 'changes', 'final')"
            ],
            "prose": "The strongest code quality signal comes from the cipher repository: the backend separates concerns into api/, services/, core/, models/, and schemas/ subdirectories under backend/app/, with a docker-compose.yml that correctly wires Postgres, Redis, and the backend service (cipher, docker-compose.yml). The pyproject.toml pins FastAPI >=0.115, SQLAlchemy 2.x, pydantic-settings, python-jose, and OpenAI/Anthropic clients, with a dev extras group for pytest (cipher, backend/pyproject.toml). The adpt frontend shows client-side caching with entity-cache and view-cache modules and graceful API fallback logic (adpt, app/(app)/applications/page.tsx). The adpt-api monorepo correctly separates API and worker processes with shared packages (adpt-api, structure). The stranded useAudio.js hook is a clean implementation of audio fade and ducking using React refs and interval management (stranded, src/hooks/useAudio.js). Weaknesses: commit messages are frequently uninformative ('added some stuff', 'final', 'changes'); a .env file was committed in applied-ai-system-project; and test coverage visible in the selected files is present but limited in scope."
        },
        "delivery": {
            "score": 72,
            "confidence": "medium",
            "stage_context": "Framed against student peers; the breadth of end-to-end systems shipped in a single semester is unusually high.",
            "basis": [
                "2,412 total commits across 48 repositories over ~4 years",
                "Active within the last 30 days (cipher pushed 2026-05-28)",
                "At least 4 distinct end-to-end applications: Stranded (live on Vercel), adpt (AI job assistant, deployed), adpt-api (deployed on Fly.io/Railway), cipher (Docker + Render)",
                "adpt-api commit log shows iterative deployment work: 'fly setup', 'some deployment fixes', 'added healthz endpoint' within a single day (adpt-api, recent_commits)",
                "applied-ai-system-project shows burst activity pattern with 8 commits in one session (applied-ai-system-project, recent_commits)",
                "Complexity trend marked as declining in temporal data — recent repos have lower commit counts than earlier ALX coursework marathon repos"
            ],
            "trend": "steady",
            "prose": "The profile shows 2,412 commits across 48 repos spanning 4 years, with the most recent push 2026-05-28 confirming active engagement (cipher, pushed_at). At least four projects show evidence of deployment: Stranded is live at stranded-zeta.vercel.app (stranded, README), adpt uses Fly.io/Supabase (adpt-api, README), cipher uses Docker + Render (cipher, backend/render.yaml referenced in structure), and adpt is deployed as a Next.js app. The adpt-api commit history shows rapid iterative deployment work within a single day — healthz endpoint, Railway/Fly config fixes, and a working discovery agent (adpt-api, recent_commits). The burst-and-done pattern (many commits in one session, then silence) limits confidence that these are maintained systems, but for a student, completing and deploying four systems in one semester is strong evidence of delivery follow-through."
        },
        "algorithms": {
            "score": 55,
            "confidence": "medium",
            "stage_context": "Framed against student peers; historical ALX DSA work plus one custom graph simulation algorithm observed.",
            "basis": [
                "safarilewis/sorting_algorithms (C, 2022-10): explicit sorting algorithms repo from ALX coursework",
                "safarilewis/alx-interview (Python, 2023-04): 41 commits to an interview prep repo, likely contains DSA exercises",
                "safarilewis/alx-higher_level_programming (Python, 486 commits): extensive Python fundamentals including data structures",
                "No dedicated DSA repos in 2025-2026 activity window; recent work is product-focused"
            ],
            "prose": "DSA evidence is drawn entirely from the 2022–2023 ALX Africa coursework period. The safarilewis/sorting_algorithms repo (C, 2022) is an explicit sorting algorithms implementation, and safarilewis/alx-interview (Python, 41 commits, 2023) suggests structured algorithm practice. The alx-higher_level_programming repo (486 commits) covers Python fundamentals that include data structure usage. No repo-based DSA evidence appears in the 2025–2026 activity window; recent work is entirely product/application oriented. The cortex_ai repository contains a custom force-directed graph simulation in useForceGraph.ts implementing O(n²) repulsion, spring attraction for edges, and velocity damping (cortex_ai, resources/knowledge-graph/hooks/useForceGraph.ts), which is a concrete algorithmic implementation above typical coursework level. Source: repo_evidence.",
            "source": "repo_evidence"
        },
        "overall": {
            "score": 67.5,
            "confidence": "high",
            "percentile_note": "Strong for a current freshman; comfortably above median for student-cohort profiles with this breadth of deployed work.",
            "scope_stage": "student",
            "scope_label": "Developing intern"
        }
    },
    "career_stage": {
        "stage": "student",
        "confidence": "high",
        "signals_used": [
            "education section lists Minerva University, start 2025-08, end 2029-05",
            "language timeline starts 2022 with ALX School coursework repos",
            "no work experience section present"
        ],
        "graduation_proximity": "current"
    },
    "signal_completeness": {
        "code_quality": {
            "available": true,
            "source": "code_context",
            "repos_reviewed": 6,
            "confidence": "high"
        },
        "delivery": {
            "available": true,
            "commit_coverage": "summary_only",
            "recency": "active"
        },
        "algorithms": {
            "available": true,
            "primary_source": "repo_evidence",
            "repo_dsa_found": true
        },
        "profile_depth": {
            "manual_sections": 1,
            "has_experience": false,
            "has_education": true,
            "has_projects": false
        }
    },
    "profile_signal_snapshot": {
        "version": 1,
        "profile": {
            "name": "Lewis Safari",
            "slug": "safarilewis",
            "headline": null
        },
        "career_stage": {
            "stage": "student",
            "confidence": "high",
            "signals_used": [
                "education section lists Minerva University, start 2025-08, end 2029-05",
                "language timeline starts 2022 with ALX School coursework repos",
                "no work experience section present"
            ],
            "graduation_proximity": "current"
        },
        "timeline": {
            "available": true,
            "language_timeline": [
                {
                    "date": "2022-07-11T00:00:00",
                    "language": "C",
                    "repo": "safarilewis/printf",
                    "commits": 29
                },
                {
                    "date": "2022-08-02T00:00:00",
                    "language": "C",
                    "repo": "safarilewis/simple_shell",
                    "commits": 16
                },
                {
                    "date": "2022-08-22T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/alx-higher_level_programming",
                    "commits": 486
                },
                {
                    "date": "2022-10-11T00:00:00",
                    "language": "C",
                    "repo": "safarilewis/sorting_algorithms",
                    "commits": 9
                },
                {
                    "date": "2022-10-25T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/AirBnB_clone",
                    "commits": 20
                },
                {
                    "date": "2022-11-08T00:00:00",
                    "language": "JavaScript",
                    "repo": "safarilewis/spotty",
                    "commits": 9
                },
                {
                    "date": "2022-12-04T00:00:00",
                    "language": "HTML",
                    "repo": "safarilewis/AirBnB_clone_v2",
                    "commits": 67
                },
                {
                    "date": "2023-01-19T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/AirBnB_clone_v3",
                    "commits": 28
                },
                {
                    "date": "2023-01-29T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/AirBnB_clone_v4",
                    "commits": 0
                },
                {
                    "date": "2023-02-27T00:00:00",
                    "language": "JavaScript",
                    "repo": "safarilewis/shortr",
                    "commits": 20
                },
                {
                    "date": "2023-03-10T00:00:00",
                    "language": "HTML",
                    "repo": "safarilewis/landing",
                    "commits": 2
                },
                {
                    "date": "2023-03-20T00:00:00",
                    "language": "JavaScript",
                    "repo": "safarilewis/alx-backend-javascript",
                    "commits": 122
                },
                {
                    "date": "2023-04-03T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/alx-backend-python",
                    "commits": 52
                },
                {
                    "date": "2023-04-06T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/alx-backend-storage",
                    "commits": 84
                },
                {
                    "date": "2023-04-12T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/alx-interview",
                    "commits": 41
                },
                {
                    "date": "2023-04-17T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/alx-backend",
                    "commits": 33
                },
                {
                    "date": "2023-04-21T00:00:00",
                    "language": "JavaScript",
                    "repo": "safarilewis/xers",
                    "commits": 29
                },
                {
                    "date": "2023-04-27T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/alx-backend-user-data",
                    "commits": 50
                },
                {
                    "date": "2023-06-27T00:00:00",
                    "language": "JavaScript",
                    "repo": "safarilewis/alx-files_manager",
                    "commits": 22
                },
                {
                    "date": "2026-02-18T00:00:00",
                    "language": "Jupyter Notebook",
                    "repo": "safarilewis/ai-agents-for-beginners",
                    "commits": 0
                },
                {
                    "date": "2026-02-22T00:00:00",
                    "language": "TypeScript",
                    "repo": "safarilewis/cortex_ai",
                    "commits": 0
                },
                {
                    "date": "2026-03-01T00:00:00",
                    "language": "TypeScript",
                    "repo": "safarilewis/adpt",
                    "commits": 20
                },
                {
                    "date": "2026-03-05T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/ai110-module1show-gameglitchinvestigator-starter",
                    "commits": 12
                },
                {
                    "date": "2026-03-17T00:00:00",
                    "language": "TypeScript",
                    "repo": "safarilewis/adpt-api",
                    "commits": 10
                },
                {
                    "date": "2026-03-23T00:00:00",
                    "language": "JavaScript",
                    "repo": "safarilewis/stranded",
                    "commits": 11
                },
                {
                    "date": "2026-03-30T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/ai110-module2show-pawpal-starter",
                    "commits": 8
                },
                {
                    "date": "2026-04-02T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/ai110-module3show-musicrecommendersimulation-starter",
                    "commits": 4
                },
                {
                    "date": "2026-04-27T00:00:00",
                    "language": "TypeScript",
                    "repo": "safarilewis/gstack",
                    "commits": 0
                },
                {
                    "date": "2026-04-27T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/applied-ai-system-project",
                    "commits": 12
                },
                {
                    "date": "2026-05-14T00:00:00",
                    "language": "Python",
                    "repo": "safarilewis/cipher",
                    "commits": 24
                }
            ],
            "abandoned_languages": [
                {
                    "language": "Shell",
                    "last_used": "2023-02-10T09:18:19",
                    "repo_count": 2
                },
                {
                    "language": "C",
                    "last_used": "2023-10-12T18:10:22",
                    "repo_count": 4
                },
                {
                    "language": "HTML",
                    "last_used": "2023-03-10T13:34:39",
                    "repo_count": 2
                }
            ],
            "adopted_languages": [
                {
                    "language": "Jupyter Notebook",
                    "first_used": "2026-02-18T00:00:00",
                    "repo_count": 1
                },
                {
                    "language": "TypeScript",
                    "first_used": "2026-02-22T00:00:00",
                    "repo_count": 4
                }
            ],
            "consistent_languages": [
                {
                    "language": "JavaScript",
                    "repo_count": 7
                },
                {
                    "language": "Python",
                    "repo_count": 14
                }
            ],
            "complexity_trend": "declining",
            "first_repo_date": "2022-04-24T00:00:00",
            "latest_activity_date": "2026-05-28T16:32:50",
            "active_years": 4.1
        },
        "languages": [
            "C",
            "HTML",
            "JavaScript",
            "Jupyter Notebook",
            "Python",
            "Shell",
            "TypeScript"
        ],
        "manual_sections": [
            {
                "kind": "education",
                "title": "Computer Science & Finance Freshman",
                "organization": "Minerva Univeristy",
                "start_date": "2025-08",
                "end_date": "2029-05"
            }
        ],
        "code_hygiene": {
            "available": true,
            "positive_signals": [
                "test files present",
                "containerization present",
                "configuration files present"
            ],
            "caution_signals": {
                "committed_env_or_secret_paths": [
                    ".env",
                    ".env.dist",
                    ".env.example",
                    "backend/.env.example",
                    "frontend/.env.example"
                ],
                "generated_artifact_paths": [
                    "dist/favicon.svg",
                    "dist/icons.svg",
                    "dist/index.html",
                    "src/__pycache__/__init__.cpython-313.pyc",
                    "src/__pycache__/__init__.cpython-314.pyc",
                    "src/__pycache__/main.cpython-313.pyc",
                    "src/__pycache__/main.cpython-314.pyc",
                    "src/__pycache__/rag.cpython-313.pyc",
                    "src/__pycache__/recommender.cpython-313.pyc",
                    "src/__pycache__/recommender.cpython-314.pyc",
                    "tests/__pycache__/conftest.cpython-313-pytest-8.4.2.pyc",
                    "tests/__pycache__/test_rag.cpython-313-pytest-8.4.2.pyc",
                    "tests/__pycache__/test_recommender.cpython-313-pytest-8.4.2.pyc"
                ]
            },
            "files_observed": 382
        },
        "architecture": [
            {
                "repo": "safarilewis/cortex_ai",
                "patterns": [
                    "has_docs"
                ],
                "framework_hints": [],
                "file_count": 100,
                "max_depth": 5
            },
            {
                "repo": "safarilewis/cipher",
                "patterns": [
                    "frontend_backend_split",
                    "api_first",
                    "has_tests",
                    "has_docker"
                ],
                "framework_hints": [
                    "python_backend",
                    "nextjs",
                    "node",
                    "python"
                ],
                "file_count": 72,
                "max_depth": 5
            },
            {
                "repo": "safarilewis/adpt-api",
                "patterns": [
                    "monorepo",
                    "api_first",
                    "has_tests",
                    "has_docker"
                ],
                "framework_hints": [
                    "node"
                ],
                "file_count": 34,
                "max_depth": 4
            },
            {
                "repo": "safarilewis/adpt",
                "patterns": [
                    "has_tests",
                    "has_docs"
                ],
                "framework_hints": [
                    "nextjs",
                    "node"
                ],
                "file_count": 100,
                "max_depth": 5
            },
            {
                "repo": "safarilewis/applied-ai-system-project",
                "patterns": [
                    "has_tests",
                    "has_docs"
                ],
                "framework_hints": [
                    "python_backend",
                    "python"
                ],
                "file_count": 31,
                "max_depth": 2
            },
            {
                "repo": "safarilewis/stranded",
                "patterns": [
                    "api_first"
                ],
                "framework_hints": [
                    "node"
                ],
                "file_count": 48,
                "max_depth": 2
            }
        ],
        "delivery": {
            "total_commits": 2412,
            "repository_count": 48,
            "selected_repository_count": 6,
            "recency": "active",
            "recent_activity": [
                {
                    "repo": "safarilewis/cortex_ai",
                    "pushed_at": "2026-02-22T01:23:03",
                    "recent_commits": []
                },
                {
                    "repo": "safarilewis/cipher",
                    "pushed_at": "2026-05-28T16:32:50",
                    "recent_commits": [
                        {
                            "sha": "093b02b2f41d",
                            "message": "Edited  README",
                            "authored_at": "2026-05-28T16:32:49Z",
                            "url": "https://github.com/safarilewis/cipher/commit/093b02b2f41d6a687498e87d02b2b962e8498472"
                        },
                        {
                            "sha": "d7990b320b3e",
                            "message": "Fix capitalization of 'Cipher' in README",
                            "authored_at": "2026-05-28T16:25:02Z",
                            "url": "https://github.com/safarilewis/cipher/commit/d7990b320b3e3108a40dcca185261d083b5496f0"
                        },
                        {
                            "sha": "6e365643648b",
                            "message": "Merge pull request #1 from safarilewis/copilot/rewrite-readme-documentation",
                            "authored_at": "2026-05-28T16:24:13Z",
                            "url": "https://github.com/safarilewis/cipher/commit/6e365643648bd77d4151b6e8f9e938970ca4f26b"
                        },
                        {
                            "sha": "d257df6ea2f4",
                            "message": "final changes",
                            "authored_at": "2026-05-27T13:21:13Z",
                            "url": "https://github.com/safarilewis/cipher/commit/d257df6ea2f4987a5eedd7b125f14f1b8f4a80eb"
                        },
                        {
                            "sha": "7664315fea33",
                            "message": "Delete personal directory",
                            "authored_at": "2026-05-26T20:25:19Z",
                            "url": "https://github.com/safarilewis/cipher/commit/7664315fea33e349f71eecd3417bebc095f600ae"
                        }
                    ]
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "pushed_at": "2026-03-20T22:48:54",
                    "recent_commits": [
                        {
                            "sha": "781a4f53e3c7",
                            "message": "contact form",
                            "authored_at": "2026-03-20T22:48:51Z",
                            "url": "https://github.com/safarilewis/adpt-api/commit/781a4f53e3c73f61ec0f58f2c484417674158d1f"
                        },
                        {
                            "sha": "e922713ae1bd",
                            "message": "contact form",
                            "authored_at": "2026-03-20T03:31:32Z",
                            "url": "https://github.com/safarilewis/adpt-api/commit/e922713ae1bd7e69219f136989f3c1dd92685dac"
                        },
                        {
                            "sha": "828cce13ea22",
                            "message": "fixing railway",
                            "authored_at": "2026-03-20T02:19:50Z",
                            "url": "https://github.com/safarilewis/adpt-api/commit/828cce13ea227b4d66f73456c460ad4a07031948"
                        },
                        {
                            "sha": "38b4982e2fc7",
                            "message": "added healthz endpoint",
                            "authored_at": "2026-03-20T01:27:57Z",
                            "url": "https://github.com/safarilewis/adpt-api/commit/38b4982e2fc7d5396b02528a33ecf591208c5d47"
                        },
                        {
                            "sha": "586548af51fc",
                            "message": "some deployment fixes",
                            "authored_at": "2026-03-20T01:05:56Z",
                            "url": "https://github.com/safarilewis/adpt-api/commit/586548af51fcabfd5415ddb188e68d0017dde4ce"
                        }
                    ]
                },
                {
                    "repo": "safarilewis/adpt",
                    "pushed_at": "2026-05-25T02:34:44",
                    "recent_commits": [
                        {
                            "sha": "aacaaa77e3ca",
                            "message": "Merge pull request #1 from safarilewis/copilot/rewrite-readme-documentation",
                            "authored_at": "2026-05-25T02:34:44Z",
                            "url": "https://github.com/safarilewis/adpt/commit/aacaaa77e3cab01a8bdf07a3153a35a95a53371b"
                        },
                        {
                            "sha": "7ece4a33d0ec",
                            "message": "updated stats on the dash",
                            "authored_at": "2026-03-08T17:12:46Z",
                            "url": "https://github.com/safarilewis/adpt/commit/7ece4a33d0ec0fbcae864980267c2adb91d7f306"
                        },
                        {
                            "sha": "bef7010464e4",
                            "message": "added pulsing live button",
                            "authored_at": "2026-03-04T08:08:21Z",
                            "url": "https://github.com/safarilewis/adpt/commit/bef7010464e42236e81cab4735fc3a4feb1c4cce"
                        },
                        {
                            "sha": "e74c29d9fdf9",
                            "message": "fixed no redirect",
                            "authored_at": "2026-03-04T08:00:32Z",
                            "url": "https://github.com/safarilewis/adpt/commit/e74c29d9fdf90c701ed2b9dc2662bba5c8c79181"
                        },
                        {
                            "sha": "3b696dce9d28",
                            "message": "fixed github issue",
                            "authored_at": "2026-03-04T07:28:46Z",
                            "url": "https://github.com/safarilewis/adpt/commit/3b696dce9d2800dc3e9aed3b4c5775e577938ad7"
                        }
                    ]
                },
                {
                    "repo": "safarilewis/applied-ai-system-project",
                    "pushed_at": "2026-04-27T07:03:34",
                    "recent_commits": [
                        {
                            "sha": "acacd84fb100",
                            "message": "added some stuff",
                            "authored_at": "2026-04-27T07:03:31Z",
                            "url": "https://github.com/safarilewis/applied-ai-system-project/commit/acacd84fb10041036a5e50165f801ed5412d3b95"
                        },
                        {
                            "sha": "a25d3fc510fe",
                            "message": "added some stuff",
                            "authored_at": "2026-04-27T06:59:44Z",
                            "url": "https://github.com/safarilewis/applied-ai-system-project/commit/a25d3fc510fed7f4722c0519db3405bf669b111d"
                        },
                        {
                            "sha": "34aff980b8f0",
                            "message": "added some stuff",
                            "authored_at": "2026-04-27T06:59:12Z",
                            "url": "https://github.com/safarilewis/applied-ai-system-project/commit/34aff980b8f0c35e641c482bbfef8a09148669ac"
                        },
                        {
                            "sha": "10a07c61924b",
                            "message": "added some stuff",
                            "authored_at": "2026-04-27T06:58:29Z",
                            "url": "https://github.com/safarilewis/applied-ai-system-project/commit/10a07c61924b0fdc1d808dfcfd6681795b72ff6a"
                        },
                        {
                            "sha": "c1c3fbeaaa38",
                            "message": "docs: complete model_card reflection for Project 4",
                            "authored_at": "2026-04-27T06:58:13Z",
                            "url": "https://github.com/safarilewis/applied-ai-system-project/commit/c1c3fbeaaa38bc58cb5ec2820cf1a2bc6732b56d"
                        }
                    ]
                },
                {
                    "repo": "safarilewis/stranded",
                    "pushed_at": "2026-05-25T02:18:18",
                    "recent_commits": [
                        {
                            "sha": "145ef56b20dc",
                            "message": "Merge pull request #1 from safarilewis/copilot/update-readme-architecture-features",
                            "authored_at": "2026-05-25T02:18:18Z",
                            "url": "https://github.com/safarilewis/stranded/commit/145ef56b20dc7543645b5bc84c949a1f9d1e294f"
                        },
                        {
                            "sha": "3ac05348e25b",
                            "message": "updated website",
                            "authored_at": "2026-04-20T17:39:22Z",
                            "url": "https://github.com/safarilewis/stranded/commit/3ac05348e25b09953c982a991a9393245233fc62"
                        },
                        {
                            "sha": "09b0d24d2bb1",
                            "message": "UI refinements",
                            "authored_at": "2026-04-20T10:58:20Z",
                            "url": "https://github.com/safarilewis/stranded/commit/09b0d24d2bb1ba3cebfeacdd08be72c14bc1667b"
                        },
                        {
                            "sha": "8a41b63dc4d1",
                            "message": "last working",
                            "authored_at": "2026-04-20T09:26:32Z",
                            "url": "https://github.com/safarilewis/stranded/commit/8a41b63dc4d1a845f343bea0d20892c7e83d092a"
                        },
                        {
                            "sha": "e3eccfac29b7",
                            "message": "updated some stuff",
                            "authored_at": "2026-04-20T08:11:35Z",
                            "url": "https://github.com/safarilewis/stranded/commit/e3eccfac29b7f796bf39af98a2ec74857f5dd53e"
                        }
                    ]
                }
            ]
        },
        "algorithms": {
            "source": "repo_evidence",
            "leetcode": null,
            "prose": "DSA evidence is drawn entirely from the 2022–2023 ALX Africa coursework period. The safarilewis/sorting_algorithms repo (C, 2022) is an explicit sorting algorithms implementation, and safarilewis/alx-interview (Python, 41 commits, 2023) suggests structured algorithm practice. The alx-higher_level_programming repo (486 commits) covers Python fundamentals that include data structure usage. No repo-based DSA evidence appears in the 2025–2026 activity window; recent work is entirely product/application oriented. The cortex_ai repository contains a custom force-directed graph simulation in useForceGraph.ts implementing O(n²) repulsion, spring attraction for edges, and velocity damping (cortex_ai, resources/knowledge-graph/hooks/useForceGraph.ts), which is a concrete algorithmic implementation above typical coursework level. Source: repo_evidence."
        },
        "skill_model": {
            "code_quality": {
                "score": 68,
                "confidence": "medium",
                "stage_context": "Scored against student/new-grad peers; production patterns observed are unusually mature for a current freshman.",
                "basis": [
                    "cipher backend uses layered FastAPI structure with api/, services/, core/, models/, schemas/ separation (cipher, backend/app/)",
                    "docker-compose.yml wires Postgres 16, Redis 7, and backend with proper depends_on and volume mounts (cipher, docker-compose.yml)",
                    "pyproject.toml declares Python 3.11+ dependency pinning with dev extras for pytest and pytest-asyncio (cipher, backend/pyproject.toml)",
                    "adpt frontend demonstrates caching patterns: getCachedApplication/setCachedApplication and view-cache staleness checks (adpt, app/(app)/applications/[id]/page.tsx)",
                    "adpt-api uses monorepo layout with apps/api, apps/workers, and packages/config + packages/shared separation (adpt-api, package.json)",
                    "stranded/src/hooks/useAudio.js implements fade-in/fade-out audio ducking with ref-based interval management and autoplay error handling (stranded, src/hooks/useAudio.js)",
                    "applied-ai-system-project committed a .env file — a hygiene caution (applied-ai-system-project, .env)",
                    "commit messages across cipher and applied-ai-system-project are largely non-descriptive ('added some stuff', 'changes', 'final')"
                ],
                "prose": "The strongest code quality signal comes from the cipher repository: the backend separates concerns into api/, services/, core/, models/, and schemas/ subdirectories under backend/app/, with a docker-compose.yml that correctly wires Postgres, Redis, and the backend service (cipher, docker-compose.yml). The pyproject.toml pins FastAPI >=0.115, SQLAlchemy 2.x, pydantic-settings, python-jose, and OpenAI/Anthropic clients, with a dev extras group for pytest (cipher, backend/pyproject.toml). The adpt frontend shows client-side caching with entity-cache and view-cache modules and graceful API fallback logic (adpt, app/(app)/applications/page.tsx). The adpt-api monorepo correctly separates API and worker processes with shared packages (adpt-api, structure). The stranded useAudio.js hook is a clean implementation of audio fade and ducking using React refs and interval management (stranded, src/hooks/useAudio.js). Weaknesses: commit messages are frequently uninformative ('added some stuff', 'final', 'changes'); a .env file was committed in applied-ai-system-project; and test coverage visible in the selected files is present but limited in scope."
            },
            "delivery": {
                "score": 72,
                "confidence": "medium",
                "stage_context": "Framed against student peers; the breadth of end-to-end systems shipped in a single semester is unusually high.",
                "basis": [
                    "2,412 total commits across 48 repositories over ~4 years",
                    "Active within the last 30 days (cipher pushed 2026-05-28)",
                    "At least 4 distinct end-to-end applications: Stranded (live on Vercel), adpt (AI job assistant, deployed), adpt-api (deployed on Fly.io/Railway), cipher (Docker + Render)",
                    "adpt-api commit log shows iterative deployment work: 'fly setup', 'some deployment fixes', 'added healthz endpoint' within a single day (adpt-api, recent_commits)",
                    "applied-ai-system-project shows burst activity pattern with 8 commits in one session (applied-ai-system-project, recent_commits)",
                    "Complexity trend marked as declining in temporal data — recent repos have lower commit counts than earlier ALX coursework marathon repos"
                ],
                "trend": "steady",
                "prose": "The profile shows 2,412 commits across 48 repos spanning 4 years, with the most recent push 2026-05-28 confirming active engagement (cipher, pushed_at). At least four projects show evidence of deployment: Stranded is live at stranded-zeta.vercel.app (stranded, README), adpt uses Fly.io/Supabase (adpt-api, README), cipher uses Docker + Render (cipher, backend/render.yaml referenced in structure), and adpt is deployed as a Next.js app. The adpt-api commit history shows rapid iterative deployment work within a single day — healthz endpoint, Railway/Fly config fixes, and a working discovery agent (adpt-api, recent_commits). The burst-and-done pattern (many commits in one session, then silence) limits confidence that these are maintained systems, but for a student, completing and deploying four systems in one semester is strong evidence of delivery follow-through."
            },
            "algorithms": {
                "score": 55,
                "confidence": "medium",
                "stage_context": "Framed against student peers; historical ALX DSA work plus one custom graph simulation algorithm observed.",
                "basis": [
                    "safarilewis/sorting_algorithms (C, 2022-10): explicit sorting algorithms repo from ALX coursework",
                    "safarilewis/alx-interview (Python, 2023-04): 41 commits to an interview prep repo, likely contains DSA exercises",
                    "safarilewis/alx-higher_level_programming (Python, 486 commits): extensive Python fundamentals including data structures",
                    "No dedicated DSA repos in 2025-2026 activity window; recent work is product-focused"
                ],
                "prose": "DSA evidence is drawn entirely from the 2022–2023 ALX Africa coursework period. The safarilewis/sorting_algorithms repo (C, 2022) is an explicit sorting algorithms implementation, and safarilewis/alx-interview (Python, 41 commits, 2023) suggests structured algorithm practice. The alx-higher_level_programming repo (486 commits) covers Python fundamentals that include data structure usage. No repo-based DSA evidence appears in the 2025–2026 activity window; recent work is entirely product/application oriented. The cortex_ai repository contains a custom force-directed graph simulation in useForceGraph.ts implementing O(n²) repulsion, spring attraction for edges, and velocity damping (cortex_ai, resources/knowledge-graph/hooks/useForceGraph.ts), which is a concrete algorithmic implementation above typical coursework level. Source: repo_evidence.",
                "source": "repo_evidence"
            },
            "overall": {
                "score": 67.5,
                "confidence": "high",
                "percentile_note": "Strong for a current freshman; comfortably above median for student-cohort profiles with this breadth of deployed work.",
                "scope_stage": "student",
                "scope_label": "Developing intern"
            }
        },
        "signal_completeness": {
            "code_quality": {
                "available": true,
                "source": "code_context",
                "repos_reviewed": 6,
                "confidence": "high"
            },
            "delivery": {
                "available": true,
                "commit_coverage": "summary_only",
                "recency": "active"
            },
            "algorithms": {
                "available": true,
                "primary_source": "repo_evidence",
                "repo_dsa_found": true
            },
            "profile_depth": {
                "manual_sections": 1,
                "has_experience": false,
                "has_education": true,
                "has_projects": false
            }
        },
        "evidence": {
            "cited_files": [],
            "observed_key_files": [
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "README.md"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "package.json"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "tsconfig.json"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "resources/knowledge-graph/components/AddNoteForm.tsx"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "resources/knowledge-graph/components/GraphView.tsx"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "resources/knowledge-graph/components/NoteDetail.tsx"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "resources/knowledge-graph/components/NotesList.tsx"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "resources/knowledge-graph/hooks/useForceGraph.ts"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "index.ts"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "resources/knowledge-graph/types.ts"
                },
                {
                    "repo": "safarilewis/cortex_ai",
                    "path": "resources/knowledge-graph/widget.tsx"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "README.md"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/pyproject.toml"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "docker-compose.yml"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "frontend/next.config.ts"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "frontend/package.json"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "frontend/tsconfig.json"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/__init__.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/api/__init__.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/api/analysis.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/api/profile.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/api/public.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/api/sources.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/auth.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/core/__init__.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/core/config.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/db.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/jobs.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/main.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/models.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/schemas.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/services/__init__.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/services/analysis.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/services/github.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/services/leetcode.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/services/refresh_policy.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/app/services/scoring.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/tests/test_analysis_v2.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/tests/test_github.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "backend/tests/test_scoring.py"
                },
                {
                    "repo": "safarilewis/cipher",
                    "path": "frontend/app/actions.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "README.md"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/package.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/tsconfig.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/workers/package.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/workers/tsconfig.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "package.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/config/package.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/config/tsconfig.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/shared/package.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/shared/tsconfig.json"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/lib/auth.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/lib/early-access.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/lib/load-env.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/lib/queues.test.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/lib/queues.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/lib/store.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/routes/protected.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/api/src/server.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/workers/src/lib/pipeline.test.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/workers/src/lib/pipeline.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/shared/src/index.test.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/workers/src/index.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/workers/src/load-env.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "apps/workers/src/workers/queue-names.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/config/src/index.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/config/src/supabase.ts"
                },
                {
                    "repo": "safarilewis/adpt-api",
                    "path": "packages/shared/src/index.ts"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "README.md"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "package.json"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "tsconfig.json"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/applications/[id]/page.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/applications/page.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/connections/github/callback/page.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/dashboard/page.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/jobs/[id]/page.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/jobs/page.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/layout.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/loading.tsx"
                },
                {
                    "repo": "safarilewis/adpt",
                    "path": "app/(app)/onboarding/page.tsx"
                }
            ],
            "highlights": []
        },
        "rag": {
            "chunk_count": 0,
            "file_count": 0,
            "files_by_dimension": {},
            "embedding_precompute": {
                "attempted": [],
                "indexed": [],
                "missing": [
                    {
                        "repo": "safarilewis/cortex_ai",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/cipher",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/adpt-api",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/adpt",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/applied-ai-system-project",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/stranded",
                        "reason": "not_indexed"
                    }
                ],
                "skipped": [
                    {
                        "repo": "safarilewis/cortex_ai",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/cipher",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/adpt-api",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/adpt",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/applied-ai-system-project",
                        "reason": "not_indexed"
                    },
                    {
                        "repo": "safarilewis/stranded",
                        "reason": "not_indexed"
                    }
                ],
                "chunks_pending": 0,
                "chunks_stored": 0,
                "errors": [],
                "mode": "read_existing_only"
            }
        },
        "recruiter": {
            "hiring_recommendation": null,
            "role_fit": [],
            "manual_section_evaluations": [],
            "interview_questions": [],
            "recruiter_risks": []
        },
        "summary_for_search": "Lewis Safari\nA first-year Minerva University student (CS & Finance, 2025–2029) with an unusually deep pre-university coding history stretching back to 2022 through the ALX Africa software engineering programme. The public portfolio spans 48 repositories across C, Python, JavaScript, and TypeScript, with 2,412 total commits. Recent work (early 2026) shows a clear shift toward production-shaped full-stack and AI-integrated applications — including a live deployed app (Stranded), a full-stack developer profile platform (Cipher), and an AI job assistant (adpt) — which is well above typical freshman-year output. No professional experience is listed; all evidence is project and coursework-based.\nLanguages: C, HTML, JavaScript, Jupyter Notebook, Python, Shell, TypeScript\nStrengths:"
    },
    "repository_evaluations": [],
    "strengths": [],
    "growth_areas": [],
    "project_complexity_notes": [],
    "evidence_highlights": [],
    "recruiter_copy": "",
    "error": null,
    "reviewed": false,
    "created_at": "2026-05-29T03:56:45.002866",
    "updated_at": "2026-05-29T03:58:08.296298"
}