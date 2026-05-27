import json
import re
from datetime import datetime, timedelta
from typing import Literal

from anthropic import Anthropic
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AnalysisStatus, GeneratedEvaluation, GitHubRepository, LeetCodeSnapshot, ProfileSection, User
from app.services.github import fetch_repo_code_context, get_github_access_token
from app.services.scoring import github_quality_signals, leetcode_signals, profile_signals
from app.services.embeddings import embed_repo_files, build_rag_context
import logging

logger = logging.getLogger(__name__)


CAREER_STAGES = {"student", "new_grad", "early", "mid", "senior"}
CONFIDENCE_LEVELS = ["high", "medium", "low"]
OVERALL_SCORE_WEIGHTS = {"code_quality": 0.50, "delivery": 0.35, "algorithms": 0.15}
MAX_PROMPT_CODE_CONTEXT_REPOS = 10
MAX_PROMPT_CODE_CONTEXT_CHARS = 220000
RETRY_PROMPT_CODE_CONTEXT_REPOS = 6
RETRY_PROMPT_CODE_CONTEXT_CHARS = 120000


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
    skill_model = generated.get("skill_model")
    if not isinstance(skill_model, dict):
        return generated

    normalized = dict(generated)
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
        "recruiter_copy",
    ],
}

EVALUATION_INSTRUCTIONS = """
ROLE
You are a senior engineering evaluator producing structured developer assessments for cipher. Your evaluations are read by developers who want honest feedback and by recruiters who need accurate signal. You are not a marketer.

CARDINAL RULES
- Every claim must trace to a specific source: a repo name, a file path, a LeetCode stat, or a profile section. No invented evidence.
- Do not use: "passionate", "rockstar", "ninja", "proven track record", "strong communicator", or any filler that carries no information.
- If evidence is missing, say what is missing and what it would change. Missing evidence is not a failing grade; it is an honest gap.
- Null scores mean insufficient evidence. Never return 0 when data is absent. 0 is a measurement. null is an absence of measurement.

EVALUATION WORKFLOW
- First identify the strongest evidence available for each dimension: code context for code quality, activity plus completed work for delivery, and repo DSA or LeetCode for algorithms.
- Then judge whether the signal is strong, mixed, weak, or absent. Weak signal should lower scores instead of being averaged away.
- If the prompt contains noisy or generated artifacts, ignore them unless they are part of a specific engineering choice worth noting.
- If the repo is mostly scaffolding, lockfiles, cache directories, generated code, or empty shells, treat that as weak signal and say so explicitly.

EVIDENCE HIERARCHY
- Highest: actual code context, architecture, tests, file structure, and repo-specific implementation details.
- Medium: repository metadata such as descriptions, language, stars, forks, and commit history.
- Lower: LeetCode and other external practice stats, which should support but not dominate the evaluation.
- Lowest: noisy paths, generated files, cache folders, and dependency artifacts.

CAREER STAGE CONTEXT
Read the career_stage object before writing anything. Your framing depends on it.
- student/new_grad: evaluate relative to peers at this stage, not working engineers. Coursework repos are valid learning evidence. Do not penalize expected lack of production experience. Recruiter copy should fit internship or new grad roles.
- early: some production experience may be expected. Evaluate transition from coursework/projects toward real systems.
- mid/senior: full engineering bar applies. Production quality, architecture decisions, and scale signal matter.

COURSEWORK REPO POLICY
Coursework-looking repositories are learning evidence. Assess code cleanliness, concept understanding, whether the developer went beyond minimum assignment work, and progression across repos. Do not penalize coursework repos for lacking production architecture.

ALGORITHMS SIGNAL POLICY
LeetCode is only a supporting signal. Repo evidence, code context, and project quality should dominate the algorithms assessment, especially when LeetCode is absent, weak, or generic.
If LeetCode is absent or weak, scan selected repository names, descriptions, README text, structure, and key files for DSA evidence such as graph/tree/heap/dp/trie/sort/bfs/dfs, algorithms directories, competitive programming, Advent of Code, CS coursework, complexity notes, or custom algorithm implementations.
If repo-based DSA evidence exists, set algorithms.source to "repo_evidence" or "both", score from that evidence, and cite it. Do not over-reward LeetCode-only signal when repo evidence is thin or absent.
If no algorithms signal exists, set algorithms.score to null, algorithms.source to "insufficient", and explain that no algorithms signal was found in LeetCode or repositories.

NEGATIVE SIGNAL POLICY
- Do not materially penalize general repo hygiene issues such as build artifacts, cache directories, generated files, or dependency folders. Treat them as neutral unless they are directly relevant to a code quality observation.
- Only committed env/secrets files should be treated as hygiene warnings, and those warnings should be narrow and specific.
- If committed env files exist, mention them as a caution flag; do not let them dominate the score unless they are the clearest evidence in the repo.

CODE QUALITY SCORING
Only score code_quality when selected_repository_code_context is non-empty. With metadata only, set score = null and note the gap. When code context exists, assess organization, naming/readability, architectural clarity, dependency choices, testability signals, README/config completeness, and project maturity.
Return one repository_evaluation object per repository with code context. If no code context is available, return an empty array.
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

RAG CONTEXT POLICY
- rag_context provides dimension-specific code chunks via semantic search.
- rag_context.architecture / code_quality / algorithms / tests each hold the top retrieved chunks.
- Cite specific files from rag_context in repository_evaluations and skill_model prose. RAG chunks are higher-priority evidence than structure_sample paths.
- If rag_context for a dimension is empty, fall back to selected_repository_code_context, but note the gap in confidence.

DEEPER CODE REASONING
- code_quality_notes and architecture_notes must cite specific files or patterns — not generic praise.
- Weak (AVOID): "Clean code structure", "Good separation of concerns."
- Strong (PREFER): "auth.py uses JWT with bcrypt password hashing; main.py wires FastAPI with dependency injection."
- Populate specific_code_references with the file paths cited.
- One concrete architectural choice per repo in architecture_notes. Skip if not concrete.

SCORING HEURISTICS
- algorithms: strong LeetCode plus repo DSA -> 80-95; strong LeetCode alone -> 60-75; moderate LeetCode plus strong repo DSA -> 65-80; repo-only strong DSA -> 80-90; weak/minor signal -> 25-45; no signal -> null.
- code_quality: clean architecture with code context -> 70-100; mixed quality -> 40-70; unclear structure -> 20-40; poor architecture, weak projects, or generated-artifact-heavy repos should drop below the middle band; metadata only -> null.
- code_quality: clean architecture with code context -> 70-100; mixed quality -> 40-70; unclear structure -> 20-40; metadata only -> null.
- delivery: active commits under 90 days plus multiple projects/completions -> 70-100; 3+ end-to-end systems should not score below 78; moderate activity -> 40-70; low/dormant -> 20-40; no commit data -> null.
- overall: weighted average of non-null dimensions: code_quality 0.45, delivery 0.40, algorithms 0.15. If fewer than two dimensions have scores, overall.score = null.

SCORING ANCHORS
- Treat architecture problems as first-class issues: missing boundaries, ad hoc coupling, lack of tests, or weak separation of concerns should lower code_quality even if the repo has many files.
- Treat polished boilerplate or auto-generated structure as low signal unless the developer made clear engineering choices on top of it.
- Treat LeetCode as evidence of algorithm practice, not system design, code quality, or product maturity.
- Treat strong repo-based DSA as a top-tier algorithms signal even when LeetCode is absent; that should commonly land in the 80s when the repo evidence is clear and specific.
- Treat 3 or more end-to-end systems as a strong delivery signal; delivery.score should be floored at 78 when that evidence is present.
- Treat live, deployed, actively maintained, or otherwise production-shaped projects as system-tier repositories.
- Treat commit count as activity only; do not assume strong delivery from raw commit volume if the work is repetitive, generated, or trivial.

OUTPUT REQUIREMENTS
- summary: 2-4 evidence-backed sentences calibrated to career stage. Do not open with the developer's name.
- skill_model.code_quality.prose: specific code observations when available, otherwise state the code-review gap.
- skill_model.delivery.prose: commit cadence, recency, repo activity, and completion signals. For students, frame as learning consistency.
- skill_model.algorithms.prose: LeetCode plus repo DSA evidence, with source stated explicitly.
- strengths: 3-5 bullets; each must cite a concrete source.
- growth_areas: 2-4 constructive bullets. For students, do not list lack of production experience as a weakness.
- repository_evaluations: one object per repository with code context; empty array when no code context exists.
- evidence_highlights: 4-7 concrete facts with numbers, repo names, file paths, or section titles, each using APA-like parenthetical in-text citations such as `(repo-name, path/to/file.py)` or `(leetcode, 213 solved)`.
- recruiter_copy: one honest polished paragraph, calibrated to career stage, that also includes a clear recommendation to the recruiter about the candidate's technical ability and the kinds of roles they should be considered for.

HUMAN-READABLE ANALYSIS & COMPETENCE RANKING (required)
- Provide a clear, human-readable analysis paragraph intended for the recruiter as the first part of `recruiter_copy`. This should be 3-6 plain-language sentences summarizing the candidate's strengths, most important growth areas, and an overall takeaway — avoid JSON or list markup inside this paragraph. Include an explicit recruiter recommendation sentence that names the technical ability level and the roles they should be considered for.
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


def compute_temporal_signals(repositories: list[GitHubRepository]) -> dict:
    """Extract evolution signals across the developer's repo history."""
    repos_with_dates = [r for r in repositories if getattr(r, "created_at", None)]
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

    sorted_repos = sorted(repos_with_dates, key=lambda r: r.created_at)

    language_timeline = [
        {
            "date": repo.created_at.isoformat(),
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
        date = getattr(repo, "pushed_at", None) or repo.created_at
        if lang not in lang_first_seen:
            lang_first_seen[lang] = repo.created_at
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

    first_repo = sorted_repos[0].created_at
    latest_activity = max((getattr(r, "pushed_at", None) or r.created_at) for r in sorted_repos)
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
        "rag_context": rag_context or {},
    }
    payload["career_stage"] = infer_career_stage(payload, user.career_stage_override)
    payload["signal_completeness"] = assess_signal_completeness(payload)
    payload["temporal_signals"] = compute_temporal_signals(repositories)
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
        "recruiter_copy": "Evaluation unavailable in fallback mode.",
    }


def context_char_count(context: dict) -> int:
    total = len(context.get("readme") or "")
    total += sum(len(path) for path in context.get("structure_sample") or [])
    for key_file in context.get("key_files") or []:
        total += len(key_file.get("path") or "")
        total += len(key_file.get("content") or "")
    return total


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
        char_count = context_char_count(context)
        if len(included) >= max_repos:
            omissions.append({"full_name": full_name, "reason": "repo_limit", "char_count": char_count})
            continue
        if used_chars + char_count > max_chars:
            omissions.append({"full_name": full_name, "reason": "char_budget", "char_count": char_count})
            continue
        included.append(context)
        used_chars += char_count

    return included, omissions


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


def extract_json_response(text: str) -> dict:
    cleaned_text = text.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
    return json.loads(cleaned_text)


def extract_anthropic_text(response) -> str:
    response_text = getattr(response, "text", None)
    if isinstance(response_text, str) and response_text.strip():
        return response_text

    content = getattr(response, "content", None) or []
    text_blocks = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                text_blocks.append(str(block.get("text", "")))
            continue
        if getattr(block, "type", "") == "text":
            text_blocks.append(str(getattr(block, "text", "")))
    return "".join(text_blocks)


def generate_with_anthropic(payload: dict) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return fallback_analysis(payload)

    client = Anthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_evaluation_input(payload)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=EVALUATION_INSTRUCTIONS,
        messages=[{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
    )
    text_content = extract_anthropic_text(response)
    return extract_json_response(text_content)


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
        access_token = get_github_access_token(db, user)
        selected_code_context = []
        for repo in selected_repositories:
            try:
                context = fetch_repo_code_context(repo.full_name, access_token)
                repo.code_analysis_snapshot = context
                selected_code_context.append(context)
            except Exception as exc:
                selected_code_context.append({"full_name": repo.full_name, "error": str(exc)})

        # Attach architecture signals to each successful code context
        for context in selected_code_context:
            if not context or "error" in context:
                continue
            try:
                context["architecture_signals"] = analyze_repo_architecture(context)
            except Exception as exc:
                logger.warning("Architecture analysis failed for %s: %s", context.get("full_name"), exc)

        # Embed code context asynchronously-friendly: schedule or run embedding in batches.
        # For now, attempt to embed synchronously but guard against failures so analysis continues.
        # Enqueue embedding jobs instead of running them inline when Redis is configured.
        redis_url = getattr(get_settings(), "redis_url", None)
        if redis_url:
            try:
                from redis import Redis
                from rq import Queue

                redis_conn = Redis.from_url(redis_url)
                q = Queue("embeddings", connection=redis_conn)
                for repo, context in zip(selected_repositories, selected_code_context):
                    if not context or "error" in context:
                        continue
                    q.enqueue("app.workers.embeddings_worker.enqueue_embedding_job", user.id, repo.id, evaluation.id, context)
            except Exception:
                logger.exception("Failed to enqueue embedding jobs; falling back to inline embedding")
                # fallback to inline embedding
                for repo, context in zip(selected_repositories, selected_code_context):
                    if not context or "error" in context:
                        continue
                    try:
                        embed_repo_files(db=db, user_id=user.id, repo_id=repo.id, analysis_id=evaluation.id, code_context=context)
                    except Exception as exc:  # don't block analysis on embedding errors
                        logger.warning("Embedding failed for %s: %s", repo.full_name, exc)
        else:
            # No Redis configured: run inline but guard against exceptions
            for repo, context in zip(selected_repositories, selected_code_context):
                if not context or "error" in context:
                    continue
                try:
                    embed_repo_files(db=db, user_id=user.id, repo_id=repo.id, analysis_id=evaluation.id, code_context=context)
                except Exception as exc:  # don't block analysis on embedding errors
                    logger.warning("Embedding failed for %s: %s", repo.full_name, exc)

        # Build rag_context from stored chunks (if any)
        repo_id_to_name = {repo.id: repo.full_name for repo in selected_repositories}
        try:
            rag_context = build_rag_context(db=db, user_id=user.id, analysis_id=evaluation.id, repo_id_to_full_name=repo_id_to_name)
        except Exception as exc:
            logger.warning("Failed to build rag_context: %s", exc)
            rag_context = {}

        prompt_code_context, prompt_omissions = limit_code_context_for_prompt(
            selected_repositories,
            [context for context in selected_code_context if "error" not in context],
            max_repos=MAX_PROMPT_CODE_CONTEXT_REPOS,
            max_chars=MAX_PROMPT_CODE_CONTEXT_CHARS,
        )
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
                rag_context=rag_context,
            )
            generated = generate_analysis(retry_payload)

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
