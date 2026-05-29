import json

from openai import OpenAI

from app.core.config import get_settings
from app.models import GeneratedEvaluation, GitHubRepository, LeetCodeSnapshot, ProfileSection, User


PROFILE_QUESTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "recommendation": {"type": "string", "enum": ["recommend", "consider", "hold", "insufficient_evidence"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "verification_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "recommendation", "confidence", "evidence", "verification_questions"],
}


PROFILE_QUESTION_INSTRUCTIONS = """
You answer recruiter questions about a public developer profile.

Rules:
- Answer only from the supplied profile evidence.
- If the recruiter asks whether the applicant is qualified for a role, give a direct recommendation:
  recommend, consider, hold, or insufficient_evidence.
- Cite concrete evidence from the analysis, role fit, manual sections, repositories, LeetCode data, or recruiter risks.
- Be fair: distinguish observed evidence from interpretation.
- Include verification questions the recruiter can ask in a screen or interview.
- Do not invent employment history, production experience, credentials, or role fit.
Return only JSON matching the schema.
""".strip()


def profile_question_payload(
    user: User,
    sections: list[ProfileSection],
    repositories: list[GitHubRepository],
    leetcode: LeetCodeSnapshot | None,
    evaluation: GeneratedEvaluation | None,
) -> dict:
    profile_signal = evaluation.profile_signal_snapshot if evaluation and isinstance(evaluation.profile_signal_snapshot, dict) else {}
    return {
        "profile": {
            "name": user.name,
            "slug": user.slug,
            "headline": user.headline,
        },
        "manual_sections": [
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
        "repositories": [
            {
                "full_name": repo.full_name,
                "description": repo.description,
                "language": repo.language,
                "stars": repo.stars,
                "forks": repo.forks,
                "commit_count": repo.commit_count,
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "selected_for_analysis": repo.selected_for_analysis,
            }
            for repo in repositories
        ],
        "leetcode": {
            "total_solved": leetcode.total_solved,
            "easy_solved": leetcode.easy_solved,
            "medium_solved": leetcode.medium_solved,
            "hard_solved": leetcode.hard_solved,
            "ranking": leetcode.ranking,
        }
        if leetcode
        else None,
        "analysis": {
            "summary": evaluation.summary if evaluation else None,
            "skill_model": evaluation.skill_model_v2 if evaluation else None,
            "career_stage": evaluation.career_stage if evaluation else None,
            "signal_completeness": evaluation.signal_completeness if evaluation else None,
            "repository_evaluations": evaluation.repository_evaluations if evaluation else None,
            "strengths": evaluation.strengths if evaluation else None,
            "growth_areas": evaluation.growth_areas if evaluation else None,
            "evidence_highlights": evaluation.evidence_highlights if evaluation else None,
            "recruiter_copy": evaluation.recruiter_copy if evaluation else None,
            "recruiter_signal": profile_signal.get("recruiter", {}),
        },
    }


def fallback_profile_question_answer(question: str, payload: dict) -> dict:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    recruiter_signal = analysis.get("recruiter_signal") if isinstance(analysis.get("recruiter_signal"), dict) else {}
    hiring = recruiter_signal.get("hiring_recommendation") if isinstance(recruiter_signal.get("hiring_recommendation"), dict) else {}
    evidence = []
    if analysis.get("summary"):
        evidence.append(str(analysis["summary"]))
    evidence.extend(str(item) for item in (analysis.get("evidence_highlights") or [])[:4])
    if not evidence:
        evidence.append("The public profile has limited generated analysis available.")

    decision = hiring.get("decision") if hiring.get("decision") in {"recommend", "consider", "hold", "insufficient_evidence"} else "insufficient_evidence"
    confidence = hiring.get("confidence") if hiring.get("confidence") in {"high", "medium", "low"} else "low"
    answer = (
        f"For the question '{question}', the available profile evidence supports a "
        f"{decision.replace('_', ' ')} recommendation with {confidence} confidence. "
        "Use the cited evidence below and verify any role-specific requirements in an interview."
    )
    return {
        "answer": answer,
        "recommendation": decision,
        "confidence": confidence,
        "evidence": evidence[:6],
        "verification_questions": [
            "Which project best matches the target role, and what parts did the candidate personally build?",
            "What production, testing, or deployment work can the candidate explain in detail?",
            "Which gaps in the target role requirements are not covered by the public profile?",
        ],
    }


def answer_profile_question(
    question: str,
    user: User,
    sections: list[ProfileSection],
    repositories: list[GitHubRepository],
    leetcode: LeetCodeSnapshot | None,
    evaluation: GeneratedEvaluation | None,
) -> dict:
    payload = profile_question_payload(user, sections, repositories, leetcode, evaluation)
    settings = get_settings()
    if not settings.openai_api_key:
        return fallback_profile_question_answer(question, payload)

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_model,
        instructions=PROFILE_QUESTION_INSTRUCTIONS,
        input=(
            "Answer this recruiter question about the public developer profile.\n\n"
            f"Recruiter question: {question}\n\n"
            f"Profile evidence:\n{json.dumps(payload, ensure_ascii=False)}"
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "public_profile_question_answer",
                "schema": PROFILE_QUESTION_SCHEMA,
                "strict": True,
            }
        },
    )
    return json.loads(response.output_text)
