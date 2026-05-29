import json
import re
from datetime import datetime, timedelta
from typing import Literal

from anthropic import Anthropic
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AnalysisStatus, GeneratedEvaluation, GitHubRepository, LeetCodeSnapshot, ProfileSection, User
from app.services.embeddings import build_rag_context, repo_has_embeddings, upsert_profile_embedding
from app.services.scoring import github_quality_signals, leetcode_signals, profile_signals
import logging

logger = logging.getLogger(__name__)


CAREER_STAGES = {"student", "new_grad", "early", "mid", "senior"}
CONFIDENCE_LEVELS = ["high", "medium", "low"]
OVERALL_SCORE_WEIGHTS = {"code_quality": 0.50, "delivery": 0.35, "algorithms": 0.15}
MAX_PROMPT_CODE_CONTEXT_REPOS = 20
MAX_PROMPT_CODE_CONTEXT_CHARS = 500000
RETRY_PROMPT_CODE_CONTEXT_REPOS = 20
RETRY_PROMPT_CODE_CONTEXT_CHARS = 260000
HIGH_SIGNAL_FILES_PER_REPO = 4
MAX_PROMPT_README_CHARS = 2500
MAX_PROMPT_FILE_CHARS = 3500
MAX_RAG_CHUNKS_PER_DIMENSION = 16
RETRY_RAG_CHUNKS_PER_DIMENSION = 8


def normalize_overall_score(skill_model: dict) -> dict:
    overall = skill_model.get("overall") if isinstance(skill_model, dict) else None
    valid_scores = []
    for dimension, weight in OVERALL_SCORE_WEIGHTS.items():
        dimension_model = skill_model.get(dimension, {}) if isinstance(skill_model, dict) else {}
        score = dimension_model.get("score") if isinstance(dimension_model, dict) else None
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            valid_scores.append((score, weight))

    base_overall = dict(overall) if isinstance(overall, dict) else {}

    if len(valid_scores) < 2:
        base_overall["score"] = None
        base_overall["confidence"] = "low"
        base_overall["percentile_note"] = base_overall.get("percentile_note", "")
        return base_overall

    weighted_score = sum(score * weight for score, weight in valid_scores) / sum(weight for _, weight in valid_scores)
    base_overall["score"] = round(weighted_score, 1)
    base_overall["confidence"] = "high" if len(valid_scores) == 3 else "medium"
    base_overall["percentile_note"] = base_overall.get("percentile_note", "")
    return base_overall


def count_end_to_end_systems(repository_evaluations: list | None) -> int:
    if not repository_evaluations:
        return 0
    return sum(1 for repo in repository_evaluations if repo.get("complexity_tier") == "system")


def floor_delivery_score(skill_model: dict, repository_evaluations: list | None) -> dict:
    if not isinstance(skill_model, dict):
        return skill_model

    delivery = skill_model.get("delivery")
    if not isinstance(delivery, dict):
        return skill_model

    system_count = count_end_to_end_systems(repository_evaluations)
    if system_count < 3:
        return skill_model

    floored_delivery = dict(delivery)
    current_score = floored_delivery.get("score")
    if not isinstance(current_score, (int, float)) or isinstance(current_score, bool):
        floored_delivery["score"] = 78
    else:
        floored_delivery["score"] = max(round(current_score, 1), 78)
    if floored_delivery.get("confidence") == "low":
        floored_delivery["confidence"] = "medium"

    updated_skill_model = dict(skill_model)
    updated_skill_model["delivery"] = floored_delivery
    return updated_skill_model


def scope_overall_score(skill_model: dict, career_stage: dict | None) -> dict:
    if not isinstance(skill_model, dict):
        return skill_model

    overall = skill_model.get("overall")
    if not isinstance(overall, dict):
        return skill_model

    stage = career_stage.get("stage") if isinstance(career_stage, dict) else None
    stage_nouns = {
        "student": "intern",
        "new_grad": "new grad",
        "early": "early-career engineer",
        "mid": "mid-level engineer",
        "senior": "senior engineer",
    }
    score = overall.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        if score >= 90:
            adjective = "Great"
        elif score >= 80:
            adjective = "Strong"
        elif score >= 70:
            adjective = "Solid"
        elif score >= 60:
            adjective = "Developing"
        else:
            adjective = "Emerging"
    else:
        adjective = "Insufficient"

    scoped_overall = dict(overall)
    scoped_overall["scope_stage"] = stage or "unknown"
    scoped_overall["scope_label"] = f"{adjective} {stage_nouns.get(stage, 'candidate')}"

    updated_skill_model = dict(skill_model)
    updated_skill_model["overall"] = scoped_overall
    return updated_skill_model


def normalize_generated_analysis(generated: dict) -> dict:
    if not isinstance(generated, dict):
        return generated
    normalized = dict(generated)

    for key in ("skill_model", "career_stage", "signal_completeness", "temporal_signals", "hiring_recommendation"):
        value = normalized.get(key)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                normalized[key] = parsed

    for key in (
        "repository_evaluations",
        "strengths",
        "growth_areas",
        "evidence_highlights",
        "role_fit",
        "manual_section_evaluations",
        "interview_questions",
        "recruiter_risks",
    ):
        value = normalized.get(key)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                normalized[key] = parsed

    repository_evaluations = normalized.get("repository_evaluations")
    if isinstance(repository_evaluations, list):
        normalized["repository_evaluations"] = [item for item in repository_evaluations if isinstance(item, dict)]

    for key in (
        "strengths",
        "growth_areas",
        "evidence_highlights",
        "role_fit",
        "manual_section_evaluations",
        "interview_questions",
        "recruiter_risks",
    ):
        if not isinstance(normalized.get(key), list):
            normalized[key] = []
    if not isinstance(normalized.get("repository_evaluations"), list):
        normalized["repository_evaluations"] = []
    if not isinstance(normalized.get("recruiter_copy"), str):
        normalized["recruiter_copy"] = ""

    skill_model = generated.get("skill_model")
    if not isinstance(skill_model, dict):
        return normalized

    normalized_skill_model = dict(skill_model)
    normalized_skill_model = floor_delivery_score(normalized_skill_model, normalized.get("repository_evaluations"))
    normalized_skill_model["overall"] = normalize_overall_score(normalized_skill_model)
    normalized_skill_model = scope_overall_score(normalized_skill_model, normalized.get("career_stage"))
    normalized["skill_model"] = normalized_skill_model
    return normalized


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


HIRING_RECOMMENDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["recommend", "consider", "hold", "insufficient_evidence"]},
        "best_fit_level": {"type": "string"},
        "best_fit_roles": {"type": "array", "items": {"type": "string"}},
        "strongest_hiring_signal": {"type": "string"},
        "primary_verification_point": {"type": "string"},
        "summary": {"type": "string"},
        "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
    },
    "required": [
        "decision",
        "best_fit_level",
        "best_fit_roles",
        "strongest_hiring_signal",
        "primary_verification_point",
        "summary",
        "confidence",
    ],
}


ROLE_FIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "role": {"type": "string"},
        "fit": {"type": "string", "enum": ["strong", "partial", "unsupported"]},
        "level": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["role", "fit", "level", "evidence", "gaps"],
}


MANUAL_SECTION_EVALUATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "kind": {"type": "string"},
        "title": {"type": "string"},
        "recruiter_value": {"type": "string", "enum": ["strong", "moderate", "limited", "unclear"]},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "verification_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kind", "title", "recruiter_value", "evidence", "verification_points"],
}


INTERVIEW_QUESTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "question": {"type": "string"},
        "verifies": {"type": "string"},
        "source": {"type": "string"},
    },
    "required": ["question", "verifies", "source"],
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
                        "repo_dsa_found": {"type": "boolean"},
                    },
                    "required": ["available", "primary_source", "repo_dsa_found"],
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
        "temporal_signals": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "available": {"type": "boolean"},
                "evolution_narrative": {"type": "string"},
                "language_shifts": {"type": "string"},
                "complexity_trend": {"type": "string", "enum": ["growing", "steady", "declining", "insufficient_data", "unknown"]},
                "active_years": {"type": "number"},
            },
            "required": ["available", "evolution_narrative", "language_shifts", "complexity_trend", "active_years"],
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
                        "scope_stage": {"type": "string", "enum": ["student", "new_grad", "early", "mid", "senior", "unknown"]},
                        "scope_label": {"type": "string"},
                    },
                    "required": ["score", "confidence", "percentile_note", "scope_stage", "scope_label"],
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
                    "architecture_signals_observed": {"type": "array", "items": {"type": "string"}},
                    "specific_code_references": {"type": "array", "items": {"type": "string"}},
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
                    "architecture_signals_observed",
                    "specific_code_references",
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
        "hiring_recommendation": HIRING_RECOMMENDATION_SCHEMA,
        "role_fit": {"type": "array", "items": ROLE_FIT_SCHEMA},
        "manual_section_evaluations": {"type": "array", "items": MANUAL_SECTION_EVALUATION_SCHEMA},
        "interview_questions": {"type": "array", "items": INTERVIEW_QUESTION_SCHEMA},
        "recruiter_risks": {"type": "array", "items": {"type": "string"}},
        "recruiter_copy": {"type": "string"},
    },
    "required": [
        "career_stage",
        "signal_completeness",
        "summary",
        "skill_model",
        "repository_evaluations",
        "temporal_signals",
        "strengths",
        "growth_areas",
        "evidence_highlights",
        "hiring_recommendation",
        "role_fit",
        "manual_section_evaluations",
        "interview_questions",
        "recruiter_risks",
        "recruiter_copy",
    ],
}

EVALUATION_INSTRUCTIONS = """
ROLE
You are a senior engineering evaluator producing structured developer assessments for cipher. Your evaluations are read by developers who want honest feedback and by recruiters who need accurate signal. You are not a marketer.

CARDINAL RULES
- Every claim must trace to a specific source: a repo name, a file path, a profile section, or a LeetCode stat when LeetCode data is present. No invented evidence.
- Do not use: "passionate", "rockstar", "ninja", "proven track record", "strong communicator", or any filler that carries no information.
- If evidence is missing, say what is missing and what it would change. Missing evidence is not a failing grade; it is an honest gap.
- Null scores mean insufficient evidence. Never return 0 when data is absent. 0 is a measurement. null is an absence of measurement.

EVALUATION WORKFLOW
- First identify the strongest evidence available for each dimension: rag_code_context plus selected repository code context for code quality, activity plus completed work for delivery, and repo DSA plus provided LeetCode data for algorithms.
- Then judge whether the signal is strong, mixed, weak, or absent. Weak signal should lower scores instead of being averaged away.
- For delivery, use commit counts, pushed_at recency, and recent commit messages/change summaries when available. Commit volume is activity evidence, but recent messages reveal whether work reflects meaningful product changes, maintenance, experiments, or trivial churn.
- Treat manual profile sections as first-class recruiter evidence. Evaluate education, experience, projects, bootcamps, and certifications for relevance, recency, credibility/detail level, consistency with GitHub evidence, and missing context a recruiter should verify.
- Treat rag_code_context as the primary code evidence. It is grouped by review dimension and contains retrieved chunks from the vector index. Cite `repo` and `file_path` from RAG chunks when making code claims.
- If rag_code_context is empty or embedding_precompute reports errors/zero stored chunks, use selected_repository_code_context as the file-model fallback. This fallback is intentionally balanced: README plus high-signal files for each selected repository.
- If the prompt contains noisy or generated artifacts, ignore them unless they are part of a specific engineering choice worth noting.
- If the repo is mostly scaffolding, lockfiles, cache directories, generated code, or empty shells, treat that as weak signal and say so explicitly.

EVIDENCE HIERARCHY
- Highest: RAG-retrieved code chunks, selected code context, architecture, tests, file structure, and repo-specific implementation details.
- Medium: manual profile sections with concrete descriptions, repository metadata such as descriptions, language, stars, forks, and commit history.
- Lower: provided LeetCode and other external practice stats, which should support but not dominate the evaluation.
- Lowest: noisy paths, generated files, cache folders, and dependency artifacts.

CAREER STAGE CONTEXT
Read the career_stage object before writing anything. Your framing depends on it.
- student/new_grad: evaluate relative to peers at this stage, not working engineers. Coursework repos are valid learning evidence. Do not penalize expected lack of production experience. Recruiter copy should fit internship or new grad roles.
- early: some production experience may be expected. Evaluate transition from coursework/projects toward real systems.
- mid/senior: full engineering bar applies. Production quality, architecture decisions, and scale signal matter.

PEER CALIBRATION AND ACCURACY
- Score and describe the developer against the peer cohort implied by career_stage.scope: students against internship/new-grad peers, early-career developers against early-career peers, and mid/senior developers against practicing engineers at that level.
- Do not compare a student or new grad to a senior production engineer unless explicitly noting a future growth path.
- Prefer conservative, evidence-backed scores over flattering scores. If the evidence is thin, lower confidence or return null instead of filling gaps with assumptions.
- Calibrate high scores to unusually strong evidence for that cohort: multiple completed systems, concrete architecture choices, tests, deployed work, sustained activity, or clear algorithm implementations.
- Keep all percentile/ranking language scoped to the cohort. For example, use "strong for a new-grad profile" rather than "strong engineer" when career_stage is student or new_grad.

COURSEWORK REPO POLICY
Coursework-looking repositories are learning evidence. Assess code cleanliness, concept understanding, whether the developer went beyond minimum assignment work, and progression across repos. Do not penalize coursework repos for lacking production architecture.

ALGORITHMS SIGNAL POLICY
LeetCode is only a supporting signal when the payload includes a leetcode object. Repo evidence, code context, and project quality should dominate the algorithms assessment.
If the payload does not include a leetcode object, do not mention LeetCode or its absence anywhere in the analysis. Instead, scan selected repository names, descriptions, README text, structure, and key files for DSA evidence such as graph/tree/heap/dp/trie/sort/bfs/dfs, algorithms directories, competitive programming, Advent of Code, CS coursework, complexity notes, or custom algorithm implementations.
If a leetcode object is present but weak, scan repositories for stronger DSA evidence before scoring.
If repo-based DSA evidence exists, set algorithms.source to "repo_evidence" or "both", score from that evidence, and cite it. Do not over-reward LeetCode-only signal when repo evidence is thin or absent.
If no algorithms signal exists, set algorithms.score to null, algorithms.source to "insufficient", and explain that no algorithms signal was found in the available evidence.

NEGATIVE SIGNAL POLICY
- Do not materially penalize general repo hygiene issues such as build artifacts, cache directories, generated files, or dependency folders. Treat them as neutral unless they are directly relevant to a code quality observation.
- Only committed env/secrets files should be treated as hygiene warnings, and those warnings should be narrow and specific.
- If committed env files exist, mention them as a caution flag; do not let them dominate the score unless they are the clearest evidence in the repo.

CODE QUALITY SCORING
Only score code_quality when rag_code_context or selected_repository_code_context is non-empty. With metadata only, set score = null and note the gap. When code context exists, assess organization, naming/readability, architectural clarity, dependency choices, testability signals, README/config completeness, and project maturity.
Return one repository_evaluation object per repository with RAG or selected code context. If no code context is available, return an empty array.
If selected_repository_code_context_omissions is non-empty, treat those repositories as omitted due prompt budget constraints, not as missing user signal.

TEMPORAL ANALYSIS
- temporal_signals tracks how the developer has evolved.
- Strong examples:
    - "Started in C during coursework, transitioned to Python and TypeScript over the last 18 months."
    - "Consistent Python usage across 3 years with growing project complexity."
- Frame language transitions as growth, not weakness.
- Populate evolution_narrative as 1-2 sentences; language_shifts as a one-liner.
- Reference temporal signals in summary and recruiter_copy.

ARCHITECTURE SIGNAL POLICY
- Each code_context includes architecture_signals from the actual file tree.
- Populate architecture_signals_observed with concrete patterns: ["layered architecture", "CI workflows", "Docker setup", "migrations"].
- Architecture observations push delivery and code_quality scores upward when production patterns are present.
- Cross-reference with temporal_signals — architectural maturity over time is a strong delivery signal.

DEEPER CODE REASONING
- code_quality_notes and architecture_notes must cite specific files or patterns — not generic praise.
- Weak (AVOID): "Clean code structure", "Good separation of concerns."
- Strong (PREFER): "auth.py uses JWT with bcrypt password hashing; main.py wires FastAPI with dependency injection."
- Populate specific_code_references with the file paths cited.
- One concrete architectural choice per repo in architecture_notes. Skip if not concrete.

RECRUITER DECISION AID
- The output should help a recruiter decide whether to interview the candidate, for which role, and what to verify.
- hiring_recommendation.decision must be one of: recommend, consider, hold, insufficient_evidence. Use recommend only when the evidence clearly supports an interview for the named level/role family. Use consider for promising but incomplete evidence. Use hold for meaningful concerns. Use insufficient_evidence when the profile lacks enough signal.
- role_fit must map evidence to likely role fits such as internship, new grad, frontend, backend, full-stack, data, infrastructure, systems, or mobile. Do not infer role fit from languages alone; cite projects, files, commits, profile sections, or LeetCode stats when present.
- recruiter_risks should be recruiter-relevant verification points, not nitpicks: thin code evidence, stale activity, mostly coursework/tutorial work, unclear ownership, no test/deployment evidence, missing work history, or weak role alignment.
- interview_questions must include 3-5 tailored questions. Each question should verify a specific claim, repo, manual section, or gap.
- For every major claim, distinguish observed evidence from interpretation. Never present interpretation as fact.

SCORING HEURISTICS
- algorithms: strong provided LeetCode plus repo DSA -> 80-95; strong provided LeetCode alone -> 60-75; moderate provided LeetCode plus strong repo DSA -> 65-80; repo-only strong DSA -> 80-90; weak/minor available signal -> 25-45; no available signal -> null.
- code_quality: clean architecture with code context -> 70-100; mixed quality -> 40-70; unclear structure -> 20-40; poor architecture, weak projects, or generated-artifact-heavy repos should drop below the middle band; metadata only -> null.
- code_quality: clean architecture with code context -> 70-100; mixed quality -> 40-70; unclear structure -> 20-40; metadata only -> null.
- delivery: active commits under 90 days plus multiple projects/completions -> 70-100; 3+ end-to-end systems should not score below 78; moderate activity -> 40-70; low/dormant -> 20-40; no commit data -> null.
- overall: weighted average of non-null dimensions: code_quality 0.45, delivery 0.40, algorithms 0.15. If fewer than two dimensions have scores, overall.score = null.

SCORING ANCHORS
- Treat architecture problems as first-class issues: missing boundaries, ad hoc coupling, lack of tests, or weak separation of concerns should lower code_quality even if the repo has many files.
- Treat polished boilerplate or auto-generated structure as low signal unless the developer made clear engineering choices on top of it.
- Treat LeetCode as evidence of algorithm practice only when the payload includes it, not system design, code quality, or product maturity.
- Treat strong repo-based DSA as a top-tier algorithms signal; that should commonly land in the 80s when the repo evidence is clear and specific.
- Treat 3 or more end-to-end systems as a strong delivery signal; delivery.score should be floored at 78 when that evidence is present.
- Treat live, deployed, actively maintained, or otherwise production-shaped projects as system-tier repositories.
- Treat commit count as activity only; do not assume strong delivery from raw commit volume if the work is repetitive, generated, or trivial.

OUTPUT REQUIREMENTS
- summary: 2-4 evidence-backed sentences calibrated to career stage. Do not open with the developer's name.
- skill_model.code_quality.prose: specific code observations when available, otherwise state the code-review gap.
- skill_model.delivery.prose: commit cadence, recency, repo activity, recent commit/change summaries, and completion signals. For students, frame as learning consistency.
- skill_model.algorithms.prose: repo DSA evidence and available LeetCode evidence when present, with source stated explicitly. If LeetCode is not in the payload, do not refer to it.
- strengths: 3-5 bullets; each must cite a concrete source.
- growth_areas: 2-4 constructive bullets. For students, do not list lack of production experience as a weakness.
- repository_evaluations: one object per repository with code context; empty array when no code context exists.
- evidence_highlights: 4-7 concrete facts with numbers, repo names, file paths, or section titles, each using APA-like parenthetical in-text citations such as `(repo-name, path/to/file.py)`. Use LeetCode citations only when the payload includes LeetCode data.
- manual_section_evaluations: one object for each manual section. If a section has little detail, say its recruiter value is limited or unclear and give a verification point.
- hiring_recommendation: concise hiring decision aid with best-fit level, best-fit roles, strongest hiring signal, primary verification point, and confidence.
- role_fit: 3-6 role fits, each marked strong, partial, or unsupported with evidence and gaps.
- interview_questions: 3-5 recruiter screening or technical follow-up questions tailored to the evidence.
- recruiter_risks: 2-5 concrete verification points. Keep them fair and evidence-based.
- recruiter_copy: an honest, polished hiring brief calibrated to career stage. Use this structure in plain text: Recommendation: ... Best-fit roles: ... Why interview: ... Verify: ... Evidence basis: ... Then include COMPETENCE_RANKING on one line.

HUMAN-READABLE ANALYSIS & COMPETENCE RANKING (required)
- Provide a clear, human-readable hiring brief intended for the recruiter as the first part of `recruiter_copy`. It should answer: should this person be interviewed, for what role/level, why, and what should be verified. Avoid JSON or list markup inside this paragraph.
- After that paragraph in the same `recruiter_copy` string, include a short "Competence ranking" section labeled `COMPETENCE_RANKING:` followed by a concise ranked list (single-line entries separated by semicolons) of the primary skill dimensions with both a qualitative label and numeric score, e.g.
    COMPETENCE_RANKING: Code Quality — Proficient (78); Delivery — Developing (62); Algorithms — Strong (85).
- For each skill include: name, qualitative label (Expert / Proficient / Developing / Insufficient), numeric 0-100 score or `null` if insufficient evidence, and a one-word confidence (`high`/`medium`/`low`) in parentheses after the score. Keep the entire competence ranking as a single line or sentence so it remains valid JSON string content.

CITATION STYLE
- When referring to evidence, prefer concise APA-like parenthetical citations in the form `(source, detail)` or `(source, detail; source, detail)`.
- Reuse citations consistently across summary, strengths, growth areas, evidence highlights, and recruiter copy so the reader can trace each claim back to a specific repo, file, or stat.

Return only a JSON object matching the schema.
""".strip()


def build_evaluation_input(payload: dict) -> str:
    return (
        "Evaluate this developer evidence for a cipher profile. "
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
    raw_rag_context = input_payload.get("rag_code_context") or {}
    rag_context = raw_rag_context if isinstance(raw_rag_context, dict) else {}
    for chunks in rag_context.values():
        for chunk in chunks or []:
            texts.extend([chunk.get("file_path", ""), chunk.get("content", "")[:2000]])
    return any(pattern.search(text) for pattern in patterns for text in texts if text)


def assess_signal_completeness(input_payload: dict) -> dict:
    selected_repos = input_payload.get("selected_repositories_for_code_review", [])
    code_context = input_payload.get("selected_repository_code_context", [])
    raw_rag_context = input_payload.get("rag_code_context") or {}
    rag_context = raw_rag_context if isinstance(raw_rag_context, dict) else {}
    rag_chunk_count = sum(len(chunks or []) for chunks in rag_context.values())
    has_repos = len(selected_repos) > 0
    has_code_context = len(code_context) > 0 or rag_chunk_count > 0
    pushed_dates = [parse_profile_date(repo.get("pushed_at", "")[:10]) for repo in selected_repos if repo.get("pushed_at")]
    pushed_dates = [date for date in pushed_dates if date]
    most_recent = max(pushed_dates) if pushed_dates else None
    recency = "unknown"
    if most_recent:
        recency = "active" if most_recent > datetime.utcnow() - timedelta(days=90) else "dormant"

    leetcode = input_payload.get("leetcode")
    leetcode_available = isinstance(leetcode, dict) and leetcode.get("available")

    dsa_found = repo_dsa_found(input_payload)
    if leetcode_available and dsa_found:
        algorithm_source = "both"
    elif leetcode_available:
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
            "repos_reviewed": len({chunk.get("repo") for chunks in rag_context.values() for chunk in (chunks or []) if isinstance(chunk, dict) and chunk.get("repo")}) or len(code_context),
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
            "repo_dsa_found": dsa_found,
        },
        "profile_depth": {
            "manual_sections": len(sections),
            "has_experience": any(section.get("kind") == "experience" for section in sections),
            "has_education": any(section.get("kind") == "education" for section in sections),
            "has_projects": any(section.get("kind") == "project" for section in sections),
        },
    }


def compute_temporal_signals(repositories: list[GitHubRepository]) -> dict:
    """Extract evolution signals across the developer's repo history."""
    def repo_date(repo: GitHubRepository) -> datetime | None:
        raw = getattr(repo, "raw", None)
        created_at = raw.get("created_at") if isinstance(raw, dict) else None
        if isinstance(created_at, str):
            parsed = parse_profile_date(created_at[:10])
            if parsed:
                return parsed
        return getattr(repo, "pushed_at", None) or getattr(repo, "created_at", None)

    repos_with_dates = [r for r in repositories if repo_date(r)]
    if not repos_with_dates:
        return {
            "available": False,
            "language_timeline": [],
            "abandoned_languages": [],
            "adopted_languages": [],
            "consistent_languages": [],
            "complexity_trend": "unknown",
            "first_repo_date": None,
            "latest_activity_date": None,
            "active_years": 0,
        }

    sorted_repos = sorted(repos_with_dates, key=lambda r: repo_date(r) or datetime.max)

    language_timeline = [
        {
            "date": (repo_date(repo) or datetime.utcnow()).isoformat(),
            "language": repo.language,
            "repo": repo.full_name,
            "commits": repo.commit_count or 0,
        }
        for repo in sorted_repos
        if repo.language
    ]

    lang_first_seen: dict[str, datetime] = {}
    lang_last_seen: dict[str, datetime] = {}
    from collections import defaultdict

    lang_repo_count: dict[str, int] = defaultdict(int)

    for repo in sorted_repos:
        if not repo.language:
            continue
        lang = repo.language
        first_date = repo_date(repo)
        if not first_date:
            continue
        date = getattr(repo, "pushed_at", None) or first_date
        if lang not in lang_first_seen:
            lang_first_seen[lang] = first_date
        lang_last_seen[lang] = max(lang_last_seen.get(lang, date), date)
        lang_repo_count[lang] += 1

    now = datetime.utcnow()
    one_year_ago = now - timedelta(days=365)
    two_years_ago = now - timedelta(days=730)

    abandoned_languages = []
    adopted_languages = []
    consistent_languages = []

    for lang, last_seen in lang_last_seen.items():
        first_seen = lang_first_seen[lang]
        repo_count = lang_repo_count[lang]
        if last_seen < one_year_ago and first_seen < two_years_ago:
            abandoned_languages.append({
                "language": lang,
                "last_used": last_seen.isoformat(),
                "repo_count": repo_count,
            })
        elif first_seen > one_year_ago:
            adopted_languages.append({
                "language": lang,
                "first_used": first_seen.isoformat(),
                "repo_count": repo_count,
            })
        elif repo_count >= 2 and last_seen > one_year_ago:
            consistent_languages.append({"language": lang, "repo_count": repo_count})

    if len(sorted_repos) >= 3:
        third = max(1, len(sorted_repos) // 3)
        early = sorted_repos[:third]
        recent = sorted_repos[-third:]
        early_avg = sum((r.commit_count or 0) for r in early) / len(early)
        recent_avg = sum((r.commit_count or 0) for r in recent) / len(recent)
        if recent_avg > early_avg * 1.5:
            complexity_trend = "growing"
        elif recent_avg < early_avg * 0.5:
            complexity_trend = "declining"
        else:
            complexity_trend = "steady"
    else:
        complexity_trend = "insufficient_data"

    first_repo = repo_date(sorted_repos[0]) or datetime.utcnow()
    latest_activity = max((getattr(r, "pushed_at", None) or repo_date(r) or first_repo) for r in sorted_repos)
    active_years = round((latest_activity - first_repo).days / 365, 1)

    return {
        "available": True,
        "language_timeline": language_timeline[-30:],
        "abandoned_languages": abandoned_languages,
        "adopted_languages": adopted_languages,
        "consistent_languages": consistent_languages,
        "complexity_trend": complexity_trend,
        "first_repo_date": first_repo.isoformat(),
        "latest_activity_date": latest_activity.isoformat(),
        "active_years": active_years,
    }


def analyze_repo_architecture(code_context: dict) -> dict:
    """Extract architectural signals from a repo's file structure."""
    structure = code_context.get("structure_sample") or []
    if not structure:
        return {"available": False}

    paths = [p.lower() for p in structure]

    patterns = {
        "monorepo": any("packages/" in p or "apps/" in p for p in paths),
        "frontend_backend_split": (
            any("frontend" in p for p in paths) and any("backend" in p for p in paths)
        ),
        "layered_architecture": (
            any("services/" in p for p in paths) and any("models/" in p for p in paths)
        ),
        "api_first": any(
            "api/" in p or "routes/" in p or "endpoints/" in p for p in paths
        ),
        "has_tests": any("test" in p or "spec" in p for p in paths),
        "has_migrations": any("migration" in p or "alembic" in p for p in paths),
        "has_ci": any(".github/workflows" in p or ".gitlab-ci" in p for p in paths),
        "has_docker": any("dockerfile" in p or "docker-compose" in p for p in paths),
        "has_docs": any(p.endswith(".md") and "readme" not in p for p in paths),
        "domain_driven": any("domain/" in p or "entities/" in p for p in paths),
    }

    framework_hints = []
    if any("fastapi" in p or "main.py" in p for p in paths):
        framework_hints.append("python_backend")
    if any("next.config" in p or "app/page.tsx" in p for p in paths):
        framework_hints.append("nextjs")
    if any("package.json" in p for p in paths):
        framework_hints.append("node")
    if any("pyproject.toml" in p or "requirements.txt" in p for p in paths):
        framework_hints.append("python")
    if any("cargo.toml" in p for p in paths):
        framework_hints.append("rust")
    if any("go.mod" in p for p in paths):
        framework_hints.append("go")

    return {
        "available": True,
        "patterns_detected": [k for k, v in patterns.items() if v],
        "framework_hints": framework_hints,
        "file_count": len(structure),
        "max_depth": max((p.count("/") for p in paths), default=0),
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
    selected_code_context_omissions: list[dict] | None = None,
    selected_code_context_total: int | None = None,
    rag_context: dict | None = None,
) -> dict:
    selected_repositories = [
        {
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "stars": repo.stars,
            "forks": repo.forks,
            "commit_count": repo.commit_count,
            "all_time_commit_count": getattr(repo, "all_time_commit_count", 0) or 0,
            "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
            "recent_commits": (getattr(repo, "raw", None) or {}).get("recent_commits", []) if isinstance(getattr(repo, "raw", None), dict) else [],
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
        "selected_repository_code_context_total": selected_code_context_total if selected_code_context_total is not None else len(selected_code_context or []),
        "selected_repository_code_context_omissions": selected_code_context_omissions or [],
        "rag_code_context": rag_context or {},
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
    if leetcode is not None:
        payload["leetcode"] = leetcode_signals(leetcode)
    payload["career_stage"] = infer_career_stage(payload, user.career_stage_override)
    payload["signal_completeness"] = assess_signal_completeness(payload)
    payload["temporal_signals"] = compute_temporal_signals(repositories)
    return payload


def code_hygiene_signals(selected_code_context: list[dict]) -> dict:
    paths: list[str] = []
    env_paths: list[str] = []
    generated_paths: list[str] = []
    for context in selected_code_context:
        paths.extend(str(path) for path in context.get("structure_sample") or [])
        for key_file in context.get("key_files") or []:
            path = str(key_file.get("path") or "")
            if path:
                paths.append(path)

    lower_paths = [path.lower() for path in paths]
    for path in paths:
        lower = path.lower()
        if ".env" in lower or "secret" in lower or "credentials" in lower:
            env_paths.append(path)
        if any(part in lower for part in ("node_modules/", "__pycache__/", ".next/", "dist/", "build/")):
            generated_paths.append(path)

    positives = []
    if any("test" in path or "spec" in path for path in lower_paths):
        positives.append("test files present")
    if any(".github/workflows" in path or ".gitlab-ci" in path for path in lower_paths):
        positives.append("CI workflow present")
    if any("dockerfile" in path or "docker-compose" in path for path in lower_paths):
        positives.append("containerization present")
    if any("migration" in path or "alembic" in path for path in lower_paths):
        positives.append("database migration structure present")
    if any(path.endswith((".toml", ".json", ".yaml", ".yml")) for path in lower_paths):
        positives.append("configuration files present")

    return {
        "available": bool(paths),
        "positive_signals": positives,
        "caution_signals": {
            "committed_env_or_secret_paths": sorted(set(env_paths))[:20],
            "generated_artifact_paths": sorted(set(generated_paths))[:20],
        },
        "files_observed": len(set(paths)),
    }


def delivery_signal_snapshot(payload: dict) -> dict:
    github = payload.get("github") if isinstance(payload.get("github"), dict) else {}
    selected = payload.get("selected_repositories_for_code_review") or []
    recent_activity = [
        {
            "repo": repo.get("full_name"),
            "pushed_at": repo.get("pushed_at"),
            "recent_commits": repo.get("recent_commits", [])[:5],
        }
        for repo in selected
    ]
    return {
        "total_commits": github.get("commits", 0),
        "repository_count": github.get("repository_count", len(selected)),
        "selected_repository_count": len(selected),
        "recency": (payload.get("signal_completeness") or {}).get("delivery", {}).get("recency", "unknown"),
        "recent_activity": recent_activity,
    }


def architecture_signal_snapshot(selected_code_context: list[dict]) -> list[dict]:
    snapshots = []
    for context in selected_code_context:
        if not context or "error" in context:
            continue
        architecture = context.get("architecture_signals") if isinstance(context.get("architecture_signals"), dict) else {}
        snapshots.append(
            {
                "repo": context.get("full_name", "unknown"),
                "patterns": architecture.get("patterns_detected", []),
                "framework_hints": architecture.get("framework_hints", []),
                "file_count": architecture.get("file_count", 0),
                "max_depth": architecture.get("max_depth", 0),
            }
        )
    return snapshots


def evidence_signal_snapshot(generated: dict, selected_code_context: list[dict]) -> dict:
    repository_evaluations = generated.get("repository_evaluations") if isinstance(generated, dict) else []
    cited_files = []
    for repo_eval in repository_evaluations or []:
        if isinstance(repo_eval, dict):
            cited_files.extend(repo_eval.get("specific_code_references") or [])

    observed_files = []
    for context in selected_code_context:
        for key_file in context.get("key_files") or []:
            path = key_file.get("path")
            if path:
                observed_files.append({"repo": context.get("full_name", "unknown"), "path": path})

    return {
        "cited_files": sorted({str(path) for path in cited_files if path})[:50],
        "observed_key_files": observed_files[:80],
        "highlights": generated.get("evidence_highlights", []) if isinstance(generated, dict) else [],
    }


def build_profile_signal_snapshot(
    user: User,
    repositories: list[GitHubRepository],
    sections: list[ProfileSection],
    leetcode: LeetCodeSnapshot | None,
    payload: dict,
    generated: dict,
    selected_code_context: list[dict],
) -> dict:
    skill_model = generated.get("skill_model") if isinstance(generated, dict) else {}
    languages = sorted({repo.language for repo in repositories if repo.language})
    manual_sections = [
        {
            "kind": section.kind,
            "title": section.title,
            "organization": section.organization,
            "start_date": section.start_date,
            "end_date": section.end_date,
        }
        for section in sections
    ]
    algorithms = {
        "source": (skill_model.get("algorithms") or {}).get("source") if isinstance(skill_model, dict) else None,
        "leetcode": leetcode_signals(leetcode) if leetcode is not None else None,
        "prose": (skill_model.get("algorithms") or {}).get("prose") if isinstance(skill_model, dict) else "",
    }
    summary_parts = [
        user.name or user.slug,
        user.headline or "",
        generated.get("summary", ""),
        generated.get("recruiter_copy", ""),
        "Languages: " + ", ".join(languages) if languages else "",
        "Strengths: " + "; ".join(generated.get("strengths") or []),
    ]

    rag_summary = rag_context_file_summary(payload.get("rag_code_context", {}))
    rag_summary["embedding_precompute"] = payload.get("rag_embedding_precompute", {})

    return {
        "version": 1,
        "profile": {"name": user.name, "slug": user.slug, "headline": user.headline},
        "career_stage": generated.get("career_stage"),
        "timeline": payload.get("temporal_signals", {}),
        "languages": languages,
        "manual_sections": manual_sections,
        "code_hygiene": code_hygiene_signals(selected_code_context),
        "architecture": architecture_signal_snapshot(selected_code_context),
        "delivery": delivery_signal_snapshot(payload),
        "algorithms": algorithms,
        "skill_model": skill_model,
        "signal_completeness": generated.get("signal_completeness"),
        "evidence": evidence_signal_snapshot(generated, selected_code_context),
        "rag": rag_summary,
        "recruiter": {
            "hiring_recommendation": generated.get("hiring_recommendation"),
            "role_fit": generated.get("role_fit", []),
            "manual_section_evaluations": generated.get("manual_section_evaluations", []),
            "interview_questions": generated.get("interview_questions", []),
            "recruiter_risks": generated.get("recruiter_risks", []),
        },
        "summary_for_search": "\n".join(part for part in summary_parts if part).strip(),
    }


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
        "temporal_signals": {
            "available": False,
            "evolution_narrative": "Temporal analysis unavailable in fallback mode.",
            "language_shifts": "",
            "complexity_trend": "unknown",
            "active_years": 0,
        },
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
            "Select up to twenty repositories so code quality can be reviewed from actual code context.",
        ],
        "evidence_highlights": [
            f"{github.get('repository_count', 0)} GitHub repositories synced.",
            f"{github.get('commits', 0)} total synced commits observed.",
        ],
        "hiring_recommendation": {
            "decision": "insufficient_evidence",
            "best_fit_level": "unknown",
            "best_fit_roles": [],
            "strongest_hiring_signal": "Generation unavailable in fallback mode.",
            "primary_verification_point": "Run analysis with an API key and reviewed source data.",
            "summary": "There is not enough generated evidence to make a recruiter recommendation.",
            "confidence": "low",
        },
        "role_fit": [],
        "manual_section_evaluations": [
            {
                "kind": section.get("kind", "unknown"),
                "title": section.get("title", "Untitled section"),
                "recruiter_value": "unclear",
                "evidence": [],
                "verification_points": ["Manual section was present but not evaluated in fallback mode."],
            }
            for section in payload.get("sections", [])
            if isinstance(section, dict)
        ],
        "interview_questions": [],
        "recruiter_risks": ["Full recruiter decision support is unavailable in fallback mode."],
        "recruiter_copy": "Evaluation unavailable in fallback mode.",
    }


def context_char_count(context: dict) -> int:
    total = len(context.get("readme") or "")
    total += sum(len(path) for path in context.get("structure_sample") or [])
    for key_file in context.get("key_files") or []:
        total += len(key_file.get("path") or "")
        total += len(key_file.get("content") or "")
    return total


def trim_text_for_prompt(value: str, max_chars: int) -> str:
    if not value or len(value) <= max_chars:
        return value or ""
    return value[:max_chars].rstrip() + "\n[truncated for prompt budget]"


def high_signal_file_rank(path: str) -> tuple[int, str]:
    lower = path.lower()
    name = lower.split("/")[-1]
    if name in {"package.json", "pyproject.toml", "requirements.txt", "dockerfile", "docker-compose.yml", "tsconfig.json", "next.config.ts"}:
        return (0, lower)
    if any(part in lower for part in ("/api/", "/routes/", "/services/", "/models/", "/schemas")):
        return (1, lower)
    if any(part in lower for part in ("/lib/", "/utils/", "/hooks/")):
        return (2, lower)
    if any(part in lower for part in ("/components/", "/pages/", "/app/")):
        return (3, lower)
    if any(part in lower for part in ("/tests/", "/test_", ".test.", ".spec.")):
        return (4, lower)
    if lower.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".cs", ".rb", ".php")):
        return (5, lower)
    return (6, lower)


def compact_code_context_for_prompt(context: dict, max_key_files: int = HIGH_SIGNAL_FILES_PER_REPO) -> dict:
    compacted = dict(context)
    compacted["readme"] = trim_text_for_prompt(str(context.get("readme") or ""), MAX_PROMPT_README_CHARS)

    ranked_files = []
    for index, key_file in enumerate(context.get("key_files") or []):
        path = str(key_file.get("path") or "")
        content = str(key_file.get("content") or "")
        if not path or not content:
            continue
        if path.lower().endswith("readme.md"):
            continue
        ranked_files.append((high_signal_file_rank(path), index, path, content))

    compacted["key_files"] = [
        {
            "path": path,
            "content": trim_text_for_prompt(content, MAX_PROMPT_FILE_CHARS),
        }
        for _, _, path, content in sorted(ranked_files)[:max_key_files]
    ]
    compacted["prompt_sampling_strategy"] = (
        f"Embedding fallback/code context mode: include README plus up to {max_key_files} high-signal files "
        "per selected repository, prioritizing config, API/routes/services/models/schemas, shared libraries, UI, and tests."
    )
    return compacted


def repo_priority(selected_repositories: list[GitHubRepository]) -> dict[str, tuple[int, str]]:
    priority = {}
    for repo in selected_repositories:
        pushed_at = repo.pushed_at.isoformat() if getattr(repo, "pushed_at", None) else ""
        priority[repo.full_name] = (int(getattr(repo, "commit_count", 0) or 0), pushed_at)
    return priority


def limit_code_context_for_prompt(
    selected_repositories: list[GitHubRepository],
    selected_code_context: list[dict],
    max_repos: int,
    max_chars: int,
) -> tuple[list[dict], list[dict]]:
    priorities = repo_priority(selected_repositories)
    ordered = sorted(
        selected_code_context,
        key=lambda context: priorities.get(context.get("full_name", ""), (0, "")),
        reverse=True,
    )

    included: list[dict] = []
    omissions: list[dict] = []
    used_chars = 0
    for context in ordered:
        full_name = context.get("full_name", "unknown")
        compacted = compact_code_context_for_prompt(context)
        char_count = context_char_count(compacted)
        if len(included) >= max_repos:
            omissions.append({"full_name": full_name, "reason": "repo_limit", "char_count": char_count})
            continue
        if used_chars + char_count > max_chars:
            omissions.append({"full_name": full_name, "reason": "char_budget", "char_count": char_count})
            continue
        included.append(compacted)
        used_chars += char_count

    return included, omissions


def trim_rag_context(rag_context: dict, top_k_per_dimension: int) -> dict:
    return {
        dimension: list(chunks or [])[:top_k_per_dimension]
        for dimension, chunks in (rag_context or {}).items()
    }


def rag_context_file_summary(rag_context: dict) -> dict:
    dimensions = {}
    files = set()
    chunk_count = 0
    for dimension, chunks in (rag_context or {}).items():
        dimension_files = []
        for chunk in chunks or []:
            if not isinstance(chunk, dict):
                continue
            chunk_count += 1
            repo = chunk.get("repo") or chunk.get("repo_id") or "unknown"
            path = chunk.get("file_path") or "unknown"
            label = f"{repo}:{path}"
            files.add(label)
            if label not in dimension_files:
                dimension_files.append(label)
        dimensions[dimension] = dimension_files
    return {"chunk_count": chunk_count, "file_count": len(files), "files_by_dimension": dimensions}


def embedding_status_for_selected_repos(db: Session, user_id: str, selected_repositories: list[GitHubRepository]) -> dict:
    indexed = []
    missing = []
    for repo in selected_repositories:
        if repo_has_embeddings(db, user_id, repo.id):
            indexed.append({"repo": repo.full_name})
            continue
        missing.append({"repo": repo.full_name, "reason": "not_indexed"})
    return {
        "attempted": [],
        "indexed": indexed,
        "missing": missing,
        "skipped": missing,
        "chunks_pending": 0,
        "chunks_stored": 0,
        "errors": [],
        "mode": "read_existing_only",
    }


def build_existing_rag_context(db: Session, user_id: str, selected_repositories: list[GitHubRepository]) -> tuple[dict, dict]:
    embedding_status = embedding_status_for_selected_repos(db, user_id, selected_repositories)
    if not embedding_status["indexed"]:
        return {}, embedding_status

    repo_id_to_full_name = {
        repo.id: repo.full_name
        for repo in selected_repositories
        if any(item["repo"] == repo.full_name for item in embedding_status["indexed"])
    }
    try:
        rag_context = build_rag_context(
            db=db,
            user_id=user_id,
            repo_id_to_full_name=repo_id_to_full_name,
            top_k_per_query=MAX_RAG_CHUNKS_PER_DIMENSION,
        )
    except Exception as exc:
        logger.warning("RAG retrieval failed during analysis; using file fallback: %s", exc)
        embedding_status["errors"].append({"message": str(exc)[:500]})
        return {}, embedding_status
    return rag_context, embedding_status


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
        if not isinstance(repo, dict):
            continue
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


ANTHROPIC_TOOL_NAME = "submit_evaluation"


def extract_anthropic_tool_input(response, tool_name: str) -> dict:
    content = getattr(response, "content", None) or []
    for block in content:
        block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", "")
        if block_type != "tool_use":
            continue
        name = block.get("name") if isinstance(block, dict) else getattr(block, "name", "")
        if name != tool_name:
            continue
        tool_input = block.get("input") if isinstance(block, dict) else getattr(block, "input", None)
        if isinstance(tool_input, dict):
            return tool_input
    raise ValueError(f"Anthropic response missing tool_use block for {tool_name}")


def generate_with_anthropic(payload: dict) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return fallback_analysis(payload)

    client = Anthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_evaluation_input(payload)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": EVALUATION_INSTRUCTIONS,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[
            {
                "name": ANTHROPIC_TOOL_NAME,
                "description": "Submit the structured developer evaluation matching the required schema.",
                "input_schema": ANALYSIS_SCHEMA,
            }
        ],
        tool_choice={"type": "tool", "name": ANTHROPIC_TOOL_NAME},
        messages=[{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
    )
    return extract_anthropic_tool_input(response, ANTHROPIC_TOOL_NAME)


def generate_analysis(payload: dict) -> dict:
    settings = get_settings()
    provider: Literal["openai", "anthropic"] = settings.analysis_provider
    if provider == "anthropic":
        return normalize_generated_analysis(generate_with_anthropic(payload))
    return normalize_generated_analysis(generate_with_openai(payload))


def run_analysis(db: Session, user: User, evaluation: GeneratedEvaluation) -> GeneratedEvaluation:
    evaluation.status = AnalysisStatus.running
    evaluation.updated_at = datetime.utcnow()
    db.commit()

    try:
        repositories = db.query(GitHubRepository).filter(GitHubRepository.user_id == user.id).all()
        selected_repositories = [repo for repo in repositories if repo.selected_for_analysis][:20]
        selected_code_context = []
        for repo in selected_repositories:
            context = repo.code_analysis_snapshot if isinstance(repo.code_analysis_snapshot, dict) else None
            if context:
                selected_code_context.append(context)
            else:
                selected_code_context.append({"full_name": repo.full_name, "error": "Code context has not been synced yet"})

        # Attach architecture signals to each successful code context
        for context in selected_code_context:
            if not context or "error" in context:
                continue
            try:
                context["architecture_signals"] = analyze_repo_architecture(context)
            except Exception as exc:
                logger.warning("Architecture analysis failed for %s: %s", context.get("full_name"), exc)

        prompt_code_context, prompt_omissions = limit_code_context_for_prompt(
            selected_repositories,
            [context for context in selected_code_context if "error" not in context],
            max_repos=MAX_PROMPT_CODE_CONTEXT_REPOS,
            max_chars=MAX_PROMPT_CODE_CONTEXT_CHARS,
        )
        rag_context, embedding_precompute = build_existing_rag_context(db, user.id, selected_repositories)
        leetcode = (
            db.query(LeetCodeSnapshot)
            .filter(LeetCodeSnapshot.user_id == user.id)
            .order_by(LeetCodeSnapshot.created_at.desc())
            .first()
        )
        sections = db.query(ProfileSection).filter(ProfileSection.user_id == user.id).order_by(ProfileSection.order).all()
        payload = build_analysis_payload(
            user,
            repositories,
            leetcode,
            sections,
            prompt_code_context,
            prompt_omissions,
            selected_code_context_total=len([context for context in selected_code_context if "error" not in context]),
            rag_context=rag_context,
        )
        payload["rag_embedding_precompute"] = embedding_precompute
        snapshot_payload = payload

        try:
            generated = generate_analysis(payload)
        except Exception:
            retry_context, retry_omissions = limit_code_context_for_prompt(
                selected_repositories,
                [context for context in selected_code_context if "error" not in context],
                max_repos=RETRY_PROMPT_CODE_CONTEXT_REPOS,
                max_chars=RETRY_PROMPT_CODE_CONTEXT_CHARS,
            )
            retry_payload = build_analysis_payload(
                user,
                repositories,
                leetcode,
                sections,
                retry_context,
                retry_omissions,
                selected_code_context_total=len([context for context in selected_code_context if "error" not in context]),
                rag_context=trim_rag_context(rag_context, RETRY_RAG_CHUNKS_PER_DIMENSION),
            )
            retry_payload["rag_embedding_precompute"] = embedding_precompute
            snapshot_payload = retry_payload
            generated = generate_analysis(retry_payload)

        evaluation.status = AnalysisStatus.ready
        evaluation.summary = generated["summary"]
        evaluation.skill_model_v2 = generated["skill_model"]
        evaluation.skill_model = legacy_skill_model(generated["skill_model"])
        evaluation.career_stage = generated["career_stage"]
        evaluation.signal_completeness = generated["signal_completeness"]
        repository_evaluations = generated.get("repository_evaluations") or []
        strengths = generated.get("strengths") or []
        growth_areas = generated.get("growth_areas") or []
        evidence_highlights = generated.get("evidence_highlights") or []
        recruiter_copy = generated.get("recruiter_copy") or ""
        evaluation.profile_signal_snapshot = build_profile_signal_snapshot(
            user=user,
            repositories=repositories,
            sections=sections,
            leetcode=leetcode,
            payload=snapshot_payload,
            generated=generated,
            selected_code_context=[context for context in selected_code_context if "error" not in context],
        )
        evaluation.repository_evaluations = repository_evaluations
        evaluation.strengths = strengths
        evaluation.growth_areas = growth_areas
        evaluation.project_complexity_notes = legacy_project_complexity_notes(repository_evaluations)
        evaluation.evidence_highlights = evidence_highlights
        evaluation.recruiter_copy = recruiter_copy
        evaluation.error = None
    except Exception as exc:  # pragma: no cover - exercised by integration tests with service mocks
        evaluation.status = AnalysisStatus.failed
        evaluation.error = str(exc)

    evaluation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(evaluation)

    if evaluation.status == AnalysisStatus.ready:
        try:
            upsert_profile_embedding(db, user, evaluation, repositories)
        except Exception as exc:
            db.rollback()
            logger.warning("Profile embedding upsert failed for user %s: %s", user.id, exc)

    return evaluation
