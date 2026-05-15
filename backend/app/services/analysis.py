import json
import re
from datetime import datetime, timedelta

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AnalysisStatus, GeneratedEvaluation, GitHubRepository, LeetCodeSnapshot, ProfileSection, User
from app.services.github import fetch_repo_code_context, get_github_access_token
from app.services.scoring import github_quality_signals, leetcode_signals, profile_signals


CAREER_STAGES = {"student", "new_grad", "early", "mid", "senior"}
CONFIDENCE_LEVELS = ["high", "medium", "low"]


def scored_dimension_schema(extra_properties: dict | None = None) -> dict:
    properties = {
        "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
        "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
        "stage_context": {"type": "string"},
        "basis": {"type": "array", "items": {"type": "string"}},
        "prose": {"type": "string"},
    }
    if extra_properties:
        properties.update(extra_properties)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "career_stage": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "stage": {"type": "string", "enum": list(CAREER_STAGES)},
                "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
                "signals_used": {"type": "array", "items": {"type": "string"}},
                "graduation_proximity": {"type": "string", "enum": ["current", "recent", "distant", "unknown"]},
            },
            "required": ["stage", "confidence", "signals_used", "graduation_proximity"],
        },
        "signal_completeness": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "code_quality": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "available": {"type": "boolean"},
                        "source": {"type": "string", "enum": ["code_context", "metadata_only", "none"]},
                        "repos_reviewed": {"type": "integer"},
                        "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
                    },
                    "required": ["available", "source", "repos_reviewed", "confidence"],
                },
                "delivery": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "available": {"type": "boolean"},
                        "commit_coverage": {"type": "string", "enum": ["full", "partial", "summary_only"]},
                        "recency": {"type": "string", "enum": ["active", "dormant", "unknown"]},
                    },
                    "required": ["available", "commit_coverage", "recency"],
                },
                "algorithms": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "available": {"type": "boolean"},
                        "primary_source": {"type": "string", "enum": ["leetcode", "repo_evidence", "both", "none"]},
                        "leetcode_strength": {"type": "string", "enum": ["strong", "moderate", "weak", "absent"]},
                        "repo_dsa_found": {"type": "boolean"},
                    },
                    "required": ["available", "primary_source", "leetcode_strength", "repo_dsa_found"],
                },
                "profile_depth": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "manual_sections": {"type": "integer"},
                        "has_experience": {"type": "boolean"},
                        "has_education": {"type": "boolean"},
                        "has_projects": {"type": "boolean"},
                    },
                    "required": ["manual_sections", "has_experience", "has_education", "has_projects"],
                },
            },
            "required": ["code_quality", "delivery", "algorithms", "profile_depth"],
        },
        "summary": {"type": "string"},
        "skill_model": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "code_quality": scored_dimension_schema(),
                "delivery": scored_dimension_schema({"trend": {"type": "string", "enum": ["accelerating", "steady", "declining", "unknown"]}}),
                "algorithms": scored_dimension_schema({"source": {"type": "string", "enum": ["leetcode", "repo_evidence", "both", "insufficient"]}}),
                "overall": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                        "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
                        "percentile_note": {"type": "string"},
                    },
                    "required": ["score", "confidence", "percentile_note"],
                },
            },
            "required": ["code_quality", "delivery", "algorithms", "overall"],
        },
        "repository_evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "full_name": {"type": "string"},
                    "language": {"type": ["string", "null"]},
                    "complexity_tier": {"type": "string", "enum": ["prototype", "project", "system"]},
                    "code_quality_notes": {"type": "string"},
                    "architecture_notes": {"type": "string"},
                    "maturity_signals": {"type": "array", "items": {"type": "string"}},
                    "dsa_evidence": {"type": ["string", "null"]},
                    "red_flags": {"type": "array", "items": {"type": "string"}},
                    "standout_signals": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "full_name",
                    "language",
                    "complexity_tier",
                    "code_quality_notes",
                    "architecture_notes",
                    "maturity_signals",
                    "dsa_evidence",
                    "red_flags",
                    "standout_signals",
                ],
            },
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "growth_areas": {"type": "array", "items": {"type": "string"}},
        "evidence_highlights": {"type": "array", "items": {"type": "string"}},
        "recruiter_copy": {"type": "string"},
    },
    "required": [
        "career_stage",
        "signal_completeness",
        "summary",
        "skill_model",
        "repository_evaluations",
        "strengths",
        "growth_areas",
        "evidence_highlights",
        "recruiter_copy",
    ],
}

EVALUATION_INSTRUCTIONS = """
ROLE
You are a senior engineering evaluator producing structured developer assessments for adpt. Your evaluations are read by developers who want honest feedback and by recruiters who need accurate signal. You are not a marketer.

CARDINAL RULES
- Every claim must trace to a specific source: a repo name, a file path, a LeetCode stat, or a profile section. No invented evidence.
- Do not use: "passionate", "rockstar", "ninja", "proven track record", "strong communicator", or any filler that carries no information.
- If evidence is missing, say what is missing and what it would change. Missing evidence is not a failing grade; it is an honest gap.
- Null scores mean insufficient evidence. Never return 0 when data is absent. 0 is a measurement. null is an absence of measurement.

CAREER STAGE CONTEXT
Read the career_stage object before writing anything. Your framing depends on it.
- student/new_grad: evaluate relative to peers at this stage, not working engineers. Coursework repos are valid learning evidence. Do not penalize expected lack of production experience. Recruiter copy should fit internship or new grad roles.
- early: some production experience may be expected. Evaluate transition from coursework/projects toward real systems.
- mid/senior: full engineering bar applies. Production quality, architecture decisions, and scale signal matter.

COURSEWORK REPO POLICY
Coursework-looking repositories are learning evidence. Assess code cleanliness, concept understanding, whether the developer went beyond minimum assignment work, and progression across repos. Do not penalize coursework repos for lacking production architecture.

ALGORITHMS SIGNAL POLICY
LeetCode is one algorithms source, not the only source. If LeetCode is absent or weak, scan selected repository names, descriptions, README text, structure, and key files for DSA evidence such as graph/tree/heap/dp/trie/sort/bfs/dfs, algorithms directories, competitive programming, Advent of Code, CS coursework, complexity notes, or custom algorithm implementations.
If repo-based DSA evidence exists, set algorithms.source to "repo_evidence" or "both", score from that evidence, and cite it. Do not penalize LeetCode absence when equivalent repo evidence exists.
If no algorithms signal exists, set algorithms.score to null, algorithms.source to "insufficient", and explain that no algorithms signal was found in LeetCode or repositories.

CODE QUALITY SCORING
Only score code_quality when selected_repository_code_context is non-empty. With metadata only, set score = null and note the gap. When code context exists, assess organization, naming/readability, architectural clarity, dependency choices, testability signals, README/config completeness, and project maturity.
Return one repository_evaluation object per repository with code context. If no code context is available, return an empty array.

SCORING HEURISTICS
- algorithms: strong LeetCode plus repo DSA -> 85-100; strong LeetCode alone -> 70-85; moderate LeetCode plus strong repo DSA -> 70-85; repo-only strong DSA -> 55-75; weak/minor signal -> 30-50; no signal -> null.
- code_quality: clean architecture with code context -> 70-100; mixed quality -> 40-70; unclear structure -> 20-40; metadata only -> null.
- delivery: active commits under 90 days plus multiple projects/completions -> 70-100; moderate activity -> 40-70; low/dormant -> 20-40; no commit data -> null.
- overall: weighted average of non-null dimensions: code_quality 0.40, delivery 0.35, algorithms 0.25. If fewer than two dimensions have scores, overall.score = null.

OUTPUT REQUIREMENTS
- summary: 2-4 evidence-backed sentences calibrated to career stage. Do not open with the developer's name.
- skill_model.code_quality.prose: specific code observations when available, otherwise state the code-review gap.
- skill_model.delivery.prose: commit cadence, recency, repo activity, and completion signals. For students, frame as learning consistency.
- skill_model.algorithms.prose: LeetCode plus repo DSA evidence, with source stated explicitly.
- strengths: 3-5 bullets; each must cite a concrete source.
- growth_areas: 2-4 constructive bullets. For students, do not list lack of production experience as a weakness.
- repository_evaluations: one object per repository with code context; empty array when no code context exists.
- evidence_highlights: 4-7 concrete facts with numbers, repo names, file paths, or section titles.
- recruiter_copy: one honest polished paragraph, calibrated to career stage.

Return only a JSON object matching the schema.
""".strip()


def build_evaluation_input(payload: dict) -> str:
    return (
        "Evaluate this developer evidence for an adpt profile. "
        "Use the instructions as the rubric and return JSON matching the schema.\n\n"
        f"Developer evidence payload:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def parse_profile_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def infer_career_stage(input_payload: dict, override: str | None = None) -> dict:
    if override in CAREER_STAGES:
        return {
            "stage": override,
            "confidence": "high",
            "signals_used": ["user-selected career stage override"],
            "graduation_proximity": "unknown",
        }

    signals_used = []
    stage = "early"
    confidence = "low"
    graduation_proximity = "unknown"
    now = datetime.utcnow()
    two_years_ago = now - timedelta(days=730)
    sections = input_payload.get("sections", [])
    education = [section for section in sections if section.get("kind") == "education"]
    experience = [section for section in sections if section.get("kind") == "experience"]
    bootcamps = [section for section in sections if section.get("kind") == "bootcamp"]

    for section in education:
        end_date = parse_profile_date(section.get("end_date"))
        if section.get("end_date") in (None, "") or (end_date and end_date > now):
            stage = "student"
            confidence = "high"
            graduation_proximity = "current"
            signals_used.append("education section has no end date or a future end date")
            break

    if stage != "student":
        for section in education:
            end_date = parse_profile_date(section.get("end_date"))
            if end_date and two_years_ago <= end_date <= now:
                graduation_proximity = "recent"
                if not experience:
                    stage = "new_grad"
                    confidence = "high"
                    signals_used.append("education end date within 2 years and no experience sections")
                break

    if stage == "early" and bootcamps and not experience:
        confidence = "medium"
        signals_used.append("bootcamp section present with no experience sections")

    if stage == "early" and input_payload.get("github", {}).get("commits", 0) < 200 and not experience:
        stage = "student"
        confidence = "medium"
        signals_used.append("low commit count with no experience sections")

    coursework_patterns = [
        re.compile(pattern, re.I)
        for pattern in (r"cs\d{2,3}", r"data.?struct", r"algorithm", r"assignment", r"homework", r"lab[-_]", r"project[-_]\d", r"\bcomp\d{3}")
    ]
    coursework_repos = [
        repo
        for repo in input_payload.get("selected_repositories_for_code_review", [])
        if any(pattern.search(repo.get("full_name", "")) for pattern in coursework_patterns)
    ]
    if coursework_repos:
        signals_used.append(f"{len(coursework_repos)} repo(s) match coursework naming patterns")
        if stage == "early":
            stage = "student"
            confidence = "medium"

    leetcode = input_payload.get("leetcode", {})
    if leetcode.get("available") and leetcode.get("total_solved", 0) > 100 and not experience and stage != "student":
        stage = "student"
        confidence = "medium"
        signals_used.append("high LeetCode volume with no work experience")

    if experience:
        signals_used.append(f"{len(experience)} experience section(s) provided")
        if confidence == "low":
            confidence = "medium"

    if not signals_used:
        signals_used.append("defaulted from limited profile evidence")

    return {
        "stage": stage,
        "confidence": confidence,
        "signals_used": signals_used,
        "graduation_proximity": graduation_proximity,
    }


def repo_dsa_found(input_payload: dict) -> bool:
    patterns = [
        re.compile(pattern, re.I)
        for pattern in (r"algorithm", r"data.?struct", r"\bdsa\b", r"leetcode", r"competitive", r"advent.?of.?code", r"codeforces", r"hackerrank", r"graph", r"tree", r"sorting", r"\bbfs\b", r"\bdfs\b", r"\bdp\b", r"trie", r"heap")
    ]
    texts = []
    for repo in input_payload.get("selected_repositories_for_code_review", []):
        texts.extend([repo.get("full_name", ""), repo.get("description") or ""])
    for context in input_payload.get("selected_repository_code_context", []):
        texts.extend([context.get("full_name", ""), context.get("readme", "")])
        texts.extend(context.get("structure_sample", []))
        for key_file in context.get("key_files", []):
            texts.extend([key_file.get("path", ""), key_file.get("content", "")[:2000]])
    return any(pattern.search(text) for pattern in patterns for text in texts if text)


def assess_signal_completeness(input_payload: dict) -> dict:
    selected_repos = input_payload.get("selected_repositories_for_code_review", [])
    code_context = input_payload.get("selected_repository_code_context", [])
    has_repos = len(selected_repos) > 0
    has_code_context = len(code_context) > 0
    pushed_dates = [parse_profile_date(repo.get("pushed_at", "")[:10]) for repo in selected_repos if repo.get("pushed_at")]
    pushed_dates = [date for date in pushed_dates if date]
    most_recent = max(pushed_dates) if pushed_dates else None
    recency = "unknown"
    if most_recent:
        recency = "active" if most_recent > datetime.utcnow() - timedelta(days=90) else "dormant"

    leetcode = input_payload.get("leetcode", {})
    leetcode_strength = "absent"
    if leetcode.get("available"):
        medium_hard = leetcode.get("medium_solved", 0) + leetcode.get("hard_solved", 0)
        if medium_hard >= 100:
            leetcode_strength = "strong"
        elif medium_hard >= 30:
            leetcode_strength = "moderate"
        else:
            leetcode_strength = "weak"

    dsa_found = repo_dsa_found(input_payload)
    if leetcode.get("available") and dsa_found:
        algorithm_source = "both"
    elif leetcode.get("available"):
        algorithm_source = "leetcode"
    elif dsa_found:
        algorithm_source = "repo_evidence"
    else:
        algorithm_source = "none"

    sections = input_payload.get("sections", [])
    return {
        "code_quality": {
            "available": has_repos,
            "source": "code_context" if has_code_context else "metadata_only" if has_repos else "none",
            "repos_reviewed": len(code_context),
            "confidence": "high" if has_code_context else "medium" if has_repos else "low",
        },
        "delivery": {
            "available": input_payload.get("github", {}).get("commits", 0) > 0,
            "commit_coverage": "summary_only",
            "recency": recency,
        },
        "algorithms": {
            "available": algorithm_source != "none",
            "primary_source": algorithm_source,
            "leetcode_strength": leetcode_strength,
            "repo_dsa_found": dsa_found,
        },
        "profile_depth": {
            "manual_sections": len(sections),
            "has_experience": any(section.get("kind") == "experience" for section in sections),
            "has_education": any(section.get("kind") == "education" for section in sections),
            "has_projects": any(section.get("kind") == "project" for section in sections),
        },
    }


def metadata_complexity_hint(selected_repositories: list[dict]) -> str:
    if not selected_repositories:
        return "insufficient_data"
    if any(repo.get("commit_count", 0) > 50 for repo in selected_repositories):
        return "needs_code_review"
    return "emerging"


def build_analysis_payload(
    user: User,
    repositories: list[GitHubRepository],
    leetcode: LeetCodeSnapshot | None,
    sections: list[ProfileSection],
    selected_code_context: list[dict] | None = None,
) -> dict:
    selected_repositories = [
        {
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "stars": repo.stars,
            "forks": repo.forks,
            "commit_count": repo.commit_count,
            "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
        }
        for repo in repositories
        if repo.selected_for_analysis
    ]
    payload = {
        "profile": {"name": user.name, "headline": user.headline},
        "github": github_quality_signals(repositories),
        "metadata_complexity_hint": metadata_complexity_hint(selected_repositories),
        "selected_repositories_for_code_review": selected_repositories,
        "selected_repository_code_context": selected_code_context or [],
        "leetcode": leetcode_signals(leetcode),
        "sections": [
            {
                "kind": section.kind,
                "title": section.title,
                "organization": section.organization,
                "start_date": section.start_date,
                "end_date": section.end_date,
                "description": section.description,
                "url": section.url,
            }
            for section in sections
        ],
        "manual_profile": profile_signals(sections),
    }
    payload["career_stage"] = infer_career_stage(payload, user.career_stage_override)
    payload["signal_completeness"] = assess_signal_completeness(payload)
    return payload


def fallback_analysis(payload: dict) -> dict:
    github = payload.get("github", {})
    career_stage = payload.get("career_stage", infer_career_stage(payload))
    signal_completeness = payload.get("signal_completeness", assess_signal_completeness(payload))
    return {
        "career_stage": career_stage,
        "signal_completeness": signal_completeness,
        "summary": (
            "Evaluation generated in fallback mode. Connect an OpenAI API key for full stage-aware code, delivery, "
            "and algorithms analysis."
        ),
        "skill_model": {
            "code_quality": {"score": None, "confidence": "low", "stage_context": "", "basis": [], "prose": "Fallback mode cannot evaluate code quality."},
            "delivery": {"score": None, "confidence": "low", "stage_context": "", "basis": [], "prose": "Fallback mode cannot score delivery.", "trend": "unknown"},
            "algorithms": {"score": None, "confidence": "low", "stage_context": "", "basis": [], "prose": "Fallback mode cannot score algorithms.", "source": "insufficient"},
            "overall": {"score": None, "confidence": "low", "percentile_note": ""},
        },
        "repository_evaluations": [],
        "strengths": ["Evaluation unavailable in fallback mode."],
        "growth_areas": [
            "Connect an OpenAI API key to generate a full evaluation.",
            "Select up to five repositories so code quality can be reviewed from actual code context.",
        ],
        "evidence_highlights": [
            f"{github.get('repository_count', 0)} GitHub repositories synced.",
            f"{github.get('commits', 0)} total synced commits observed.",
        ],
        "recruiter_copy": "Evaluation unavailable in fallback mode.",
    }


def legacy_skill_model(v2_skill_model: dict | None) -> dict | None:
    if not v2_skill_model:
        return None
    return {
        "code_quality": v2_skill_model.get("code_quality", {}).get("prose", ""),
        "delivery": v2_skill_model.get("delivery", {}).get("prose", ""),
        "algorithms": v2_skill_model.get("algorithms", {}).get("prose", ""),
    }


def legacy_project_complexity_notes(repository_evaluations: list | None) -> list:
    if not repository_evaluations:
        return []
    notes = []
    for repo in repository_evaluations:
        full_name = repo.get("full_name", "selected repository")
        tier = repo.get("complexity_tier", "project")
        architecture = repo.get("architecture_notes", "")
        notes.append(f"{full_name} is assessed as {tier}. {architecture}".strip())
    return notes


def generate_with_openai(payload: dict) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return fallback_analysis(payload)

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_model,
        instructions=EVALUATION_INSTRUCTIONS,
        input=build_evaluation_input(payload),
        text={
            "format": {
                "type": "json_schema",
                "name": "adpt_developer_evaluation",
                "schema": ANALYSIS_SCHEMA,
                "strict": True,
            }
        },
    )
    return json.loads(response.output_text)


def run_analysis(db: Session, user: User, evaluation: GeneratedEvaluation) -> GeneratedEvaluation:
    evaluation.status = AnalysisStatus.running
    evaluation.updated_at = datetime.utcnow()
    db.commit()

    try:
        repositories = db.query(GitHubRepository).filter(GitHubRepository.user_id == user.id).all()
        selected_repositories = [repo for repo in repositories if repo.selected_for_analysis][:5]
        access_token = get_github_access_token(db, user)
        selected_code_context = []
        for repo in selected_repositories:
            try:
                context = fetch_repo_code_context(repo.full_name, access_token)
                repo.code_analysis_snapshot = context
                selected_code_context.append(context)
            except Exception as exc:
                selected_code_context.append({"full_name": repo.full_name, "error": str(exc)})
        leetcode = (
            db.query(LeetCodeSnapshot)
            .filter(LeetCodeSnapshot.user_id == user.id)
            .order_by(LeetCodeSnapshot.created_at.desc())
            .first()
        )
        sections = db.query(ProfileSection).filter(ProfileSection.user_id == user.id).order_by(ProfileSection.order).all()
        payload = build_analysis_payload(user, repositories, leetcode, sections, selected_code_context)
        generated = generate_with_openai(payload)

        evaluation.status = AnalysisStatus.ready
        evaluation.summary = generated["summary"]
        evaluation.skill_model_v2 = generated["skill_model"]
        evaluation.skill_model = legacy_skill_model(generated["skill_model"])
        evaluation.career_stage = generated["career_stage"]
        evaluation.signal_completeness = generated["signal_completeness"]
        evaluation.repository_evaluations = generated["repository_evaluations"]
        evaluation.strengths = generated["strengths"]
        evaluation.growth_areas = generated["growth_areas"]
        evaluation.project_complexity_notes = legacy_project_complexity_notes(generated["repository_evaluations"])
        evaluation.evidence_highlights = generated["evidence_highlights"]
        evaluation.recruiter_copy = generated["recruiter_copy"]
        evaluation.error = None
    except Exception as exc:  # pragma: no cover - exercised by integration tests with service mocks
        evaluation.status = AnalysisStatus.failed
        evaluation.error = str(exc)

    evaluation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(evaluation)
    return evaluation
