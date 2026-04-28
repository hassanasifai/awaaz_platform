import { betterAuth } from "better-auth";
import { Pool } from "pg";

const databaseUrl =
  process.env.DATABASE_URL_SYNC?.replace(/^postgresql\+psycopg:/, "postgresql:") ??
  process.env.DATABASE_URL?.replace(/^postgresql\+asyncpg:/, "postgresql:") ??
  "postgresql://awaaz:devpassword@localhost:5432/awaaz";

const trustedOrigins = (process.env.AUTH_TRUSTED_ORIGINS ?? "http://localhost:3000")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

/**
 * Server-side Better Auth singleton.  Schema is shared with the API
 * (`auth_sessions`, `users`, `auth_oauth_accounts`, `auth_verification_tokens`)
 * — see `apps/api/awaaz_api/migrations/versions/...`.
 */
export const auth = betterAuth({
  secret: requireEnv("BETTER_AUTH_SECRET"),
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  trustedOrigins,
  database: new Pool({ connectionString: databaseUrl }),
  session: {
    expiresIn: 60 * 60 * 24 * 30,
    cookieCache: { enabled: true, maxAge: 60 },
  },
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false,
    autoSignIn: true,
    minPasswordLength: 12,
  },
  socialProviders: {
    google: process.env.GOOGLE_CLIENT_ID
      ? {
          clientId: process.env.GOOGLE_CLIENT_ID,
          clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
        }
      : undefined,
  },
  advanced: {
    cookiePrefix: "awaaz",
    useSecureCookies: process.env.NODE_ENV === "production",
    crossSubDomainCookies: { enabled: false },
  },
  plugins: [],
});

export type Auth = typeof auth;

function requireEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(
      `${key} is required.  Generate one with: openssl rand -hex 32`,
    );
  }
  return value;
}
