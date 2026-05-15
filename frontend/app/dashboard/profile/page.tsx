import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { saveProfileSection } from "@/app/actions";
import { PendingButton } from "@/components/PendingButton";

export default async function DashboardProfilePage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <section className="panel stack">
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
        <label className="field"><span>Description</span><textarea name="description" /></label>
        <label className="field"><span>URL</span><input name="url" /></label>
        <input name="order" type="hidden" value="0" />
        <PendingButton pendingLabel="Saving evidence...">Save evidence</PendingButton>
      </form>
    </section>
  );
}
