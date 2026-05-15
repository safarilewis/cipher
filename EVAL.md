# adpt Evaluation Spec

This document describes the current profile structure, evaluation input, evaluation prompt contract, and generated output shape used by adpt.

## Profile Structure

The profile is built from a user record, connected source data, manual profile sections, selected GitHub repositories, and generated evaluations.

### User

Stored in `users`.

```ts
type UserProfile = {
  id: string;
  email: string | null;
  name: string | null;
  slug: string;
  headline: string | null;
  published: boolean;
  created_at: datetime;
  updated_at: datetime;
};
```

Notes:
- `published` is `false` by default.
- Public profile links are only readable after the user reviews an evaluation and publishes.
- `slug` is the public profile identifier used by `/u/[slug]`.

### Connected Sources

Stored in `connected_accounts`.

```ts
type ConnectedAccount = {
  id: string;
  user_id: string;
  kind: "github" | "leetcode";
  external_username: string;
  access_token: string | null;
  raw_snapshot: Record<string, unknown> | null;
  last_synced_at: datetime | null;
  created_at: datetime;
};
```

GitHub source snapshots currently include:

```json
{
  "repository_count": 23,
  "total_commit_count": 847,
  "synced_from": "github"
}
```

Source refresh policy:
- Free-tier refreshes are limited by `FREE_TIER_REFRESH_DAYS`.
- Default is `14`.
- The frontend displays next available refresh time from source summary data.

### Manual Profile Sections

Stored in `profile_sections`.

```ts
type ProfileSection = {
  id: string;
  user_id: string;
  kind: "education" | "experience" | "certification" | "bootcamp" | "project";
  title: string;
  organization: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  url: string | null;
  order: number;
};
```

Manual sections are treated as user-claimed evidence unless supported by connected source data.

### GitHub Repositories

Stored in `github_repositories`.

```ts
type GitHubRepository = {
  id: string;
  user_id: string;
  full_name: string;
  description: string | null;
  language: string | null;
  stars: number;
  forks: number;
  open_issues: number;
  commit_count: number;
  selected_for_analysis: boolean;
  pushed_at: datetime | null;
  code_analysis_snapshot: Record<string, unknown> | null;
  raw: Record<string, unknown> | null;
};
```

Repository notes:
- `commit_count` is fetched during GitHub sync.
- Users can select up to 5 repositories for code analysis.
- Selected repositories receive code-context extraction during analysis.
- `code_analysis_snapshot` stores the sampled code review input used for generation.

### LeetCode Snapshot

Stored in `leetcode_snapshots`.

```ts
type LeetCodeSnapshot = {
  id: string;
  user_id: string;
  username: string;
  total_solved: number;
  easy_solved: number;
  medium_solved: number;
  hard_solved: number;
  ranking: number | null;
  raw: Record<string, unknown> | null;
  created_at: datetime;
};
```

LeetCode is used only for algorithms/problem-solving signal.

## Evaluation Input

The evaluation payload is built in `build_analysis_payload()`.

```ts
type EvaluationInput = {
  profile: {
    name: string | null;
    headline: string | null;
  };
  github: GitHubSignals;
  selected_repositories_for_code_review: SelectedRepositorySummary[];
  selected_repository_code_context: RepositoryCodeContext[];
  leetcode: LeetCodeSignals;
  sections: ManualSectionEvidence[];
  manual_profile: ManualProfileSignals;
};
```

### GitHub Signals

Produced by `github_quality_signals()`.

```ts
type GitHubSignals = {
  repository_count: number;
  language_count: number;
  languages: string[];
  stars: number;
  forks: number;
  commits: number;
  active_projects: number;
  project_complexity: "emerging" | "solid" | "advanced";
};
```

Current complexity heuristic:
- `advanced` when repository count is at least 8, stars are at least 50, or language count is at least 5.
- `solid` when repository count is at least 3, stars are at least 10, or language count is at least 3.
- Otherwise `emerging`.

Important interpretation:
- Commits are activity evidence, not direct quality evidence.
- Stars/forks are weak external validation, not proof of engineering quality.
- Language count indicates breadth, not mastery.

### Selected Repository Summary

Included for repos where `selected_for_analysis = true`.

```ts
type SelectedRepositorySummary = {
  full_name: string;
  description: string | null;
  language: string | null;
  stars: number;
  forks: number;
  commit_count: number;
  pushed_at: string | null;
};
```

### Repository Code Context

Fetched for up to 5 selected repositories during `run_analysis()`.

```ts
type RepositoryCodeContext = {
  full_name: string;
  default_branch: string;
  file_count: number;
  structure_sample: string[];
  readme: string;
  key_files: Array<{
    path: string;
    content: string;
  }>;
  sampling_strategy: string;
};
```

Sampling behavior:
- README is fetched and truncated to `MAX_CODE_FILE_CHARS`.
- Recursive git tree is fetched for the default branch.
- `structure_sample` includes up to `MAX_TREE_PATHS`.
- Key files are selected from known root/config/source paths, then from common source directories.
- Each key file is truncated to `MAX_CODE_FILE_CHARS`.

Current preferred key files include:
- `README.md`
- `package.json`
- `pyproject.toml`
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml`
- `next.config.ts`
- `tsconfig.json`
- `app/main.py`
- `src/main.ts`
- `src/index.ts`
- `src/App.tsx`

For large repositories, the model is instructed to evaluate the structure sample, README, package/config files, and selected key files as sampled code evidence.

### LeetCode Signals

Produced by `leetcode_signals()`.

```ts
type LeetCodeSignals =
  | {
      available: false;
    }
  | {
      available: true;
      total_solved: number;
      easy_solved: number;
      medium_solved: number;
      hard_solved: number;
      ranking: number | null;
    };
```

### Manual Section Evidence

```ts
type ManualSectionEvidence = {
  kind: string;
  title: string;
  organization: string | null;
  description: string | null;
};
```

### Manual Profile Signals

Produced by `profile_signals()`.

```ts
type ManualProfileSignals = {
  section_counts: Record<string, number>;
  total_sections: number;
};
```

## Evaluation Prompt Contract

The OpenAI call uses the Responses API with strict JSON schema output.

The evaluator is instructed to:
- Build a sober, recruiter-readable developer model.
- Prefer evidence over polish.
- Trace every claim to GitHub, LeetCode, or user-entered profile sections.
- Evaluate actual selected repository code when code context is available.
- State uncertainty instead of filling gaps with generic praise.

Evidence priority order:
1. Selected repository code context.
2. GitHub repository metadata.
3. LeetCode snapshot.
4. Manual profile sections.

Repository review must assess:
- Code organization.
- Maintainability.
- Architectural clarity.
- Testability.
- Dependency choices.
- Project maturity.

Hard guardrails:
- Do not invent degrees, jobs, certifications, employers, technologies, metrics, outcomes, test coverage, security posture, or production usage.
- Do not claim production quality, security quality, scalability, or test coverage unless directly evidenced.
- Do not use empty resume filler such as "passionate", "rockstar", "ninja", or "proven track record".
- If source data is missing, say what is missing and what would strengthen the signal.

## Evaluation Output

The model must return this strict schema.

```ts
type EvaluationOutput = {
  summary: string;
  skill_model: {
    code_quality: string;
    delivery: string;
    algorithms: string;
  };
  strengths: string[];
  growth_areas: string[];
  project_complexity_notes: string[];
  evidence_highlights: string[];
  recruiter_copy: string;
};
```

Output expectations:
- `summary`: 2-4 balanced, evidence-backed sentences.
- `skill_model.code_quality`: actual code evidence when available, otherwise the code evidence gap.
- `skill_model.delivery`: commits, recency, repository activity, project completion signals, and profile sections.
- `skill_model.algorithms`: LeetCode evidence only.
- `strengths`: 3-5 concise evidence-backed bullets.
- `growth_areas`: 2-4 constructive bullets.
- `project_complexity_notes`: 3-5 bullets about repos, architecture, scope, README/structure, dependencies, or maturity.
- `evidence_highlights`: 4-7 concrete facts with numbers, repository names, file paths, or section titles.
- `recruiter_copy`: one honest, polished paragraph.

## Stored Evaluation Structure

Generated output is stored in `generated_evaluations`.

```ts
type GeneratedEvaluation = {
  id: string;
  user_id: string;
  status: "queued" | "running" | "ready" | "failed";
  summary: string | null;
  skill_model: {
    code_quality: string;
    delivery: string;
    algorithms: string;
  } | null;
  strengths: string[] | null;
  growth_areas: string[] | null;
  project_complexity_notes: string[] | null;
  evidence_highlights: string[] | null;
  recruiter_copy: string | null;
  error: string | null;
  reviewed: boolean;
  created_at: datetime;
  updated_at: datetime;
};
```

Lifecycle:
1. Evaluation is created with `status = "queued"`.
2. `run_analysis()` sets `status = "running"`.
3. Source data, selected repo code context, LeetCode data, and profile sections are gathered.
4. OpenAI generates structured output, or fallback generation is used when no API key is configured.
5. On success, `status = "ready"` and generated fields are stored.
6. On failure, `status = "failed"` and `error` is stored.
7. User reviews the evaluation.
8. Public profile can be published only after review.

## Public Profile Output

The public endpoint returns:

```ts
type PublicProfile = {
  user: UserProfile;
  sections: ProfileSection[];
  repositories: GitHubRepository[];
  leetcode: LeetCodeSnapshot | null;
  evaluation: GeneratedEvaluation | null;
};
```

Public profile behavior:
- If `published = false`, public slug access must fail.
- If source data is deleted, deleted snapshots should not be used in future analysis.
- AI output is not public until the user reviews and publishes.

## Current Gaps

These are areas to improve as the evaluation system matures:
- Add explicit numeric subscores for code quality, delivery, algorithms, and profile completeness.
- Add confidence levels per output section.
- Add per-repository evaluation objects rather than only prose notes.
- Add test-file detection and dependency-risk summaries.
- Add branch-aware or full-history commit counting if needed.
- Add VSCode extension signals when that source exists.
- Add provenance metadata that records exactly which source snapshot generated each evaluation.
