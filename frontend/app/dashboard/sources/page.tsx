import Link from "next/link";
import { redirect } from "next/navigation";
import { Trash2 } from "lucide-react";
import { auth } from "@/auth";
import { deleteSource } from "@/app/actions";
import { backendFetch } from "@/lib/backend";
import type { Repository, Source } from "@/lib/types";
import { PendingButton } from "@/components/PendingButton";
import { RepositorySelectionForm } from "@/components/RepositorySelectionForm";

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
        <p className="lead">Connected data is user-controlled. Choose up to ten GitHub repos for code review.</p>
      </section>
      <section className="dashboard-card-grid">
        {sources.map((source) => (
          <article className="card stack" key={source.kind}>
            <span className="status">{source.kind}</span>
            <h3>{source.external_username}</h3>
            <p className="muted">Last synced: {source.last_synced_at ? new Date(source.last_synced_at).toLocaleString() : "Never"}</p>
            <p className="muted">
              Free-tier refresh: every {String(source.summary?.refresh_interval_days ?? 14)} days
              {source.summary?.next_refresh_at ? ` - next available ${new Date(String(source.summary.next_refresh_at)).toLocaleString()}` : ""}
            </p>
            <pre className="faint">{JSON.stringify(source.summary ?? {}, null, 2)}</pre>
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
          <span className="status">{selectedCount}/10 selected for code analysis</span>
          <h2>Repository code review</h2>
          <p className="muted">
            adpt sends selected repos to the LLM with commit counts, README, repository structure, and a few key source files.
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
