"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOutUser } from "@/app/actions";
import { PendingButton } from "@/components/PendingButton";

type DashboardNavProps = {
  githubConnected: boolean;
  leetcodeConnected: boolean;
  connectedCount: number;
  sectionCount: number;
  analysisStatus: string;
  published: boolean;
};

function navClass(pathname: string, href: string) {
  if (href === "/dashboard") {
    return pathname === href ? "sidebar-item active" : "sidebar-item";
  }
  return pathname.startsWith(href) ? "sidebar-item active" : "sidebar-item";
}

export function DashboardNav({
  githubConnected,
  leetcodeConnected,
  connectedCount,
  sectionCount,
  analysisStatus,
  published
}: DashboardNavProps) {
  const pathname = usePathname();

  return (
    <aside className="ui-sidebar dashboard-sidebar">
      <div className="sidebar-section">
        <div className="sidebar-label">Workspace</div>
        <Link className={navClass(pathname, "/dashboard")} href="/dashboard"><div className="s-icon">^</div> Profile</Link>
        <Link className={navClass(pathname, "/dashboard/sources")} href="/dashboard/sources"><div className="s-icon">G</div> Sources</Link>
        <Link className={navClass(pathname, "/dashboard/analysis")} href="/dashboard/analysis"><div className="s-icon">!</div> Signal</Link>
        <Link className={navClass(pathname, "/dashboard/profile")} href="/dashboard/profile"><div className="s-icon">+</div> Add evidence</Link>
      </div>
      <div className="sidebar-divider" />
      <div className="sidebar-section">
        <div className="sidebar-label">Onboarding</div>
        <Link className={navClass(pathname, "/onboarding/github")} href="/onboarding/github"><div className="s-icon">G</div> GitHub <span className="sidebar-chip">{githubConnected ? "on" : "off"}</span></Link>
        <Link className={navClass(pathname, "/onboarding/leetcode")} href="/onboarding/leetcode"><div className="s-icon">L</div> LeetCode <span className="sidebar-chip">{leetcodeConnected ? "on" : "off"}</span></Link>
        <Link className={navClass(pathname, "/onboarding/profile")} href="/onboarding/profile"><div className="s-icon">P</div> Evidence</Link>
      </div>
      <div className="sidebar-divider" />
      <div className="sidebar-section">
        <div className="sidebar-label">Sources</div>
        <div className="sidebar-item"><div className="s-icon">G</div> GitHub <span className="sidebar-chip">{githubConnected ? "on" : "off"}</span></div>
        <div className="sidebar-item"><div className="s-icon">L</div> LeetCode <span className="sidebar-chip">{leetcodeConnected ? "on" : "off"}</span></div>
        <div className="sidebar-item"><div className="s-icon">V</div> VSCode <span className="sidebar-chip">soon</span></div>
      </div>
      <div className="sidebar-divider" />
      <div className="sidebar-section">
        <div className="sidebar-stat"><span className="sk">Sources</span><span className="sv g">{connectedCount}</span></div>
        <div className="sidebar-stat"><span className="sk">Sections</span><span className="sv">{sectionCount}</span></div>
        <div className="sidebar-stat"><span className="sk">Analysis</span><span className="sv">{analysisStatus}</span></div>
        <div className="sidebar-stat"><span className="sk">Public</span><span className="sv g">{published ? "yes" : "no"}</span></div>
      </div>
      <form className="sidebar-signout" action={signOutUser}>
        <PendingButton className="secondary" pendingLabel="Signing out...">Sign out</PendingButton>
      </form>
    </aside>
  );
}
