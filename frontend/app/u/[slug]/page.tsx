import { notFound } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { PublicProfileQuestionBox } from "@/components/PublicProfileQuestionBox";
import { publicFetch } from "@/lib/backend";
import type { PublicProfile } from "@/lib/types";

export default async function PublicProfilePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let profile: PublicProfile;
  try {
    profile = await publicFetch<PublicProfile>(`/public/profiles/${slug}`);
  } catch {
    notFound();
  }

  return (
    <>
      <AppHeader />
      <main className="page stack landing-spacer">
        <section className="panel">
          <span className="status">Verified developer profile</span>
          <h1>{profile.user.name ?? profile.user.slug}</h1>
          <p className="lead">{profile.user.headline ?? profile.evaluation?.summary}</p>
        </section>

        {profile.evaluation && (
          <section className="panel stack">
            <h2>cipher analysis</h2>
            <p>{profile.evaluation.summary}</p>
            <div className="analysis-copy">{profile.evaluation.recruiter_copy}</div>
          </section>
        )}

        <PublicProfileQuestionBox slug={slug} />

        <section className="grid">
          <article className="card">
            <h3>GitHub</h3>
            <p className="muted">{profile.repositories.length} repositories analyzed</p>
          </article>
          <article className="card">
            <h3>LeetCode</h3>
            <p className="muted">
              {profile.leetcode ? `${profile.leetcode.total_solved} solved` : "No public LeetCode snapshot"}
            </p>
          </article>
        </section>

        <section className="grid">
          {profile.sections.map((section) => (
            <article className="card" key={section.id}>
              <span className="status">{section.kind}</span>
              <h3>{section.title}</h3>
              <p className="muted">{section.organization}</p>
              <p>{section.description}</p>
            </article>
          ))}
        </section>
      </main>
    </>
  );
}
