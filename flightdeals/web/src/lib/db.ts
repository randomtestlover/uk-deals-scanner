import { Pool } from "pg";

// Singleton pool — survives Next.js dev hot-reload and is shared across
// route handlers. Sized small: Postgres lives on the same Coolify box.
const globalForPg = globalThis as unknown as { pgPool?: Pool };

export const pool =
  globalForPg.pgPool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 10,
    idleTimeoutMillis: 30_000,
  });

if (process.env.NODE_ENV !== "production") globalForPg.pgPool = pool;
