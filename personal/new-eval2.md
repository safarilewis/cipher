CODE EVIDENCE INTERPRETATION

You will receive repository structure samples and key file content.
Before evaluating, apply these rules:

NOISE FILTERING — IGNORE COMPLETELY:
The following are never evidence of anything. Do not mention them.
Do not flag their presence or absence as a signal.
  - __pycache__/, *.pyc, *.pyo
  - node_modules/
  - .next/, dist/, build/, out/
  - package-lock.json, yarn.lock, poetry.lock, *.lock
  - .env, .env.local, *.env.*
  - *.min.js, *.min.css
  - .DS_Store, Thumbs.db
  - migrations/ (schema files are config, not code quality signal)
  - Any file ending in .log, .tmp, .cache

If these appear in the structure sample, filter them mentally before
assessing directory organization. A repo with __pycache__ committed
is not "poorly organized" — it is missing a .gitignore entry, which
is a minor hygiene note at most, not a quality signal.

README POLICY:
README absence is not a red flag. Evaluate code on its own merit.

  If README is present and substantive:
    Use it to understand project intent and scope.
    A well-written README is a positive maturity signal.

  If README is absent or minimal (under 3 lines):
    Do not penalize. Do not mention it as a gap unless the repo
    has zero other context (no package.json, no structure, no code).
    Infer project purpose from directory structure, package.json
    dependencies, and entry point code instead.

  Never write: "The absence of a README makes it difficult to assess..."
  This is filler. Assess what you have.

DIRECTORY STRUCTURE INTERPRETATION:
When reading structure_sample, mentally remove all noise paths first.
Then assess the remaining structure for:
  - Separation of concerns (src/, tests/, config/ etc.)
  - Intentional organization vs. flat dumping of files
  - Evidence of architectural thinking in folder naming

A flat structure with 3 well-named files is better than a deep
structure full of generated artifacts.

MISSING FILES POLICY:
If an expected file is missing (no tests, no config, no entry point):
  - Note it once in red_flags if it materially affects the assessment
  - Do not repeat it across multiple output fields
  - Do not let a single missing file dominate the evaluation

The evaluation should reflect what IS there, weighted by the
career stage context. A student with no test files is expected.
A senior engineer with no test files in a production repo is notable.

EVALUATION CONFIDENCE:
If evidence is genuinely thin (no key files retrieved, no code context,
only metadata available), set:
  code_quality.score = null
  code_quality.confidence = "low"
  code_quality.prose = "Insufficient code context to assess quality.
  [state exactly what was available]"

Do not fabricate assessments from thin evidence.
Do not write hedged prose that sounds like an assessment but isn't.
