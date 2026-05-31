import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { connectLeetcode, skipLeetcode } from "@/app/actions";
import { PendingButton } from "@/components/PendingButton";

export default async function LeetcodeOnboardingPage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <section className="panel stack">
      <span className="status">Step 2 of 3</span>
      <h1>Add LeetCode</h1>
      <p className="lead">Enter your public username so cipher can snapshot your challenge progress.</p>
      <form className="dashboard-profile-form" action={connectLeetcode}>
        <label className="field">
          <span>LeetCode username</span>
          <input name="username" required />
        </label>
        <PendingButton pendingLabel="Importing LeetCode...">Import LeetCode stats</PendingButton>
      </form>
      <form action={skipLeetcode}>
        <PendingButton className="btn-secondary" pendingLabel="Skipping...">Skip LeetCode</PendingButton>
      </form>
    </section>
  );
}
