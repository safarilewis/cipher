import Link from "next/link";

export function PublicHeader() {
  return (
    <header className="topbar">
      <Link className="brand" href="/">
        <span className="brand-mark">c</span>
        <span>cipher</span>
      </Link>
      <nav className="nav">
        <Link href="/#how">How It Works</Link>
        <Link href="/#signal">Signal</Link>
        <Link href="/#pricing">Pricing</Link>
        <span className="nav-sep" />
        <Link className="btn-nav" href="/login">Log In</Link>
        <Link className="btn-nav btn-nav-primary" href="/signup">Connect GitHub -&gt;</Link>
      </nav>
    </header>
  );
}
