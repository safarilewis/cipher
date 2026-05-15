# adpt Evaluation System — Full Fix Spec
# For Codex implementation
# Author: adpt / internal
# Status: Implementation ready

---

## Overview

This document specifies all changes required to fix the adpt evaluation system.
There are five discrete problem areas. Each section below describes the problem,
the exact fix, and the new types/logic required.

Implement in this order:
1. New types (no side effects)
2. Signal extraction helpers
3. Updated build_analysis_payload()
4. Updated prompt contract
5. Updated output schema + storage

---

## 1. NEW TYPES

Add these types. They extend or replace existing types. Do not delete old types
until all call sites are updated.

```ts
// ── Career stage ──────────────────────────────────────────────────────────────

type CareerStage =
  | "student"       // currently enrolled, no real work experience
  | "new_grad"      // graduated within 2 years, limited experience
  | "early"         // 0-3 years professional experience
  | "mid"           // 3-7 years
  | "senior";       // 7+ years

type CareerStageAssessment = {
  stage: CareerStage;
  confidence: "high" | "medium" | "low";
  signals_used: string[];             // human-readable list of signals that drove inference
  graduation_proximity: "current" | "recent" | "distant" | "unknown";
};

// ── Signal completeness ───────────────────────────────────────────────────────

type SignalCompleteness = {
  code_quality: {
    available: boolean;
    source: "code_context" | "metadata_only" | "none";
    repos_reviewed: number;
    confidence: "high" | "medium" | "low";
  };
  delivery: {
    available: boolean;
    commit_coverage: "full" | "partial" | "summary_only";
    recency: "active" | "dormant" | "unknown";
  };
  algorithms: {
    available: boolean;
    primary_source: "leetcode" | "repo_evidence" | "both" | "none";
    leetcode_strength: "strong" | "moderate" | "weak" | "absent";
    repo_dsa_found: boolean;
  };
  profile_depth: {
    manual_sections: number;
    has_experience: boolean;
    has_education: boolean;
    has_projects: boolean;
  };
};

// ── DSA repo evidence ─────────────────────────────────────────────────────────

type RepoDSAEvidence = {
  repo: string;
  evidence_type:
    | "data_structure_impl"
    | "algorithm_impl"
    | "competitive_programming"
    | "cs_coursework"
    | "complexity_aware_code";
  description: string;
  confidence: "high" | "medium" | "low";
};

// ── Per-repository evaluation ─────────────────────────────────────────────────

type RepositoryEvaluation = {
  full_name: string;
  language: string | null;
  complexity_tier: "prototype" | "project" | "system";
  code_quality_notes: string;
  architecture_notes: string;
  maturity_signals: string[];
  dsa_evidence: string | null;        // null if no DSA found in this repo
  red_flags: string[];
  standout_signals: string[];
};

// ── Scored skill model ────────────────────────────────────────────────────────

type ScoredDimension = {
  score: number | null;               // 0-100. null = insufficient evidence (NOT zero)
  confidence: "high" | "medium" | "low";
  stage_context: string;              // e.g. "Strong for a current student"
  basis: string[];                    // which repos / sources drove this score
  prose: string;
};

type ScoredSkillModel = {
  code_quality: ScoredDimension;
  delivery: ScoredDimension & {
    trend: "accelerating" | "steady" | "declining" | "unknown";
  };
  algorithms: ScoredDimension & {
    source: "leetcode" | "repo_evidence" | "both" | "insufficient";
  };
  overall: {
    score: number | null;
    confidence: "high" | "medium" | "low";
    percentile_note: string;          // e.g. "Top quartile for current students"
  };
};

// ── Updated evaluation output ─────────────────────────────────────────────────

type EvaluationOutput = {
  career_stage: CareerStageAssessment;
  signal_completeness: SignalCompleteness;
  summary: string;
  skill_model: ScoredSkillModel;
  repository_evaluations: RepositoryEvaluation[];   // replaces project_complexity_notes
  strengths: string[];
  growth_areas: string[];
  evidence_highlights: string[];
  recruiter_copy: string;
  // REMOVED: project_complexity_notes (replaced by repository_evaluations)
};

// ── Updated stored evaluation ─────────────────────────────────────────────────

// In generated_evaluations table, add these columns:
// - career_stage jsonb
// - signal_completeness jsonb
// - skill_model jsonb         (replaces old skill_model shape)
// - repository_evaluations jsonb[]
//
// Keep old columns for migration safety until public profile is updated:
// - project_complexity_notes text[]  (deprecated, keep until frontend migrated)
```

---

## 2. SIGNAL EXTRACTION HELPERS

Add these functions. They run before the LLM call and feed the prompt.

### 2a. infer_career_stage()

```ts
function infer_career_stage(input: EvaluationInput): CareerStageAssessment {
  const signals_used: string[] = [];
  let stage: CareerStage = "early";
  let confidence: "high" | "medium" | "low" = "low";
  let graduation_proximity: CareerStageAssessment["graduation_proximity"] = "unknown";

  const sections = input.sections;
  const edu = sections.filter(s => s.kind === "education");
  const exp = sections.filter(s => s.kind === "experience");
  const bootcamp = sections.filter(s => s.kind === "bootcamp");

  // Check for current enrollment
  const current_edu = edu.find(e => !e.end_date || new Date(e.end_date) > new Date());
  if (current_edu) {
    stage = "student";
    confidence = "high";
    graduation_proximity = "current";
    signals_used.push("education section with no end date or future end date");
  }

  // Check for recent graduation (within 2 years)
  if (stage !== "student") {
    const recent_grad = edu.find(e => {
      if (!e.end_date) return false;
      const grad = new Date(e.end_date);
      const two_years_ago = new Date();
      two_years_ago.setFullYear(two_years_ago.getFullYear() - 2);
      return grad > two_years_ago && grad <= new Date();
    });
    if (recent_grad && exp.length === 0) {
      stage = "new_grad";
      confidence = "high";
      graduation_proximity = "recent";
      signals_used.push("education end date within 2 years, no experience sections");
    }
  }

  // Bootcamp without experience = early
  if (bootcamp.length > 0 && exp.length === 0 && stage === "early") {
    stage = "early";
    confidence = "medium";
    signals_used.push("bootcamp section present, no experience sections");
  }

  // Commit history age heuristic
  // If total commits are low and no experience sections, lean student/early
  if (
    input.github.commits < 200 &&
    exp.length === 0 &&
    (stage === "early" || stage === "student")
  ) {
    if (stage !== "student") {
      stage = "student";
      confidence = "medium";
      signals_used.push("low commit count with no experience sections");
    }
  }

  // Coursework repo names
  const coursework_patterns = [
    /cs\d{2,3}/i, /data.?struct/i, /algorithm/i, /assignment/i,
    /homework/i, /lab[-_]/i, /project[-_]\d/i, /\bcomp\d{3}/i,
  ];
  const coursework_repos = input.selected_repositories_for_code_review.filter(r =>
    coursework_patterns.some(p => p.test(r.full_name))
  );
  if (coursework_repos.length > 0) {
    signals_used.push(`${coursework_repos.length} repo(s) match coursework naming patterns`);
    if (stage === "early") {
      stage = "student";
      confidence = "medium";
    }
  }

  // LeetCode grind pattern without experience = student preparing for interviews
  if (
    input.leetcode.available &&
    input.leetcode.total_solved > 100 &&
    exp.length === 0 &&
    stage !== "student"
  ) {
    signals_used.push("high LeetCode volume with no work experience (interview prep pattern)");
    stage = "student";
    confidence = "medium";
  }

  return { stage, confidence, signals_used, graduation_proximity };
}
```

### 2b. assess_signal_completeness()

```ts
function assess_signal_completeness(input: EvaluationInput): SignalCompleteness {
  const has_code_context = input.selected_repository_code_context.length > 0;
  const has_repos = input.selected_repositories_for_code_review.length > 0;

  // Check commit recency from pushed_at dates
  const pushed_dates = input.selected_repositories_for_code_review
    .map(r => r.pushed_at ? new Date(r.pushed_at) : null)
    .filter(Boolean) as Date[];
  const most_recent = pushed_dates.length > 0
    ? Math.max(...pushed_dates.map(d => d.getTime()))
    : null;
  const ninety_days_ago = Date.now() - 90 * 24 * 60 * 60 * 1000;
  const recency = most_recent
    ? most_recent > ninety_days_ago ? "active" : "dormant"
    : "unknown";

  // DSA repo detection
  const dsa_patterns = [
    /algorithm/i, /data.?struct/i, /dsa/i, /leetcode/i,
    /competitive/i, /advent.?of.?code/i, /codeforces/i,
    /hackerrank/i, /graph/i, /tree/i, /sorting/i,
  ];
  const dsa_repos = input.selected_repositories_for_code_review.filter(r =>
    dsa_patterns.some(p => p.test(r.full_name) || p.test(r.description ?? ""))
  );

  // LeetCode strength
  const lc = input.leetcode;
  let lc_strength: SignalCompleteness["algorithms"]["leetcode_strength"] = "absent";
  if (lc.available) {
    const hard_med = lc.medium_solved + lc.hard_solved;
    if (hard_med >= 100) lc_strength = "strong";
    else if (hard_med >= 30) lc_strength = "moderate";
    else lc_strength = "weak";
  }

  return {
    code_quality: {
      available: has_repos,
      source: has_code_context ? "code_context" : has_repos ? "metadata_only" : "none",
      repos_reviewed: input.selected_repository_code_context.length,
      confidence: has_code_context ? "high" : has_repos ? "medium" : "low",
    },
    delivery: {
      available: input.github.commits > 0,
      commit_coverage: "summary_only",     // upgrade to "full" when per-commit data available
      recency,
    },
    algorithms: {
      available: lc.available || dsa_repos.length > 0,
      primary_source: lc.available && dsa_repos.length > 0
        ? "both"
        : lc.available ? "leetcode"
        : dsa_repos.length > 0 ? "repo_evidence"
        : "none",
      leetcode_strength: lc_strength,
      repo_dsa_found: dsa_repos.length > 0,
    },
    profile_depth: {
      manual_sections: input.sections.length,
      has_experience: input.sections.some(s => s.kind === "experience"),
      has_education: input.sections.some(s => s.kind === "education"),
      has_projects: input.sections.some(s => s.kind === "project"),
    },
  };
}
```

### 2c. Fix project_complexity heuristic

Replace the current `project_complexity` logic in `github_quality_signals()`:

```ts
// BEFORE (broken — gameable by forking repos):
// advanced when repository_count >= 8 OR stars >= 50 OR language_count >= 5

// AFTER: metadata complexity is "unverified" unless code context reviewed
// The LLM assigns complexity_tier per repo after reading code context.
// Remove the complexity field from GitHubSignals entirely.
// If you need a pre-LLM complexity signal, use this conservative heuristic:

function metadata_complexity_hint(
  repos: SelectedRepositorySummary[]
): "insufficient_data" | "emerging" | "needs_code_review" {
  if (repos.length === 0) return "insufficient_data";
  const has_substantial = repos.some(r => r.commit_count > 50);
  if (!has_substantial) return "emerging";
  return "needs_code_review"; // actual complexity set by LLM after code review
}

// Do NOT expose this as a public score. Use only as prompt context.
```

---

## 3. UPDATED build_analysis_payload()

Add career stage and signal completeness to the evaluation input:

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

  // NEW:
  career_stage: CareerStageAssessment;
  signal_completeness: SignalCompleteness;
};

// In build_analysis_payload(), add:
const career_stage = infer_career_stage(raw_input);
const signal_completeness = assess_signal_completeness(raw_input);

return {
  ...existing_payload,
  career_stage,
  signal_completeness,
};
```

---

## 4. UPDATED PROMPT CONTRACT

Replace the existing system prompt with the following.
Keep the JSON schema enforcement (strict output). Only the instructions change.

```
ROLE
You are a senior engineering evaluator producing structured developer assessments
for adpt. Your evaluations are read by developers who want honest feedback and
by recruiters who need accurate signal. You are not a marketer.

CARDINAL RULES
- Every claim must trace to a specific source: a repo name, a file path, a
  LeetCode stat, or a profile section. No invented evidence.
- Do not use: "passionate", "rockstar", "ninja", "proven track record",
  "strong communicator", or any filler that carries no information.
- If evidence is missing, say what is missing and what it would change.
  Missing evidence is not a failing grade — it is an honest gap.
- null scores mean insufficient evidence. Never return 0 when data is absent.
  0 is a measurement. null is an absence of measurement.

CAREER STAGE CONTEXT
You will receive a career_stage object in the input. This is critical.

Read it before writing anything. Your entire evaluation framing depends on it.

  student / new_grad:
    - Evaluate relative to peers at this stage, not working engineers.
    - Coursework repos are valid learning evidence. Do not penalize them for
      lacking production architecture.
    - "No production experience" is EXPECTED. Do not list it as a growth area.
    - Delivery signal = learning consistency and project completion rate.
    - strengths should identify what makes this developer stand out among
      students, not among engineers with 5 years of experience.
    - growth_areas should be constructive and forward-looking, not deficit-framing.
    - recruiter_copy should be written for internship and new grad roles.
    - If a student has strong GitHub activity and solid LeetCode, that IS strong.
      Say so clearly.

  early:
    - Some production experience expected. Evaluate what they've built.
    - Growing from coursework toward real systems. Frame accordingly.

  mid / senior:
    - Full engineering bar applies.
    - Production quality, architecture decisions, and scale signal matter.

COURSEWORK REPO POLICY
Repositories matching coursework patterns (CS101, data-structures, assignment-,
lab-, homework-) are learning evidence. Assess:
  - Is the code clean and organized for a learning context?
  - Does it show understanding of the concept being taught?
  - Did the developer go beyond the minimum assignment?
  - Is there a progression pattern across multiple coursework repos?
Do NOT penalize coursework repos for lacking production architecture.
DO note exceptional work that goes beyond assignment requirements.

ALGORITHMS SIGNAL POLICY
LeetCode is one source of algorithms signal. It is not the only one.

When LeetCode is absent or weak (fewer than 50 medium+hard solved):
  Scan the following for algorithmic evidence:
  - Repository names and descriptions (graph, tree, heap, dp, trie, sort, bfs, dfs)
  - Directory structure (algorithms/, dsa/, data-structures/, competitive/)
  - README content mentioning complexity, Big O, algorithms, or problem-solving
  - Key file content for data structure or algorithm implementations
  - Competitive programming repos (Codeforces, HackerRank, Advent of Code)
  - CS coursework repos with clear algorithm focus

If repo-based DSA evidence is found:
  - Set algorithms.source = "repo_evidence" or "both"
  - Score from that evidence
  - Note the source explicitly in algorithms.prose
  - Do not penalize LeetCode absence if equivalent signal exists in repos

A developer who implemented a custom graph traversal for a real project
demonstrates equivalent signal to solving graph problems on LeetCode.

If NO algorithms signal exists from any source:
  algorithms.score = null
  algorithms.source = "insufficient"
  algorithms.prose = "No algorithms signal found in LeetCode or repositories.
  Adding LeetCode activity or a DSA-focused repository would strengthen this
  dimension."

CODE QUALITY SCORING
Only score code_quality when code context is available (selected_repository_code_context
is non-empty). When only metadata is available, set score = null and note the gap.

When code context IS available, assess each repository for:
  - Code organization and file structure
  - Naming conventions and readability
  - Architectural clarity (separation of concerns, module design)
  - Dependency choices (are dependencies appropriate for the project scope?)
  - Testability signals (test files present, testable patterns)
  - Project maturity (README quality, configuration files, completeness)

Return one RepositoryEvaluation object per reviewed repository.
Set complexity_tier per repo:
  prototype  = small, exploratory, or early-stage
  project    = functional, intentional scope, reasonable structure
  system     = multiple modules, clear architecture, production-oriented patterns

SCORING HEURISTICS

algorithms.score:
  LeetCode strong (100+ med/hard) + repo DSA evidence  → 85-100
  LeetCode strong alone                                 → 70-85
  LeetCode moderate + strong repo DSA                   → 70-85
  LeetCode absent + strong repo DSA evidence            → 55-75
  LeetCode weak + minor repo DSA signals                → 30-50
  No signal from either source                          → null

code_quality.score:
  Code context available + clean architecture           → 70-100
  Code context available + mixed quality                → 40-70
  Code context available + unclear structure            → 20-40
  Only metadata available                               → null

delivery.score:
  Active commits (< 90 days), multiple repos, completions  → 70-100
  Moderate activity, some completions                       → 40-70
  Low activity or dormant                                   → 20-40
  No commit data                                            → null

overall.score = weighted average of non-null dimensions:
  code_quality × 0.40
  delivery     × 0.35
  algorithms   × 0.25

If fewer than 2 dimensions have scores, overall.score = null.

STAGE-RELATIVE PERCENTILE NOTES
For overall.percentile_note, use these framings based on career_stage:
  student:   "Top / Mid / Lower quartile for current students"
  new_grad:  "Strong / Moderate / Developing profile for a new graduate"
  early:     "Strong / Developing early-career profile"
  mid/senior: omit percentile note, use plain description

OUTPUT REQUIREMENTS

summary:
  2-4 sentences. Evidence-backed. Calibrated to career stage.
  Do not open with the developer's name.
  Example for student: "A consistent CS student with strong algorithmic
  foundations demonstrated through 180 LeetCode problems and three
  coursework repositories with clean, well-organized code."

skill_model.code_quality.prose:
  When code context available: specific observations from actual code.
  When metadata only: state the gap and what reviewing code would reveal.

skill_model.delivery.prose:
  Commit cadence, recency, repo activity, project completion signals.
  For students: frame as learning consistency, not shipping cadence.

skill_model.algorithms.prose:
  LeetCode evidence + repo DSA evidence. State source explicitly.

strengths:
  3-5 bullets. Each must cite a specific source.
  Bad:  "Strong problem solver"
  Good: "180 LeetCode problems solved (62 medium, 18 hard) indicating solid
        algorithmic foundations for a current student"

growth_areas:
  2-4 bullets. Constructive. Forward-looking.
  For students: do not list "no production experience" — it is expected.
  Focus on what would strengthen their profile next.

repository_evaluations:
  One object per repository with code context available.
  If no code context: return empty array.

evidence_highlights:
  4-7 concrete facts. Numbers, repo names, file paths, section titles.
  Bad:  "Active GitHub presence"
  Good: "847 commits across 23 repositories in the past 12 months"

recruiter_copy:
  One paragraph. Honest and polished.
  Calibrated to career stage:
    student/new_grad → written for internship/new grad recruiters
    early/mid/senior → written for hiring managers
```

---

## 5. UPDATED OUTPUT SCHEMA

Replace the existing OpenAI response schema with:

```json
{
  "type": "object",
  "required": [
    "career_stage",
    "signal_completeness",
    "summary",
    "skill_model",
    "repository_evaluations",
    "strengths",
    "growth_areas",
    "evidence_highlights",
    "recruiter_copy"
  ],
  "additionalProperties": false,
  "properties": {
    "career_stage": {
      "type": "object",
      "required": ["stage", "confidence", "signals_used", "graduation_proximity"],
      "properties": {
        "stage": { "type": "string", "enum": ["student", "new_grad", "early", "mid", "senior"] },
        "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
        "signals_used": { "type": "array", "items": { "type": "string" } },
        "graduation_proximity": { "type": "string", "enum": ["current", "recent", "distant", "unknown"] }
      }
    },
    "signal_completeness": {
      "type": "object",
      "required": ["code_quality", "delivery", "algorithms", "profile_depth"],
      "properties": {
        "code_quality": {
          "type": "object",
          "required": ["available", "source", "repos_reviewed", "confidence"],
          "properties": {
            "available": { "type": "boolean" },
            "source": { "type": "string", "enum": ["code_context", "metadata_only", "none"] },
            "repos_reviewed": { "type": "integer" },
            "confidence": { "type": "string", "enum": ["high", "medium", "low"] }
          }
        },
        "delivery": {
          "type": "object",
          "required": ["available", "commit_coverage", "recency"],
          "properties": {
            "available": { "type": "boolean" },
            "commit_coverage": { "type": "string", "enum": ["full", "partial", "summary_only"] },
            "recency": { "type": "string", "enum": ["active", "dormant", "unknown"] }
          }
        },
        "algorithms": {
          "type": "object",
          "required": ["available", "primary_source", "leetcode_strength", "repo_dsa_found"],
          "properties": {
            "available": { "type": "boolean" },
            "primary_source": { "type": "string", "enum": ["leetcode", "repo_evidence", "both", "none"] },
            "leetcode_strength": { "type": "string", "enum": ["strong", "moderate", "weak", "absent"] },
            "repo_dsa_found": { "type": "boolean" }
          }
        },
        "profile_depth": {
          "type": "object",
          "required": ["manual_sections", "has_experience", "has_education", "has_projects"],
          "properties": {
            "manual_sections": { "type": "integer" },
            "has_experience": { "type": "boolean" },
            "has_education": { "type": "boolean" },
            "has_projects": { "type": "boolean" }
          }
        }
      }
    },
    "summary": { "type": "string" },
    "skill_model": {
      "type": "object",
      "required": ["code_quality", "delivery", "algorithms", "overall"],
      "properties": {
        "code_quality": {
          "type": "object",
          "required": ["score", "confidence", "stage_context", "basis", "prose"],
          "properties": {
            "score": { "type": ["number", "null"], "minimum": 0, "maximum": 100 },
            "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
            "stage_context": { "type": "string" },
            "basis": { "type": "array", "items": { "type": "string" } },
            "prose": { "type": "string" }
          }
        },
        "delivery": {
          "type": "object",
          "required": ["score", "confidence", "stage_context", "basis", "prose", "trend"],
          "properties": {
            "score": { "type": ["number", "null"], "minimum": 0, "maximum": 100 },
            "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
            "stage_context": { "type": "string" },
            "basis": { "type": "array", "items": { "type": "string" } },
            "prose": { "type": "string" },
            "trend": { "type": "string", "enum": ["accelerating", "steady", "declining", "unknown"] }
          }
        },
        "algorithms": {
          "type": "object",
          "required": ["score", "confidence", "stage_context", "basis", "prose", "source"],
          "properties": {
            "score": { "type": ["number", "null"], "minimum": 0, "maximum": 100 },
            "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
            "stage_context": { "type": "string" },
            "basis": { "type": "array", "items": { "type": "string" } },
            "prose": { "type": "string" },
            "source": { "type": "string", "enum": ["leetcode", "repo_evidence", "both", "insufficient"] }
          }
        },
        "overall": {
          "type": "object",
          "required": ["score", "confidence", "percentile_note"],
          "properties": {
            "score": { "type": ["number", "null"], "minimum": 0, "maximum": 100 },
            "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
            "percentile_note": { "type": "string" }
          }
        }
      }
    },
    "repository_evaluations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "full_name", "language", "complexity_tier",
          "code_quality_notes", "architecture_notes",
          "maturity_signals", "dsa_evidence",
          "red_flags", "standout_signals"
        ],
        "properties": {
          "full_name": { "type": "string" },
          "language": { "type": ["string", "null"] },
          "complexity_tier": { "type": "string", "enum": ["prototype", "project", "system"] },
          "code_quality_notes": { "type": "string" },
          "architecture_notes": { "type": "string" },
          "maturity_signals": { "type": "array", "items": { "type": "string" } },
          "dsa_evidence": { "type": ["string", "null"] },
          "red_flags": { "type": "array", "items": { "type": "string" } },
          "standout_signals": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "strengths": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1,
      "maxItems": 5
    },
    "growth_areas": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1,
      "maxItems": 4
    },
    "evidence_highlights": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 2,
      "maxItems": 7
    },
    "recruiter_copy": { "type": "string" }
  }
}
```

---

## 6. DATABASE MIGRATION

Add columns to `generated_evaluations`:

```sql
ALTER TABLE generated_evaluations
  ADD COLUMN IF NOT EXISTS career_stage         jsonb,
  ADD COLUMN IF NOT EXISTS signal_completeness  jsonb,
  ADD COLUMN IF NOT EXISTS repository_evaluations jsonb,
  ADD COLUMN IF NOT EXISTS skill_model_v2       jsonb;

-- skill_model_v2 stores the new ScoredSkillModel shape.
-- skill_model (old) is kept until the frontend is migrated.
-- project_complexity_notes (old) is kept until the frontend is migrated.
-- Once frontend reads from repository_evaluations, drop project_complexity_notes.
```

---

## 7. FALLBACK GENERATION

The existing fallback (no API key configured) must be updated to return the
new output shape. At minimum:

```ts
const fallback_output: EvaluationOutput = {
  career_stage: {
    stage: "early",
    confidence: "low",
    signals_used: ["fallback mode — no inference performed"],
    graduation_proximity: "unknown",
  },
  signal_completeness: assess_signal_completeness(input),
  summary: "Evaluation generated in fallback mode. Connect an OpenAI API key for full analysis.",
  skill_model: {
    code_quality: { score: null, confidence: "low", stage_context: "", basis: [], prose: "Fallback mode." },
    delivery:     { score: null, confidence: "low", stage_context: "", basis: [], prose: "Fallback mode.", trend: "unknown" },
    algorithms:   { score: null, confidence: "low", stage_context: "", basis: [], prose: "Fallback mode.", source: "insufficient" },
    overall:      { score: null, confidence: "low", percentile_note: "" },
  },
  repository_evaluations: [],
  strengths: ["Evaluation unavailable in fallback mode."],
  growth_areas: ["Connect an API key to generate a full evaluation."],
  evidence_highlights: [],
  recruiter_copy: "Evaluation unavailable.",
};
```

---

## 8. IMPLEMENTATION CHECKLIST

For Codex — implement in this order:

- [ ] Add new types to types file
- [ ] Add `infer_career_stage()` helper
- [ ] Add `assess_signal_completeness()` helper
- [ ] Replace `project_complexity` heuristic with `metadata_complexity_hint()`
- [ ] Update `build_analysis_payload()` to include career_stage + signal_completeness
- [ ] Replace system prompt with updated prompt contract above
- [ ] Replace JSON output schema with updated schema above
- [ ] Update storage layer to write new fields to DB
- [ ] Update fallback generation to return new shape
- [ ] Run DB migration (add columns)
- [ ] Update public profile endpoint to return `repository_evaluations`
- [ ] Keep old fields (`project_complexity_notes`, `skill_model`) until frontend migrated

Do NOT break the existing public profile shape until the frontend
reads from the new fields. Ship backend first, migrate frontend separately.

---

## 9. KNOWN REMAINING GAPS (post this fix)

These are not in scope for this implementation but should be tracked:

- Two-pass LLM evaluation (signal extraction call → generation call)
- VSCode extension telemetry as a signal source
- Per-source provenance metadata on evaluations
- Branch-aware or full-history commit counting
- Test file detection
- Dependency risk analysis
