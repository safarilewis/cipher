import { redirect } from "next/navigation";
import { CheckCircle2, RefreshCcw } from "lucide-react";
import { auth } from "@/auth";
import { createAnalysis, reviewAnalysis } from "@/app/actions";
import { backendFetch } from "@/lib/backend";
import type { Evaluation } from "@/lib/types";
import { PendingButton } from "@/components/PendingButton";

function ListBlock({ title, items }: { title: string; items: string[] | null }) {
  if (!items?.length) return null;
  return (
    <div className="card">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

export default async function AnalysisPage() {
  const session = await auth();
  if (!session) redirect("/login");

  const evaluation = await backendFetch<Evaluation | null>("/analysis/latest");

  return (
    <>
      <section className="panel stack">
        <h1>Analysis</h1>
        <p className="lead">Generate evidence-backed profile copy, then review it before anything can be published.</p>
        <form action={createAnalysis}>
          <PendingButton pendingLabel="Analyzing signal..."><RefreshCcw size={16} /> Generate new analysis</PendingButton>
        </form>
      </section>

      {!evaluation && <p className="muted">No analysis yet.</p>}

      {evaluation && (
        <section className="stack">
          <span className="status">{evaluation.status}{evaluation.reviewed ? " reviewed" : ""}</span>
          {evaluation.error && <p className="muted">{evaluation.error}</p>}
          <div className="panel">
            <h2>Summary</h2>
            <p>{evaluation.summary}</p>
          </div>
          <div className="grid">
            <ListBlock title="Strengths" items={evaluation.strengths} />
            <ListBlock title="Growth areas" items={evaluation.growth_areas} />
            <ListBlock title="Project complexity" items={evaluation.project_complexity_notes} />
            <ListBlock title="Evidence highlights" items={evaluation.evidence_highlights} />
          </div>
          <div className="panel">
            <h2>Recruiter copy</h2>
            <p>{evaluation.recruiter_copy}</p>
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
