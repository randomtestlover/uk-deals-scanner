"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function CheckoutButton({
  plan,
  signedIn,
}: {
  plan: "plus" | "pro";
  signedIn: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    if (!signedIn) {
      router.push("/signin");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      const body = await resp.json();
      if (!resp.ok || !body.url) {
        setError(body.error ?? "Checkout unavailable");
        return;
      }
      window.location.href = body.url;
    } catch {
      setError("Network error — try again");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button onClick={go} disabled={busy} className="btn-primary w-full disabled:opacity-50">
        {busy ? "Redirecting…" : `Get ${plan === "plus" ? "Plus" : "Pro"}`}
      </button>
      {error ? <p className="mt-2 text-xs text-rose-400">{error}</p> : null}
    </div>
  );
}
