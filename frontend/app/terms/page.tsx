import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";

export const metadata = {
  title: "Terms of Service | cipher",
  description: "Terms for using cipher developer profiles."
};

export default function TermsPage() {
  return (
    <>
      <AppHeader />
      <main className="legal-page">
        <header className="legal-hero">
          <div className="legal-eyebrow">Terms of Service</div>
          <h1>Terms of Service</h1>
          <p>
            The basic terms for using cipher to create, review, and publish an evidence-backed
            developer profile.
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
              <a href="https://github.com/safarilewis/cipher" target="_blank" rel="noreferrer">GitHub repo</a>
            </div>
          </aside>

          <article className="legal-document">
            <section>
              <h2>Using cipher</h2>
              <p>
                cipher helps developers build reviewed public profiles from connected source data,
                structured career context, and generated analysis. You are responsible for the accuracy
                of information you add and for reviewing generated analysis before publishing it.
              </p>
            </section>

            <section>
              <h2>Accounts and sources</h2>
              <p>
                You may connect third-party accounts such as GitHub or LeetCode to import profile
                evidence. You must only connect accounts and data that you have the right to use, and
                you can disconnect sources through the product where supported.
              </p>
            </section>

            <section>
              <h2>Published content</h2>
              <p>
                You control whether your profile is public. If you publish a profile, you grant cipher
                permission to display the published profile content at its public URL until you unpublish
                it or remove the content.
              </p>
            </section>

            <section>
              <h2>Acceptable use</h2>
              <p>
                Do not use cipher to misrepresent your identity, publish content you do not have rights
                to share, interfere with the service, or attempt to access data that does not belong to
                you.
              </p>
            </section>

            <section>
              <h2>No warranty</h2>
              <p>
                cipher is provided as-is. Generated analysis can be incomplete or incorrect, which is
                why review is required before publication. The service may change, pause, or stop as the
                project evolves.
              </p>
            </section>

            <div className="legal-actions">
              <Link className="btn-secondary" href="/">Back home</Link>
              <Link className="btn-secondary" href="/privacy">Privacy Policy</Link>
            </div>
          </article>
        </div>
      </main>
    </>
  );
}
