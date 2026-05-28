import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { backendFetch } from "@/lib/backend";
import type { ProfileSection } from "@/lib/types";
import { deleteProfileSection, saveProfileSection, updateProfileSection } from "@/app/actions";
import { PendingButton } from "@/components/PendingButton";

function toMonthValue(date: string | null) {
  return date?.slice(0, 7) ?? "";
}

function SectionCard({ section }: { section: ProfileSection }) {
  return (
    <article className="card stack section-card">
      <div className="section-card-head">
        <div>
          <span className="status">{section.kind}</span>
          <h3>{section.title}</h3>
          <p className="muted">{section.organization ?? "No organization listed"}</p>
        </div>
        <div className="section-card-meta">
          <span>{section.start_date ?? "Start date not set"}</span>
          <span>{section.end_date ?? "End date not set"}</span>
        </div>
      </div>

      {section.description && <p className="section-card-description">{section.description}</p>}
      {section.url && (
        <a className="section-card-link" href={section.url} target="_blank" rel="noreferrer">
          {section.url}
        </a>
      )}
      <form className="section-card-form" action={updateProfileSection}>
        <input type="hidden" name="id" value={section.id} />
        <label className="field">
          <span>Section type</span>
          <select name="kind" defaultValue={section.kind}>
            <option value="project">Project</option>
            <option value="experience">Experience</option>
            <option value="education">Education</option>
            <option value="certification">Certification</option>
            <option value="bootcamp">Bootcamp</option>
          </select>
        </label>
        <label className="field"><span>Title</span><input name="title" defaultValue={section.title} required /></label>
        <label className="field"><span>Organization</span><input name="organization" defaultValue={section.organization ?? ""} /></label>
        <div className="section-card-dates">
          <label className="field"><span>Start date</span><input name="startDate" type="month" defaultValue={toMonthValue(section.start_date)} /></label>
          <label className="field"><span>End date</span><input name="endDate" type="month" defaultValue={toMonthValue(section.end_date)} /></label>
        </div>
        <label className="field"><span>Description</span><textarea name="description" defaultValue={section.description ?? ""} /></label>
        <label className="field"><span>URL</span><input name="url" defaultValue={section.url ?? ""} /></label>
        <input name="order" type="hidden" value={String(section.order)} />
        <PendingButton pendingLabel="Saving section...">Save changes</PendingButton>
      </form>

      <form className="section-card-delete" action={deleteProfileSection}>
        <input type="hidden" name="id" value={section.id} />
        <PendingButton className="danger" pendingLabel="Deleting section...">Delete</PendingButton>
      </form>
    </article>
  );
}

export default async function DashboardProfilePage() {
  const session = await auth();
  if (!session) redirect("/login");

  const sections = await backendFetch<ProfileSection[]>("/profile/sections");

  return (
    <section className="stack">
      <div className="panel stack">
        <span className="status">Profile evidence</span>
        <h1>Add profile evidence</h1>
        <p className="lead">Add education, employment, certifications, bootcamps, and projects that should inform your developer model.</p>
        <form className="dashboard-profile-form" action={saveProfileSection}>
          <label className="field">
            <span>Section type</span>
            <select name="kind" defaultValue="project">
              <option value="project">Project</option>
              <option value="experience">Experience</option>
              <option value="education">Education</option>
              <option value="certification">Certification</option>
              <option value="bootcamp">Bootcamp</option>
            </select>
          </label>
          <label className="field"><span>Title</span><input name="title" required /></label>
          <label className="field"><span>Organization</span><input name="organization" /></label>
          <div className="section-card-dates">
            <label className="field"><span>Start date</span><input name="startDate" type="month" /></label>
            <label className="field"><span>End date</span><input name="endDate" type="month" /></label>
          </div>
          <label className="field"><span>Description</span><textarea name="description" /></label>
          <label className="field"><span>URL</span><input name="url" /></label>
          <input name="order" type="hidden" value="0" />
          <PendingButton pendingLabel="Saving evidence...">Save evidence</PendingButton>
        </form>
      </div>

      <section className="stack">
        <div>
          <span className="status">{sections.length} manual sections</span>
          <h2>Current sections</h2>
          <p className="lead">Edit or delete any manually added section below. Changes update your profile immediately.</p>
        </div>
        {sections.length > 0 ? (
          <div className="profile-section-grid">
            {sections.map((section) => <SectionCard key={section.id} section={section} />)}
          </div>
        ) : (
          <div className="panel stack">
            <h3>No manual sections yet</h3>
            <p className="muted">Add your first section above to start shaping your profile model.</p>
          </div>
        )}
      </section>
    </section>
  );
}
