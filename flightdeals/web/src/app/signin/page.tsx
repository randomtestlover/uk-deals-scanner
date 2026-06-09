import { redirect } from "next/navigation";
import { auth, authProviders, signIn } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function SignInPage() {
  const session = await auth().catch(() => null);
  if (session?.user) redirect("/account");

  const none = !authProviders.email && !authProviders.google;

  return (
    <div className="mx-auto max-w-md py-10">
      <h1 className="text-center text-3xl font-extrabold">Sign in</h1>
      <p className="mt-2 text-center text-slate-400">
        One account for alerts, regional airports and live search.
      </p>

      <div className="card mt-8 space-y-4">
        {authProviders.email ? (
          <form
            action={async (formData: FormData) => {
              "use server";
              await signIn("resend", {
                email: formData.get("email") as string,
                redirectTo: "/account",
              });
            }}
            className="space-y-3"
          >
            <label className="block text-sm font-semibold" htmlFor="email">
              Email — we&apos;ll send you a magic link
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              placeholder="you@example.co.uk"
              className="input"
            />
            <button type="submit" className="btn-primary w-full">
              Email me a sign-in link
            </button>
          </form>
        ) : null}

        {authProviders.email && authProviders.google ? (
          <div className="text-center text-xs text-slate-500">or</div>
        ) : null}

        {authProviders.google ? (
          <form
            action={async () => {
              "use server";
              await signIn("google", { redirectTo: "/account" });
            }}
          >
            <button type="submit" className="btn-ghost w-full">
              Continue with Google
            </button>
          </form>
        ) : null}

        {none ? (
          <p className="text-center text-sm text-slate-400">
            Sign-in isn&apos;t configured yet. Set <code>AUTH_RESEND_KEY</code> and/or{" "}
            <code>GOOGLE_CLIENT_ID</code> + <code>GOOGLE_CLIENT_SECRET</code>.
          </p>
        ) : null}
      </div>
    </div>
  );
}
