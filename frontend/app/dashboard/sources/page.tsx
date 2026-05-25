import Link from "next/link";
import { redirect } from "next/navigation";
import { Trash2 } from "lucide-react";
import { auth } from "@/auth";
import { deleteSource } from "@/app/actions";
import { backendFetch } from "@/lib/backend";
import type { Repository, Source } from "@/lib/types";
import { PendingButton } from "@/components/PendingButton";
import { RepositorySelectionForm } from "@/components/RepositorySelectionForm";

function numberFromSummary(summary: Record<string, unknown> | null, key: string): number | null {
  const value = summary?.[key];
  return typeof value === "number" ? value : null;
}

function formatDateTime(value: string | null): string {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function sourceMetrics(source: Source, repositories: Repository[]) {
  if (source.kind === "github") {
    const summary = source.summary;
    const repoCount = numberFromSummary(summary, "repository_count") ?? repositories.length;
    const commitCount =
      numberFromSummary(summary, "all_time_commit_count") ??
      numberFromSummary(summary, "total_commit_count") ??
      repositories.reduce((sum, repository) => sum + repository.commit_count, 0);

    return [
      { label: "Repositories", value: repoCount.toLocaleString() },
      { label: "All-time commits", value: commitCount.toLocaleString() },
      { label: "Provider", value: "GitHub" },
    ];
  }

  const summary = source.summary;
  const rank = numberFromSummary(summary, "ranking");
  return [
    { label: "Total solved", value: (numberFromSummary(summary, "total_solved") ?? 0).toLocaleString() },
    { label: "Easy / Medium / Hard", value: `${numberFromSummary(summary, "easy_solved") ?? 0} / ${numberFromSummary(summary, "medium_solved") ?? 0} / ${numberFromSummary(summary, "hard_solved") ?? 0}` },
    { label: "Global rank", value: rank ? `#${rank.toLocaleString()}` : "Unavailable" },
  ];
}

export default async function SourcesPage() {
  const session = await auth();
  if (!session) redirect("/login");

  const [sources, repositories] = await Promise.all([
    backendFetch<Source[]>("/sources"),
    backendFetch<Repository[]>("/sources/github/repositories")
  ]);
  const githubSource = sources.find((source) => source.kind === "github");
  const allTimeCommitTotal = Number(githubSource?.summary?.all_time_commit_count ?? githubSource?.summary?.total_commit_count ?? repositories.reduce((sum, repo) => sum + repo.commit_count, 0));
  const selectedCount = repositories.filter((repo) => repo.selected_for_analysis).length;

  return (
    <>
      <section className="dashboard-page-head">
        <h1>Sources</h1>
        <p className="lead">Connected data is user-controlled. Choose up to twenty GitHub repos for code review.</p>
      </section>
      <section className="dashboard-card-grid">
        {sources.map((source) => (
          <article className="card stack source-card" key={source.kind}>
            <div className="source-card-head">
              <span className="status source-kind">{source.kind}</span>
              <h3>{source.external_username}</h3>
              <p className="muted">Last synced: {formatDateTime(source.last_synced_at)}</p>
            </div>

            <div className="source-metrics-grid">
              {sourceMetrics(source, repositories).map((metric) => (
                <div className="source-metric" key={`${source.kind}-${metric.label}`}>
                  <div className="source-metric-value">{metric.value}</div>
                  <div className="source-metric-label">{metric.label}</div>
                </div>
              ))}
            </div>

            <div className="source-refresh-note">
              Free-tier refresh every {String(source.summary?.refresh_interval_days ?? 14)} days.
              {source.summary?.next_refresh_at ? ` Next refresh: ${formatDateTime(String(source.summary.next_refresh_at))}.` : ""}
            </div>

            <form action={deleteSource}>
              <input type="hidden" name="kind" value={source.kind} />
              <PendingButton className="danger" pendingLabel="Deleting source..."><Trash2 size={16} /> Delete source</PendingButton>
            </form>
          </article>
        ))}
        {sources.length === 0 && (
          <article className="card stack">
            <h3>No sources connected</h3>
            <Link className="button" href="/onboarding/github">Start onboarding</Link>
          </article>
        )}
      </section>

      <section className="panel stack">
        <div>
          <span className="status">{selectedCount}/20 selected for code analysis</span>
          <h2>Repository code review</h2>
          <p className="muted">
            cipher sends selected repos to the LLM with commit counts, README, repository structure, and a few key source files.
            All-time synced commits: {allTimeCommitTotal}.
          </p>
        </div>
        {repositories.length > 0 ? (
          <RepositorySelectionForm repositories={repositories} />
        ) : (
          <p className="muted">Import GitHub first to choose repositories for code analysis.</p>
        )}
      </section>
    </>
  );
}
