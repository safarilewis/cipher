import { GitHubSignInButton } from "@/components/GitHubSignInButton";
import { AppHeader } from "@/components/AppHeader";

export default function SignupPage() {
  return (
    <>
      <AppHeader />
      <main className="page landing-spacer">
        <section className="panel stack">
          <h1>Create your profile</h1>
          <p className="lead">Start with GitHub. Your public profile remains off until you review and publish it.</p>
          <GitHubSignInButton>Sign up with GitHub</GitHubSignInButton>
        </section>
      </main>
    </>
  );
}
