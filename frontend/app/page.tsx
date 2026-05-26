import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";

const activityLevels = [
  0, 0, 0, 1, 1, 2, 2, 3, 4, 3, 2, 1, 1, 0, 1, 2, 3, 4, 3, 2, 1, 2, 3, 4, 4, 3,
  2, 1, 0, 0, 1, 1, 2, 3, 4, 4, 3, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2, 1, 0, 0, 1,
  2, 3, 3, 4, 3, 2, 1, 0, 0, 1, 1, 2, 3, 4, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2,
  1, 0, 0, 1, 2, 3, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 3, 2
];

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
        <div className="hero-badge">
          <div className="hero-badge-dot" />
          Early access
        </div>

        <h1>Your code is your resume.<br /><span className="dim">Stop writing about it.</span></h1>

        <p className="hero-sub">
          Connect GitHub. cipher reads your actual behavior and builds a verified developer identity.
          One link. Always live. Zero manual work.
        </p>

        <div className="hero-actions">
          <Link href="/signup" className="btn-primary"><GitHubIcon />Connect GitHub</Link>
          <Link href="#how" className="btn-secondary">See how it works</Link>
        </div>

        <div className="hero-ui">
          <div className="ui-window">
            <div className="ui-titlebar">
              <div className="ui-dots"><div className="ui-dot" /><div className="ui-dot" /><div className="ui-dot" /></div>
              <div className="ui-url"><GitHubIcon size={10} /><span className="url-green">cipher.so</span>/safs-k</div>
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
                  <div className="sidebar-item"><div className="s-icon">V</div> VSCode</div>
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
                    <div><div className="profile-name">Safs K.</div><div className="profile-handle">cipher.so/safs-k</div></div>
                  </div>
                  <div className="profile-badges"><div className="badge badge-green">Verified</div><div className="badge badge-dim">Open to work</div></div>
                </div>

                <p className="profile-narrative">
                  "Strong in full-stack systems. Consistent shipper - 847 commits across 23 repos in 12 months.
                  TypeScript-first, production-minded. Builds complex data pipelines independently."
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
              <div className="status-item"><div className="status-dot amber" /> VSCode connected</div>
              <div className="status-item status-right">3 companies viewed this week</div>
            </div>
          </div>
        </div>
      </main>

      <div className="section-divider landing-spacer" />
      <section className="section reveal in" id="how">
        <div className="section-eyebrow">How it works</div>
        <h2>From code to credential<br /><span className="dim">in 60 seconds.</span></h2>
        <p className="section-desc">Connect your accounts. cipher handles everything else. Free-tier profiles refresh every 14 days.</p>
        <div className="steps">
          <div className="step"><div className="step-num">01 - Connect</div><h3>Link GitHub & LeetCode</h3><p>OAuth in one click. Optionally install the VSCode extension for private session telemetry - the signal layer no other platform can access.</p></div>
          <div className="step"><div className="step-num">02 - Analyze</div><h3>cipher reads your behavior</h3><p>Commit cadence, language distribution, problem-solving depth, coding patterns. GPT writes your narrative from the data. You type nothing.</p></div>
          <div className="step"><div className="step-num">03 - Share</div><h3>One link, forever</h3><p>cipher.so/you - always live, always current. Send it instead of a resume. Free profiles refresh automatically every 14 days.</p></div>
        </div>
      </section>

      <div className="section-divider" />
      <section className="section reveal in" id="signal">
        <div className="section-eyebrow">Signal sources</div>
        <h2>Four layers of verified signal.<br /><span className="dim">None of it self-reported.</span></h2>
        <p className="section-desc">Your profile is built from sources that are harder to game. No endorsements, no keyword stuffing - just what you actually built.</p>
        <div className="signal-cards">
          <div className="signal-card"><div className="sc-eyebrow">Public - OAuth</div><h4>GitHub Activity</h4><p>Commit cadence, repo complexity, language distribution, open source contributions, PR quality, 12-month consistency signal.</p></div>
          <div className="signal-card"><div className="sc-eyebrow">Public - API</div><h4>LeetCode & Competitive</h4><p>Problems solved, difficulty distribution, acceptance rate, contest history. Measures how you think under constraint.</p></div>
          <div className="signal-card"><div className="sc-eyebrow g">Private - Opt-in only</div><h4>VSCode Telemetry</h4><p>Real session behavior. Language time, refactor patterns, build cadence. The signal nobody else has access to - only available through cipher.</p></div>
          <div className="signal-card"><div className="sc-eyebrow">AI - GPT</div><h4>Auto-generated Narrative</h4><p>Your profile summary, written from your actual data. Specific, honest, current. No self-promotion required from you.</p></div>
        </div>
      </section>

      <div className="section-divider" />
      <section className="section reveal in">
        <div className="section-eyebrow">Comparison</div>
        <h2>The resume hasn't changed<br /><span className="dim">since 1482.</span></h2>
        <p className="section-desc">Self-reported, manually updated, trivially gamed. cipher replaces the format entirely.</p>
        <table className="compare-table">
          <thead><tr><th></th><th className="d">Resume / LinkedIn</th><th className="g">cipher profile</th></tr></thead>
          <tbody>
            <tr><td>Data source</td><td className="cross">Self-reported</td><td className="check cipher-col">Verified behavior</td></tr>
            <tr><td>Update frequency</td><td className="cross">When you remember</td><td className="check cipher-col">Every 14 days on free tier</td></tr>
            <tr><td>Can be fabricated</td><td className="cross">Trivially</td><td className="check cipher-col">No</td></tr>
            <tr><td>Shows work patterns</td><td className="cross">Never</td><td className="check cipher-col">Always</td></tr>
            <tr><td>Format</td><td className="cross">PDF attachment</td><td className="check cipher-col">Live URL</td></tr>
            <tr><td>Narrative author</td><td className="cross">You (biased)</td><td className="check cipher-col">Data (objective)</td></tr>
          </tbody>
        </table>
      </section>

      <div className="section-divider" />
      <section className="section reveal in" id="pricing">
        <div className="section-eyebrow">Pricing</div>
        <h2>Free for developers.<br /><span className="dim">Simple for companies.</span></h2>
        <p className="section-desc">Developers can start free. Companies pay for access to the pool.</p>
        <div className="pricing-cards">
          <div className="pricing-card"><div className="pc-tier">Developer</div><div className="pc-price free">Free</div><div className="pc-period">Forever - no credit card</div><p className="pc-desc">Full verified profile, shareable link, GitHub and LeetCode integrations with a 14-day refresh cadence.</p><ul className="pc-features"><li>Verified profile link</li><li>GitHub + LeetCode sync</li><li>Auto-generated narrative</li><li>Refreshes every 14 days</li><li>VSCode extension</li></ul></div>
          <div className="pricing-card featured"><div className="pc-tier g">Company</div><div className="pc-price"><span className="cur">$</span>299</div><div className="pc-period">Per month - flat rate</div><p className="pc-desc">Search and contact verified developers. No per-seat nonsense.</p><ul className="pc-features"><li>Unlimited candidate search</li><li>Filter by language, score, activity</li><li>Direct outreach credits</li><li>Export shortlists</li><li>API access</li></ul></div>
          <div className="pricing-card"><div className="pc-tier">Developer Pro</div><div className="pc-price"><span className="cur">$</span>9</div><div className="pc-period">Per month</div><p className="pc-desc">Know who's looking at your profile. Understand your market value.</p><ul className="pc-features"><li>Profile view analytics</li><li>Salary benchmarks by stack</li><li>Company interest signals</li><li>Priority in search results</li></ul></div>
        </div>
      </section>

      <section className="cta-wrap reveal in">
        <div className="cta-inner">
          <div className="cta-left"><h2>Your code is already<br />your resume.</h2><p>Stop writing about what you built. Let cipher show it. Free for developers.</p></div>
          <div className="cta-right"><input className="cta-input" type="email" placeholder="your@email.com" /><Link href="/signup" className="btn-primary">Get early access -&gt;</Link></div>
        </div>
      </section>

      <footer>
        <div className="footer-left"><div className="footer-logo">cipher</div><div className="footer-copy">© 2026 cipher - cipher.so</div></div>
        <div className="footer-links"><Link href="#">Privacy</Link><Link href="#">Terms</Link><Link href="#">Twitter</Link><Link href="#">GitHub</Link></div>
      </footer>
    </>
  );
}
