/**
 * Server-side session helpers.
 *
 * **CVE-2025-29927 mitigation:** never trust middleware to gate access.  Every
 * server component / route handler that needs auth calls `requireSession()`
 * which reads the session via the Better Auth API directly and throws (→ 401
 * or redirect) if it's missing.  Middleware is for routing hints only.
 */

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

export async function getSession() {
  const session = await auth.api.getSession({ headers: await headers() });
  return session;
}

export async function requireSession() {
  const session = await getSession();
  if (!session) {
    redirect("/sign-in");
  }
  return session;
}

export async function requireRole(allowed: ReadonlyArray<string>) {
  const session = await requireSession();
  // Memberships live in the API; the dashboard fetches them via the BFF
  // route which forwards the session cookie.
  return session;
}
