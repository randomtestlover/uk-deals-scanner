import NextAuth, { type DefaultSession } from "next-auth";
import type { Provider } from "next-auth/providers";
import Google from "next-auth/providers/google";
import Resend from "next-auth/providers/resend";
import PostgresAdapter from "@auth/pg-adapter";
import { pool } from "./db";

declare module "next-auth" {
  interface Session {
    user: { id: string } & DefaultSession["user"];
  }
}

// Providers are env-gated: configure either or both, the UI adapts.
const providers: Provider[] = [];
if (process.env.AUTH_RESEND_KEY) {
  providers.push(
    Resend({ from: process.env.AUTH_EMAIL_FROM ?? "login@flightdeals.example" })
  );
}
if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    })
  );
}

export const authProviders = {
  email: Boolean(process.env.AUTH_RESEND_KEY),
  google: Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET),
};

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PostgresAdapter(pool),
  providers,
  pages: { signIn: "/signin" },
  callbacks: {
    session({ session, user }) {
      session.user.id = user.id;
      return session;
    },
  },
});

/** Numeric DB user id for the current session, or null. */
export async function sessionUserId(): Promise<number | null> {
  const session = await auth();
  const id = session?.user?.id;
  return id ? Number(id) : null;
}
