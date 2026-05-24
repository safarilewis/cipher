import { redirect } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { auth } from "@/auth";
import { backendFetch } from "@/lib/backend";
import type { Evaluation, ProfileSection, Source, UserProfile } from "@/lib/types";
import { DashboardNav } from "@/components/DashboardNav";

type DashboardShellProps = {
  children: React.ReactNode;
};

function sourceStatus(sources: Source[], kind: Source["kind"]) {
  return sources.find((source) => source.kind === kind);
}

async function optionalBackendFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    return await backendFetch<T>(path);
  } catch {
    return fallback;
  }
}

export async function DashboardShell({ children }: DashboardShellProps) {
  const session = await auth();
  if (!session) redirect("/login");

  const fallbackProfile: UserProfile = {
    id: "local",
    email: session.user?.email ?? "",
    name: session.user?.name ?? null,
    headline: null,
    slug: "draft",
    published: false
  };

  const [profile, sources, sections, evaluation] = await Promise.all([
    optionalBackendFetch<UserProfile>("/profile", fallbackProfile),
    optionalBackendFetch<Source[]>("/sources", []),
    optionalBackendFetch<ProfileSection[]>("/profile/sections", []),
    optionalBackendFetch<Evaluation | null>("/analysis/latest", null)
  ]);

  const github = sourceStatus(sources, "github");
  const leetcode = sourceStatus(sources, "leetcode");
  const refreshDays = String(sources[0]?.summary?.refresh_interval_days ?? 14);

  return (
    <main className="dashboard-stage">
      <section className="dashboard-app">
        <div className="dashboard-topline">
          <div>
            <div className="sidebar-label">Live profile</div>
            <div className="dashboard-url"><span>cipher.so</span>/{profile.slug}</div>
          </div>
          <div className="dashboard-topline-right">
            <span className="status">{profile.published ? <Eye size={14} /> : <EyeOff size={14} />} {profile.published ? "Published" : "Private"}</span>
            <span className="status">refresh every {refreshDays}d</span>
          </div>
        </div>
        <div className="dashboard-body">
          <DashboardNav
            githubConnected={Boolean(github)}
            leetcodeConnected={Boolean(leetcode)}
            connectedCount={sources.length}
            sectionCount={sections.length}
            analysisStatus={evaluation?.status ?? "none"}
            published={profile.published}
          />

          <section className="dashboard-main ui-main">
            <div className="dashboard-content">
              {children}
            </div>
          </section>
        </div>

        <div className="ui-statusbar">
          <div className="status-item"><div className="status-dot green" /> {sources.length} sources</div>
          <div className="status-item"><div className="status-dot amber" /> {evaluation?.status ?? "analysis pending"}</div>
          <div className="status-item status-right">{profile.published ? "Public profile live" : "Private until reviewed"}</div>
        </div>
      </section>
    </main>
  );
}
