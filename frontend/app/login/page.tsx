import { GitHubSignInButton } from "@/components/GitHubSignInButton";
import { AppHeader } from "@/components/AppHeader";

export default function LoginPage() {
  return (
    <>
      <AppHeader />
      <main className="page landing-spacer">
        <section className="panel stack">
          <h1>Log in</h1>
          <p className="lead">Continue with GitHub to manage your cipher profile.</p>
          <GitHubSignInButton>Continue with GitHub</GitHubSignInButton>
        </section>
      </main>
    </>
  );
}
