import Link from "next/link";
import { auth } from "@/auth";
import { signOutUser } from "@/app/actions";
import { PendingButton } from "@/components/PendingButton";

export async function AppHeader() {
  const session = await auth();

  return (
    <header className="topbar">
      <Link className="brand" href="/">
        <span className="brand-mark">c</span>
        <span>cipher</span>
      </Link>
      <nav className="nav">
        {session ? (
          <>
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/dashboard/sources">Sources</Link>
            <Link href="/dashboard/analysis">Analysis</Link>
            <form action={signOutUser}>
              <PendingButton className="secondary" pendingLabel="Signing out...">Sign out</PendingButton>
            </form>
          </>
        ) : (
          <>
            <Link href="/#how">How it works</Link>
            <Link href="/#signal">Signal</Link>
            <a href="https://github.com/safarilewis/cipher" target="_blank" rel="noreferrer">GitHub</a>
            <span className="nav-sep" />
            <Link className="btn-nav" href="/login">Log in</Link>
            <Link className="btn-nav btn-nav-primary" href="/signup">Connect GitHub -&gt;</Link>
          </>
        )}
      </nav>
    </header>
  );
}
