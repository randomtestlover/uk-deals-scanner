import Link from "next/link";
import { auth } from "@/lib/auth";

export default async function Nav() {
  const session = await auth().catch(() => null);
  return (
    <header className="border-b border-edge bg-panel/60 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-lg font-bold tracking-tight">
          ✈️ FlightDeals<span className="text-sky-400">UK</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/deals" className="btn-ghost border-0">Deals</Link>
          <Link href="/explore/LHR" className="btn-ghost border-0">Explore</Link>
          <Link href="/search" className="btn-ghost border-0">Live search</Link>
          <Link href="/pricing" className="btn-ghost border-0">Pricing</Link>
          {session?.user ? (
            <Link href="/account" className="btn-primary ml-2">Account</Link>
          ) : (
            <Link href="/signin" className="btn-primary ml-2">Sign in</Link>
          )}
        </nav>
      </div>
    </header>
  );
}
