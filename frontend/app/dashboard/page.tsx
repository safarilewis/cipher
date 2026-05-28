import Link from "next/link";
import { redirect } from "next/navigation";
import type { ComponentType } from "react";
import { BriefcaseBusiness, CalendarDays, ExternalLink, GraduationCap, RefreshCcw, Trash2, Trophy, Eye, EyeOff } from "lucide-react";
import { auth } from "@/auth";
import { backendFetch } from "@/lib/backend";
import type { Evaluation, ProfileSection, Source, UserProfile } from "@/lib/types";
import { createAnalysis, deleteProfileSection, publishProfile, unpublishProfile, updateProfileBasics } from "@/app/actions";
import { PendingButton } from "@/components/PendingButton";

const activityLevels = [
  0, 1, 1, 2, 3, 4, 3, 2, 1, 0, 1, 2, 2, 3, 4, 4, 3, 2, 1, 0, 0, 1, 2, 3,
  4, 3, 2, 1, 1, 2, 3, 4, 4, 3, 2, 1, 0, 1, 2, 3, 3, 4, 3, 2, 1, 0, 1, 2,
  3, 4, 3, 2, 1, 0, 0, 1, 1, 2, 3, 4, 4, 3, 2, 1, 0, 1, 2, 3, 4, 3, 2, 1
];

const sectionLabels: Record<ProfileSection["kind"], string> = {
  bootcamp: "Bootcamp",
  certification: "Certification",
  education: "Education",
  experience: "Experience",
  project: "Project"
};

const sectionIcons: Record<ProfileSection["kind"], ComponentType<{ size?: number }>> = {
  bootcamp: GraduationCap,
  certification: Trophy,
  education: GraduationCap,
  experience: BriefcaseBusiness,
  project: BriefcaseBusiness
};

function formatDateRange(section: ProfileSection) {
  const start = section.start_date || "No start";
  const end = section.end_date || "Present";
  return `${start} - ${end}`;
}

function DashboardSectionCard({ section }: { section: ProfileSection }) {
  const Icon = sectionIcons[section.kind];

  return (
    <article className="dashboard-section-card">
      <div className="dashboard-section-head">
        <div className="section-icon" aria-hidden="true"><Icon size={17} /></div>
        <div className="dashboard-section-title">
          <span className="status">{sectionLabels[section.kind]}</span>
          <h3>{section.title}</h3>
          {section.organization && <p>{section.organization}</p>}
        </div>
      </div>
      <div className="dashboard-section-date">
        <CalendarDays size={14} aria-hidden="true" />
        <span>{formatDateRange(section)}</span>
      </div>
      {section.description && <p className="dashboard-section-description">{section.description}</p>}
      <div className="dashboard-section-actions">
        {section.url && (
          <a className="btn-secondary btn-compact" href={section.url} target="_blank" rel="noreferrer">
            <ExternalLink size={14} /> Open
          </a>
        )}
        <Link className="btn-secondary btn-compact" href="/dashboard/profile">Edit</Link>
        <form action={deleteProfileSection}>
          <input type="hidden" name="id" value={section.id} />
          <input type="hidden" name="redirectTo" value="/dashboard" />
          <PendingButton className="danger compact" pendingLabel="Deleting..."><Trash2 size={14} /> Delete</PendingButton>
        </form>
      </div>
    </article>
  );
}

export default async function DashboardPage() {
  const session = await auth();
  if (!session) redirect("/login");

  const [profile, sources, sections, evaluation] = await Promise.all([
    backendFetch<UserProfile>("/profile"),
    backendFetch<Source[]>("/sources"),
    backendFetch<ProfileSection[]>("/profile/sections"),
    backendFetch<Evaluation | null>("/analysis/latest")
  ]);

  const canPublish = evaluation?.status === "ready" && evaluation.reviewed;
  const connectedCount = sources.length;
  const refreshDays = String(sources[0]?.summary?.refresh_interval_days ?? 14);
  const projectCount = sections.filter((section) => section.kind === "project").length;
  const experienceCount = sections.filter((section) => section.kind === "experience").length;
  const displayName = profile.name ?? session.user?.name ?? "Your profile";
  const widgetOrigin = process.env.NEXTAUTH_URL ?? process.env.AUTH_URL ?? "http://localhost:3000";
  const widgetSnippet = `<script async src="${widgetOrigin}/widget.js" data-slug="${profile.slug}"></script>`;
  const initials = displayName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "A";

  return (
    <>
      <div className="profile-header">
        <div className="profile-identity">
          <div className="profile-avatar">{initials}</div>
          <div>
            <div className="profile-name">{displayName}</div>
            <div className="profile-handle">cipher.so/{profile.slug}</div>
          </div>
        </div>
        <div className="profile-badges">
          <div className="badge badge-green">{evaluation?.reviewed ? "Verified" : "Draft"}</div>
          <div className="badge badge-dim">{profile.published ? "Published" : "Private"}</div>
        </div>
      </div>

      <p className="profile-narrative">
        &quot;{profile.headline ?? evaluation?.summary ?? "Connect your sources, add profile evidence, and generate your developer signal."}&quot;
      </p>

      <div className="metrics dashboard-metrics">
        <div className="metric"><div className="metric-val g">{connectedCount}</div><div className="metric-key">Sources connected</div></div>
        <div className="metric"><div className="metric-val">{sections.length}</div><div className="metric-key">Profile sections</div></div>
        <div className="metric"><div className="metric-val">{projectCount}</div><div className="metric-key">Projects</div></div>
        <div className="metric"><div className="metric-val g">{refreshDays}d</div><div className="metric-key">Free refresh</div></div>
      </div>

      <div className="dashboard-grid">
        <form className="dashboard-profile-form" action={updateProfileBasics}>
          <div className="activity-label">Profile basics</div>
          <label className="field"><span>Name</span><input name="name" defaultValue={profile.name ?? ""} /></label>
          <label className="field"><span>Headline</span><input name="headline" defaultValue={profile.headline ?? ""} /></label>
          <label className="field"><span>Profile slug</span><input name="slug" defaultValue={profile.slug} pattern="[a-z0-9-]{3,80}" /></label>
          <PendingButton className="secondary" pendingLabel="Saving profile...">Save profile</PendingButton>
        </form>

        <div className="dashboard-signal-panel">
          <div className="activity-label">Contribution activity</div>
          <div className="activity-grid dashboard-activity">
            {activityLevels.map((level, index) => (
              <div className={`activity-cell${level ? ` l${level}` : ""}`} key={`${level}-${index}`} />
            ))}
          </div>
          <div className="stack-row">
            <span className="stack-pill hi">GitHub</span>
            <span className="stack-pill hi">LeetCode</span>
            <span className="stack-pill">GPT analysis</span>
            <span className="stack-pill">Projects {projectCount}</span>
            <span className="stack-pill">Experience {experienceCount}</span>
          </div>
        </div>
      </div>

      <div className="dashboard-action-row">
        <Link className="btn-secondary" href="/dashboard/sources">Manage sources</Link>
        <Link className="btn-secondary" href="/dashboard/profile">Add section</Link>
        <form action={createAnalysis}>
          <PendingButton pendingLabel="Starting analysis..."><RefreshCcw size={16} /> Generate analysis</PendingButton>
        </form>
        {profile.published ? (
          <form action={unpublishProfile}>
            <PendingButton className="secondary" pendingLabel="Unpublishing..."><EyeOff size={16} /> Unpublish</PendingButton>
          </form>
        ) : (
          <form action={publishProfile}>
            <PendingButton disabled={!canPublish} pendingLabel="Publishing..."><Eye size={16} /> Publish</PendingButton>
          </form>
        )}
        {profile.published && <Link className="btn-secondary" href={`/u/${profile.slug}`}>Open public profile</Link>}
      </div>

      {profile.published && (
        <section className="dashboard-section-panel">
          <div className="dashboard-section-panel-head">
            <div>
              <div className="activity-label">Portfolio widget</div>
              <h2>Embed recruiter role-fit search</h2>
              <p className="muted">Drop this script into a portfolio so recruiters can ask whether you fit a specific role using your published cipher evidence.</p>
            </div>
            <Link className="btn-secondary" href={`/u/${profile.slug}`}>Preview</Link>
          </div>
          <pre className="embed-code"><code>{widgetSnippet}</code></pre>
        </section>
      )}

      <section className="dashboard-section-panel">
        <div className="dashboard-section-panel-head">
          <div>
            <div className="activity-label">Added profile evidence</div>
            <h2>What your profile is using</h2>
            <p className="muted">These cards are the projects, experience, education, and credentials that feed your developer profile.</p>
          </div>
          <Link className="btn-secondary" href="/dashboard/profile">Add evidence</Link>
        </div>
        {sections.length > 0 ? (
          <div className="dashboard-sections-grid">
            {sections.map((section) => <DashboardSectionCard key={section.id} section={section} />)}
          </div>
        ) : (
          <div className="dashboard-empty-card">
            <h3>No manual evidence yet</h3>
            <p className="muted">Add an experience, project, education item, certification, or bootcamp so the profile has more than source data to work with.</p>
            <Link className="btn-primary" href="/dashboard/profile">Add first item</Link>
          </div>
        )}
      </section>
    </>
  );
}
