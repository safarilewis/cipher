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
  const cipherScore = getOverallCipherScore(evaluation);
  const languages = getLanguages(repositories);

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
            <p>{evaluation.summary}</p>
          </div>
          <div className="grid analysis-grid">
            <ListBlock title="Strengths" items={evaluation.strengths} />
            <ListBlock title="Growth areas" items={evaluation.growth_areas} />
            <ListBlock title="Project complexity" items={evaluation.project_complexity_notes} />
            <ListBlock title="Evidence highlights" items={evaluation.evidence_highlights} />
            <ListBlock title="Languages" items={languages} />
          </div>
          <div className="panel stack">
            <h2>Recruiter copy</h2>
            <div className="analysis-copy">{evaluation.recruiter_copy}</div>
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
