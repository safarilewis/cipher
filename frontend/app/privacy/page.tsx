import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";

export const metadata = {
  title: "Privacy Policy | cipher",
  description: "How cipher handles profile, source, and account data."
};

export default function PrivacyPage() {
  return (
    <>
      <AppHeader />
      <main className="legal-page">
        <header className="legal-hero">
          <div className="legal-eyebrow">Privacy Policy</div>
          <h1>Privacy Policy</h1>
          <p>
            How cipher handles account, source, profile, and analysis data while keeping public
            publication under your control.
          </p>
        </header>

        <div className="legal-layout">
          <aside className="legal-aside">
            <div>
              <span>Last updated</span>
              <strong>May 29, 2026</strong>
            </div>
            <div>
              <span>Project</span>
              <a href="https://github.com/safarilewis/new-adpt" target="_blank" rel="noreferrer">GitHub repo</a>
            </div>
          </aside>

          <article className="legal-document">
            <section>
              <h2>What cipher collects</h2>
              <p>
                cipher collects the information you provide directly, such as your name, headline,
                profile sections, links, and review decisions. When you connect sources, cipher also
                stores source data needed to build your developer profile, including GitHub repository
                evidence and LeetCode progress snapshots.
              </p>
            </section>

            <section>
              <h2>How we use data</h2>
              <p>
                We use your data to authenticate your account, sync connected sources, generate and
                store profile analysis, let you review that analysis, and publish a public profile only
                when you explicitly choose to publish it.
              </p>
            </section>

            <section>
              <h2>Public profiles</h2>
              <p>
                Profiles are private by default. A profile becomes public only after you publish it.
                Public profile pages may include your selected profile details, connected source
                summaries, and reviewed analysis.
              </p>
            </section>

            <section>
              <h2>Third-party services</h2>
              <p>
                cipher relies on services such as GitHub authentication, connected source APIs,
                hosting providers, databases, and AI providers to operate the product. Those services
                process data only as needed to provide the features you request.
              </p>
            </section>

            <section>
              <h2>Your choices</h2>
              <p>
                You can edit profile information, disconnect sources, unpublish your profile, and
                choose whether generated analysis is reviewed and published. To request deletion or ask
                a privacy question, contact the project maintainer through the GitHub repository.
              </p>
            </section>

            <div className="legal-actions">
              <Link className="btn-secondary" href="/">Back home</Link>
              <Link className="btn-secondary" href="/terms">Terms of Service</Link>
            </div>
          </article>
        </div>
      </main>
    </>
  );
}
