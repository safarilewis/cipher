import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";

const activityLevels = [
  0, 0, 0, 1, 1, 2, 2, 3, 4, 3, 2, 1, 1, 0, 1, 2, 3, 4, 3, 2, 1, 2, 3, 4, 4, 3,
  2, 1, 0, 0, 1, 1, 2, 3, 4, 4, 3, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2, 1, 0, 0, 1,
  2, 3, 3, 4, 3, 2, 1, 0, 0, 1, 1, 2, 3, 4, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2,
  1, 0, 0, 1, 2, 3, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2
];

const githubRepoUrl = "https://github.com/safarilewis/new-adpt";

function GitHubIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

export default function HomePage() {
  return (
    <>
      <AppHeader />
      <main className="hero">
        <h1>Make your portfolio<br /><span className="dim">queryable by recruiters.</span></h1>

        <p className="hero-sub">
          Connect your GitHub, LeetCode, and experience to publish a reviewed developer profile
          built from real evidence.
        </p>

        <div className="hero-actions">
          <Link href="/signup" className="btn-primary"><GitHubIcon />Connect GitHub</Link>
          <Link href="#how" className="btn-secondary">See how it works</Link>
          <a href={githubRepoUrl} className="btn-secondary" target="_blank" rel="noreferrer"><GitHubIcon />GitHub repo</a>
        </div>

        <div className="hero-ui">
          <div className="ui-window">
            <div className="ui-titlebar">
              <div className="ui-dots"><div className="ui-dot" /><div className="ui-dot" /><div className="ui-dot" /></div>
              <div className="ui-url"><GitHubIcon size={10} /><span className="url-green">cipher.so</span>/u/safs-k</div>
              <div className="ui-sync-note">last synced 2m ago</div>
            </div>

            <div className="ui-body">
              <aside className="ui-sidebar">
                <div className="sidebar-section">
                  <div className="sidebar-label">Overview</div>
                  <div className="sidebar-item active"><div className="s-icon">^</div> Profile</div>
                  <div className="sidebar-item"><div className="s-icon">*</div> Activity</div>
                  <div className="sidebar-item"><div className="s-icon">!</div> Signal</div>
                </div>
                <div className="sidebar-divider" />
                <div className="sidebar-section">
                  <div className="sidebar-label">Sources</div>
                  <div className="sidebar-item"><div className="s-icon">G</div> GitHub</div>
                  <div className="sidebar-item"><div className="s-icon">L</div> LeetCode</div>
                  <div className="sidebar-item"><div className="s-icon">P</div> Profile</div>
                </div>
                <div className="sidebar-divider" />
                <div className="sidebar-section">
                  <div className="sidebar-stat"><span className="sk">Commits</span><span className="sv g">847</span></div>
                  <div className="sidebar-stat"><span className="sk">Repos</span><span className="sv">23</span></div>
                  <div className="sidebar-stat"><span className="sk">Solved</span><span className="sv">312</span></div>
                  <div className="sidebar-stat"><span className="sk">Score</span><span className="sv g">94</span></div>
                </div>
              </aside>

              <section className="ui-main">
                <div className="profile-header">
                  <div className="profile-identity">
                    <div className="profile-avatar">SK</div>
                    <div><div className="profile-name">Safs K.</div><div className="profile-handle">cipher.so/u/safs-k</div></div>
                  </div>
                  <div className="profile-badges"><div className="badge badge-green">Verified</div><div className="badge badge-dim">Open to work</div></div>
                </div>

                <p className="profile-narrative">
                  "Full-stack developer with consistent GitHub activity, strong TypeScript and Python
                  signal, and project context reviewed before publishing."
                </p>

                <div className="metrics">
                  <div className="metric"><div className="metric-val g">847</div><div className="metric-key">Commits / 12mo</div></div>
                  <div className="metric"><div className="metric-val">94.2%</div><div className="metric-key">LC accept rate</div></div>
                  <div className="metric"><div className="metric-val">312</div><div className="metric-key">Problems solved</div></div>
                  <div className="metric"><div className="metric-val g">94</div><div className="metric-key">cipher score</div></div>
                </div>

                <div className="activity-label">Contribution activity</div>
                <div className="activity-grid">
                  {activityLevels.map((level, index) => (
                    <div className={`activity-cell${level ? ` l${level}` : ""}`} key={`${level}-${index}`} />
                  ))}
                </div>

                <div className="stack-row">
                  <span className="stack-pill hi">TypeScript</span>
                  <span className="stack-pill hi">Python</span>
                  <span className="stack-pill">Node.js</span>
                  <span className="stack-pill">Next.js</span>
                  <span className="stack-pill">PostgreSQL</span>
                  <span className="stack-pill">Redis</span>
                </div>
              </section>
            </div>

            <div className="ui-statusbar">
              <div className="status-item"><div className="status-dot green" /> Synced</div>
              <div className="status-item"><div className="status-dot amber" /> Profile reviewed</div>
              <div className="status-item status-right">public link ready</div>
            </div>
          </div>
        </div>
      </main>

      <div className="section-divider landing-spacer" />
      <section className="section reveal in" id="how">
        <div className="section-eyebrow">How it works</div>
        <h2>From raw data<br /><span className="dim">to a queryable portfolio.</span></h2>
        <p className="section-desc">Connect your sources, add career sections, review the analysis, and publish when it is ready.</p>
        <div className="steps">
          <div className="step"><div className="step-num">01 - Connect</div><h3>Link GitHub and LeetCode</h3><p>Bring in repository evidence and problem-solving snapshots without asking anyone to take your resume at face value.</p></div>
          <div className="step"><div className="step-num">02 - Add context</div><h3>Fill in the human parts</h3><p>Add experience, education, projects, and links so the analysis has both hard signal and career context.</p></div>
          <div className="step"><div className="step-num">03 - Review and publish</div><h3>One link you control</h3><p>Read the generated analysis, approve it, then publish a public profile at cipher.so/u/you.</p></div>
        </div>
      </section>

      <div className="section-divider" />
      <section className="section reveal in" id="signal">
        <div className="section-eyebrow">Signal sources</div>
        <h2>Evidence first.<br /><span className="dim">Self-reported where it belongs.</span></h2>
        <p className="section-desc">cipher combines source data with structured profile sections, then makes you review the analysis before anything goes public.</p>
        <div className="signal-cards">
          <div className="signal-card"><div className="sc-eyebrow">Public - OAuth</div><h4>GitHub Activity</h4><p>Commit cadence, repo complexity, language distribution, open source contributions, PR quality, 12-month consistency signal.</p></div>
          <div className="signal-card"><div className="sc-eyebrow">Public - API</div><h4>LeetCode & Competitive</h4><p>Problems solved, difficulty distribution, acceptance rate, contest history. Measures how you think under constraint.</p></div>
          <div className="signal-card"><div className="sc-eyebrow g">Manual - Reviewed</div><h4>Career Sections</h4><p>Experience, education, projects, and links provide the context raw activity cannot explain on its own.</p></div>
          <div className="signal-card"><div className="sc-eyebrow">AI - Reviewed</div><h4>Generated Analysis</h4><p>Your summary is drafted from connected evidence and profile context, then kept private until you approve it.</p></div>
        </div>
      </section>

      <div className="section-divider" />
      <section className="section reveal in">
        <div className="section-eyebrow">Comparison</div>
        <h2>A profile with receipts<br /><span className="dim">beats a static PDF.</span></h2>
        <p className="section-desc">Resumes flatten the work. cipher keeps the evidence, context, and reviewed narrative together.</p>
        <table className="compare-table">
          <thead><tr><th></th><th className="d">Resume / LinkedIn</th><th className="g">cipher profile</th></tr></thead>
          <tbody>
            <tr><td>Data source</td><td className="cross">Self-reported</td><td className="check cipher-col">Verified behavior</td></tr>
            <tr><td>Update frequency</td><td className="cross">When you remember</td><td className="check cipher-col">Refreshable source snapshots</td></tr>
            <tr><td>Can be fabricated</td><td className="cross">Trivially</td><td className="check cipher-col">Evidence-backed</td></tr>
            <tr><td>Shows work patterns</td><td className="cross">Never</td><td className="check cipher-col">Always</td></tr>
            <tr><td>Format</td><td className="cross">PDF attachment</td><td className="check cipher-col">Live URL</td></tr>
            <tr><td>Narrative author</td><td className="cross">You alone</td><td className="check cipher-col">Evidence plus review</td></tr>
          </tbody>
        </table>
      </section>

      <section className="cta-wrap reveal in">
        <div className="cta-inner">
          <div className="cta-left"><h2>Build a profile<br />with the work attached.</h2><p>Start with GitHub, add LeetCode and career context, then publish only after you review the analysis.</p></div>
          <div className="cta-right"><Link href="/signup" className="btn-primary">Connect GitHub -&gt;</Link></div>
        </div>
      </section>

      <footer>
        <div className="footer-left"><div className="footer-logo">Cipher</div><div className="footer-copy">© 2026 Cipher - cipher.so</div></div>
        <div className="footer-links"><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><a href={githubRepoUrl} target="_blank" rel="noreferrer">GitHub</a></div>
      </footer>
    </>
  );
}
