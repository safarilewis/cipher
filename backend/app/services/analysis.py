import json
from datetime import datetime

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AnalysisStatus, GeneratedEvaluation, GitHubRepository, LeetCodeSnapshot, ProfileSection, User
from app.services.github import fetch_repo_code_context, get_github_access_token
from app.services.scoring import github_quality_signals, leetcode_signals, profile_signals


ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "skill_model": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "code_quality": {"type": "string"},
                "delivery": {"type": "string"},
                "algorithms": {"type": "string"},
            },
            "required": ["code_quality", "delivery", "algorithms"],
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "growth_areas": {"type": "array", "items": {"type": "string"}},
        "project_complexity_notes": {"type": "array", "items": {"type": "string"}},
        "evidence_highlights": {"type": "array", "items": {"type": "string"}},
        "recruiter_copy": {"type": "string"},
    },
    "required": [
        "summary",
        "skill_model",
        "strengths",
        "growth_areas",
        "project_complexity_notes",
        "evidence_highlights",
        "recruiter_copy",
    ],
}

EVALUATION_INSTRUCTIONS = """
You are adpt's developer evidence evaluator. adpt replaces resumes with a profile built from connected source data.

Your job:
- Build a sober, recruiter-readable developer model from the payload.
- Prefer evidence over polish. Every claim should be traceable to GitHub, LeetCode, or user-entered profile sections.
- Evaluate actual selected repository code when selected_repository_code_context is present.
- Identify uncertainty plainly instead of filling gaps with generic praise.

Evidence priorities:
1. Selected repository code context: source snippets, README, project structure, package/config files, and sampling notes.
2. GitHub repository metadata: languages, commit counts, recency, stars, forks, repository count, and selected repo metadata.
3. LeetCode snapshot: solved counts, difficulty distribution, rank, and contest-like signal when available.
4. Manual profile sections: employment, education, bootcamps, certifications, projects, and described outcomes.

Repository code review rules:
- For selected repos, explicitly assess code organization, maintainability, architectural clarity, testability, dependency choices, and project maturity.
- If only README/structure/key files are available, say the code review is sampled and base conclusions only on the provided sample.
- For large repos, use structure_sample, README, package/config files, and key_files as the evidence set.
- Mention concrete file paths or repository names in evidence_highlights or project_complexity_notes when useful.
- Do not claim production quality, security quality, test coverage, or scalability unless the payload contains direct evidence.

GitHub interpretation rules:
- Commit count is activity evidence, not quality evidence by itself.
- Stars/forks are weak external validation, not proof of skill.
- Language diversity can indicate breadth, but avoid treating it as mastery without code or project evidence.
- Recency and active projects matter for delivery signal.

LeetCode interpretation rules:
- Use solved counts and difficulty distribution for algorithms/problem-solving signal.
- Avoid ranking candidates against other developers unless ranking data is present.
- Do not overvalue easy-only progress; distinguish breadth from hard-problem depth.

Manual profile rules:
- Treat user-entered sections as claimed experience unless supported by connected evidence.
- Use employment, bootcamps, certifications, and projects to add context, not to invent capability claims.

Output quality:
- summary: 2-4 sentences, balanced and evidence-backed.
- skill_model.code_quality: focus on actual code evidence when available; otherwise state the evidence gap.
- skill_model.delivery: focus on commits, recency, repo activity, project completion signals, and profile sections.
- skill_model.algorithms: focus on LeetCode evidence only.
- strengths: 3-5 concise bullets, each grounded in evidence.
- growth_areas: 2-4 constructive bullets that help the user improve the profile or engineering signal.
- project_complexity_notes: 3-5 bullets about selected repos, architecture, scope, README/structure, dependencies, or maturity.
- evidence_highlights: 4-7 bullets with concrete numbers, repo names, file paths, or section titles from the payload.
- recruiter_copy: one polished paragraph, honest and not hype-driven.

Hard guardrails:
- Never invent degrees, jobs, certifications, employers, technologies, metrics, outcomes, test coverage, security posture, or production usage.
- Never use empty resume filler such as "passionate", "rockstar", "ninja", or "proven track record" unless directly evidenced.
- If source data is missing, say what is missing and what would strengthen the signal.
- Return only a JSON object that matches the provided schema.
""".strip()


def build_evaluation_input(payload: dict) -> str:
    return (
        "Evaluate this developer evidence for an adpt profile. "
        "Use the instructions as the rubric and return JSON matching the schema.\n\n"
        f"Developer evidence payload:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def build_analysis_payload(
    user: User,
    repositories: list[GitHubRepository],
    leetcode: LeetCodeSnapshot | None,
    sections: list[ProfileSection],
    selected_code_context: list[dict] | None = None,
) -> dict:
    return {
        "profile": {"name": user.name, "headline": user.headline},
        "github": github_quality_signals(repositories),
        "selected_repositories_for_code_review": [
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
        ],
        "selected_repository_code_context": selected_code_context or [],
        "leetcode": leetcode_signals(leetcode),
        "sections": [
            {
                "kind": section.kind,
                "title": section.title,
                "organization": section.organization,
                "description": section.description,
            }
            for section in sections
        ],
        "manual_profile": profile_signals(sections),
    }


def fallback_analysis(payload: dict) -> dict:
    github = payload["github"]
    leetcode = payload["leetcode"]
    languages = ", ".join(github.get("languages") or ["their active stack"])
    solved = leetcode.get("total_solved", 0) if leetcode.get("available") else 0
    selected = payload.get("selected_repositories_for_code_review", [])
    code_context = payload.get("selected_repository_code_context", [])
    selected_names = [repo.get("full_name") for repo in selected if repo.get("full_name")]
    selected_label = ", ".join(selected_names[:3]) if selected_names else "no selected repositories"
    selected_commit_count = sum(repo.get("commit_count", 0) for repo in selected)
    return {
        "summary": (
            f"This profile currently shows {github['project_complexity']} GitHub project maturity across "
            f"{github['repository_count']} repositories, with visible work in {languages}. "
            f"The strongest code-review evidence is from {selected_label}."
        ),
        "skill_model": {
            "code_quality": (
                f"Sampled code context was collected for {len(code_context)} selected repositories; review should focus on structure, README, and key files."
                if code_context
                else "No repository code samples were selected yet, so code quality cannot be evaluated beyond metadata."
            ),
            "delivery": (
                f"Delivery signal is estimated from {github['commits']} total synced commits, "
                f"{github['active_projects']} active projects, and {payload['manual_profile']['total_sections']} profile sections."
            ),
            "algorithms": f"{solved} LeetCode problems solved." if solved else "No LeetCode data connected yet.",
        },
        "strengths": [
            f"Maintains {github['repository_count']} synced GitHub repositories.",
            f"Shows activity across {github['language_count']} detected languages.",
            "Combines connected source data with user-entered profile evidence.",
        ],
        "growth_areas": [
            "Select up to five repositories for deeper sampled code review.",
            "Add project outcomes, constraints, and technical decisions to manual profile sections.",
            "Refresh coding challenge data after major LeetCode milestones.",
        ],
        "project_complexity_notes": [
            f"Current complexity signal is {github['project_complexity']} based on repositories, stars, forks, language spread, and activity.",
            f"Selected repositories account for {selected_commit_count} synced commits.",
            "Without full repository checkout, large-repo conclusions should remain tied to sampled structure, README, and key files.",
        ],
        "evidence_highlights": [
            f"{github['repository_count']} GitHub repositories analyzed.",
            f"{github['stars']} total GitHub stars observed.",
            f"{github['commits']} total synced commits observed.",
            f"{selected_commit_count} commits across selected repositories.",
            f"{solved} LeetCode problems solved." if solved else "LeetCode source has not contributed solved-count evidence yet.",
        ],
        "recruiter_copy": (
            "This adpt profile presents a developer signal backed by connected GitHub activity, "
            "coding challenge progress where available, and reviewed career evidence. "
            "The profile should be read as evidence-backed and strongest where source data is connected."
        ),
    }


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
        evaluation.skill_model = generated["skill_model"]
        evaluation.strengths = generated["strengths"]
        evaluation.growth_areas = generated["growth_areas"]
        evaluation.project_complexity_notes = generated["project_complexity_notes"]
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
