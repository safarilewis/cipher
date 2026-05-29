import { redirect } from "next/navigation";
import { CheckCircle2, RefreshCcw } from "lucide-react";
import { auth } from "@/auth";
import { createAnalysis, reviewAnalysis } from "@/app/actions";
import { backendFetch } from "@/lib/backend";
import type { Evaluation, Repository } from "@/lib/types";
import { PendingButton } from "@/components/PendingButton";
import { AnalysisStatusPoller } from "@/components/AnalysisStatusPoller";

function ListBlock({ title, items }: { title: string; items: string[] | null }) {
  if (!items?.length) return null;
  return (
    <div className="card">
      <h3>{title}</h3>
      <ul className="analysis-list">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

type SkillDimension = {
  score?: number | null;
  confidence?: string | null;
  stage_context?: string | null;
  basis?: string[] | null;
  prose?: string | null;
  source?: string | null;
  trend?: string | null;
};

function getSkillDimensions(evaluation: Evaluation | null) {
  const model = evaluation?.skill_model_v2 && typeof evaluation.skill_model_v2 === "object"
    ? evaluation.skill_model_v2 as Record<string, unknown>
    : {};

  return (["code_quality", "delivery", "algorithms"] as const)
    .map((key) => {
      const raw = model[key];
      if (!raw || typeof raw !== "object") return null;
      const dimension = raw as SkillDimension;
      if (!dimension.prose && !dimension.basis?.length && dimension.score == null) return null;
      return {
        key,
        title: key === "code_quality" ? "Code quality" : key[0].toUpperCase() + key.slice(1),
        dimension,
      };
    })
    .filter(Boolean) as { key: string; title: string; dimension: SkillDimension }[];
}

function SkillDimensionCard({ title, dimension }: { title: string; dimension: SkillDimension }) {
  const score = typeof dimension.score === "number" ? `${Math.round(dimension.score)}/100` : "Unscored";
  const meta = [
    score,
    dimension.confidence ? `Confidence: ${dimension.confidence}` : null,
    dimension.source ? `Source: ${dimension.source}` : null,
    dimension.trend ? `Trend: ${dimension.trend}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <div className="card">
      <h3>{title}</h3>
      <p className="muted">{meta}</p>
      {dimension.stage_context && <p>{dimension.stage_context}</p>}
      {dimension.prose && <p>{dimension.prose}</p>}
      {!!dimension.basis?.length && (
        <ul className="analysis-list">
          {dimension.basis.slice(0, 6).map((item) => <li key={item}>{item}</li>)}
        </ul>
      )}
    </div>
  );
}

function getLanguages(repositories: Repository[]) {
  const counts = new Map<string, number>();

  for (const repository of repositories) {
    if (!repository.language) continue;
    counts.set(repository.language, (counts.get(repository.language) ?? 0) + 1);
  }

  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([language, count]) => `${language} (${count})`);
}

function getOverallCipherScore(evaluation: Evaluation | null) {
  const overall = evaluation?.skill_model_v2 && typeof evaluation.skill_model_v2 === "object"
    ? (evaluation.skill_model_v2 as { overall?: { score?: number | null; confidence?: string | null; scope_label?: string | null } }).overall
    : null;

  if (!overall || overall.score == null) {
    return { label: "Insufficient data", note: "Waiting on enough signal to score" };
  }

  return {
    label: `${Math.round(overall.score)}/100`,
    note: `${overall.scope_label ? `${overall.scope_label} · ` : ""}Confidence: ${overall.confidence ?? "unknown"}`,
  };
}

type RagCoverage = {
  chunkCount: number;
  fileCount: number;
  files: string[];
  attemptedRepos: number;
  skippedRepos: number;
  chunksPending: number;
  chunksStored: number;
  errors: string[];
};

function getRagCoverage(evaluation: Evaluation | null): RagCoverage {
  const snapshot = evaluation?.profile_signal_snapshot;
  const rag = snapshot && typeof snapshot === "object" ? snapshot.rag : null;
  const ragRecord = rag && typeof rag === "object" ? rag as Record<string, unknown> : {};
  const filesByDimension = ragRecord.files_by_dimension && typeof ragRecord.files_by_dimension === "object"
    ? ragRecord.files_by_dimension as Record<string, unknown>
    : {};
  const embeddingPrecompute = ragRecord.embedding_precompute && typeof ragRecord.embedding_precompute === "object"
    ? ragRecord.embedding_precompute as Record<string, unknown>
    : {};
  const attempted = Array.isArray(embeddingPrecompute.attempted) ? embeddingPrecompute.attempted : [];
  const skipped = Array.isArray(embeddingPrecompute.skipped) ? embeddingPrecompute.skipped : [];
  const rawErrors = Array.isArray(embeddingPrecompute.errors) ? embeddingPrecompute.errors : [];
  const files = new Set<string>();

  for (const dimensionFiles of Object.values(filesByDimension)) {
    if (!Array.isArray(dimensionFiles)) continue;
    for (const file of dimensionFiles) {
      if (typeof file === "string") files.add(file);
    }
  }

  return {
    chunkCount: typeof ragRecord.chunk_count === "number" ? ragRecord.chunk_count : 0,
    fileCount: typeof ragRecord.file_count === "number" ? ragRecord.file_count : files.size,
    files: [...files].slice(0, 8),
    attemptedRepos: attempted.length,
    skippedRepos: skipped.length,
    chunksPending: typeof embeddingPrecompute.chunks_pending === "number" ? embeddingPrecompute.chunks_pending : 0,
    chunksStored: typeof embeddingPrecompute.chunks_stored === "number" ? embeddingPrecompute.chunks_stored : 0,
    errors: rawErrors
      .map((error) => {
        if (typeof error === "string") return error;
        if (error && typeof error === "object" && "message" in error && typeof error.message === "string") return error.message;
        return "";
      })
      .filter(Boolean)
      .slice(0, 2),
  };
}

function formatGeneratedAt(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default async function AnalysisPage({ searchParams }: { searchParams?: Promise<{ error?: string | string[] }> }) {
  const session = await auth();
  if (!session) redirect("/login");
  const resolvedSearchParams = await Promise.resolve(searchParams);

  const [evaluation, repositories] = await Promise.all([
    backendFetch<Evaluation | null>("/analysis/latest"),
    backendFetch<Repository[]>("/sources/github/repositories"),
  ]);

  const totalCommits = repositories.reduce((sum, repository) => sum + repository.commit_count, 0);
  const selectedRepositories = repositories.filter((repository) => repository.selected_for_analysis);
  const embeddedRepositories = selectedRepositories.filter((repository) => repository.embedding_status === "embedded");
  const selectedEmbeddedChunks = selectedRepositories.reduce((sum, repository) => sum + repository.embedded_chunk_count, 0);
  const cipherScore = getOverallCipherScore(evaluation);
  const languages = getLanguages(repositories);
  const ragCoverage = getRagCoverage(evaluation);
  const skillDimensions = getSkillDimensions(evaluation);
  const recruiterCopy = evaluation?.recruiter_copy || evaluation?.summary || "";

  const reviewLabel = evaluation ? (evaluation.reviewed ? "Reviewed" : "Needs review") : "No analysis";
  const statusLabel = evaluation?.status ? evaluation.status.charAt(0).toUpperCase() + evaluation.status.slice(1) : "Idle";
  const analysisInProgress = evaluation?.status === "queued" || evaluation?.status === "running";
  const errorMessage = Array.isArray(resolvedSearchParams?.error)
    ? resolvedSearchParams.error[0]
    : resolvedSearchParams?.error;

  return (
    <>
      <section className="panel stack analysis-hero">
        <div className="stack">
          <span className="status">Analysis workspace</span>
          <h1>Analysis</h1>
          <p className="lead">Generate evidence-backed profile copy, then review it before anything can be published.</p>
        </div>
        <div className="metrics analysis-metrics">
          <div className="metric analysis-stat">
            <div className="metric-val g">{totalCommits.toLocaleString()}</div>
            <div className="metric-key">GitHub commits</div>
            <div className="analysis-stat-note">Across {repositories.length} synced repositories</div>
          </div>
          <div className="metric analysis-stat">
            <div className="metric-val">{selectedRepositories.length}</div>
            <div className="metric-key">Repos in scope</div>
            <div className="analysis-stat-note">Selected for the current evaluation</div>
          </div>
          <div className="metric analysis-stat">
            <div className="metric-val">{embeddedRepositories.length}/{selectedRepositories.length}</div>
            <div className="metric-key">Repos embedded</div>
            <div className="analysis-stat-note">{selectedEmbeddedChunks.toLocaleString()} stored chunks</div>
          </div>
          <div className="metric analysis-stat">
            <div className="metric-val">{cipherScore.label}</div>
            <div className="metric-key">Overall cipher score</div>
            <div className="analysis-stat-note">{cipherScore.note}</div>
          </div>
          <div className="metric analysis-stat">
            <div className="metric-val">{reviewLabel}</div>
            <div className="metric-key">Review state</div>
            <div className="analysis-stat-note">{statusLabel}</div>
          </div>
        </div>
        <form action={createAnalysis}>
          <PendingButton pendingLabel="Starting analysis..."><RefreshCcw size={16} /> Generate new analysis</PendingButton>
        </form>
        {errorMessage && (
          <div className="card">
            <h3>Analysis error</h3>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{errorMessage}</pre>
          </div>
        )}
      </section>

      {!evaluation && <p className="muted">No analysis yet.</p>}

      {evaluation && (
        <section className="stack">
          <span className="status">{evaluation.status}{evaluation.reviewed ? " reviewed" : ""}</span>
          {evaluation.error && <p className="muted">{evaluation.error}</p>}
          {analysisInProgress && <AnalysisStatusPoller initialStatus={evaluation.status} />}
          <div className="panel stack">
            <h2>Summary</h2>
            <p className="muted">Run {evaluation.id} · generated {formatGeneratedAt(evaluation.updated_at)}</p>
            <p>{evaluation.summary}</p>
          </div>
          {skillDimensions.length > 0 && (
            <div className="grid analysis-grid">
              {skillDimensions.map(({ key, title, dimension }) => (
                <SkillDimensionCard key={key} title={title} dimension={dimension} />
              ))}
            </div>
          )}
          <div className="grid analysis-grid">
            <ListBlock title="Strengths" items={evaluation.strengths} />
            <ListBlock title="Growth areas" items={evaluation.growth_areas} />
            <ListBlock title="Project complexity" items={evaluation.project_complexity_notes} />
            <ListBlock title="Evidence highlights" items={evaluation.evidence_highlights} />
            <ListBlock title="Languages" items={languages} />
            <div className="card">
              <h3>Evidence coverage</h3>
              <p className="muted">
                Current repo embeddings: {embeddedRepositories.length} of {selectedRepositories.length} selected repos embedded; {selectedEmbeddedChunks.toLocaleString()} chunks stored.
              </p>
              <p className="muted">
                {ragCoverage.chunkCount > 0
                  ? `${ragCoverage.chunkCount} retrieved code chunks across ${ragCoverage.fileCount} files`
                  : "No retrieved code chunks were attached to this analysis"}
              </p>
              <p className="muted">
                Embedding pass: {ragCoverage.chunksStored.toLocaleString()} of {ragCoverage.chunksPending.toLocaleString()} chunks stored from {ragCoverage.attemptedRepos} repos; {ragCoverage.skippedRepos} repos skipped.
              </p>
              {ragCoverage.errors.length > 0 && (
                <ul className="analysis-list">
                  {ragCoverage.errors.map((error) => <li key={error}>{error}</li>)}
                </ul>
              )}
              {ragCoverage.files.length > 0 && (
                <ul className="analysis-list">
                  {ragCoverage.files.map((file) => <li key={file}>{file}</li>)}
                </ul>
              )}
              {selectedRepositories.length > 0 && (
                <ul className="analysis-list">
                  {selectedRepositories.slice(0, 8).map((repository) => (
                    <li key={repository.id}>
                      {repository.full_name}: {repository.embedding_status === "embedded"
                        ? `${repository.embedded_chunk_count.toLocaleString()} chunks`
                        : repository.code_analysis_available
                          ? "code fetched, embedding pending"
                          : "fetch pending"}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <div className="panel stack">
            <h2>Recruiter copy</h2>
            <div className="analysis-copy">{recruiterCopy}</div>
          </div>
          {!evaluation.reviewed && evaluation.status === "ready" && (
            <form action={reviewAnalysis}>
              <input type="hidden" name="id" value={evaluation.id} />
              <PendingButton pendingLabel="Marking reviewed..."><CheckCircle2 size={16} /> Mark reviewed</PendingButton>
            </form>
          )}
        </section>
      )}
    </>
  );
}
