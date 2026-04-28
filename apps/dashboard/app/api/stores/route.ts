import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { getSession } from "@/lib/session";

const ApiBase = process.env.API_BASE_URL ?? "http://localhost:8000";

const StoreCreateSchema = z.object({
  slug: z.string().min(2),
  name: z.string().min(1),
  brand_name: z.string().min(1),
  platform: z.enum(["shopify", "woocommerce", "custom", "manual"]),
});

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const json = await req.json();
  const parsed = StoreCreateSchema.safeParse(json);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "validation", issues: parsed.error.issues },
      { status: 400 },
    );
  }

  // For now, expect the org id to come from a session-bound membership endpoint.
  // We'll resolve it via /v1/orgs (first one) — improved when Org Switcher
  // ships.  This is intentionally simple, not a long-term shape.
  const orgsRes = await fetch(`${ApiBase}/v1/orgs`, {
    headers: { "X-Awaaz-User-Id": session.user.id },
    cache: "no-store",
  });
  if (!orgsRes.ok) {
    return NextResponse.json({ error: "no orgs" }, { status: 412 });
  }
  const orgs = (await orgsRes.json()) as Array<{ id: string }>;
  if (!orgs[0]) {
    return NextResponse.json({ error: "no orgs" }, { status: 412 });
  }
  const orgId = orgs[0].id;

  const res = await fetch(`${ApiBase}/v1/orgs/${orgId}/stores`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Awaaz-User-Id": session.user.id,
    },
    body: JSON.stringify(parsed.data),
  });
  const body = await res.json().catch(() => null);
  return NextResponse.json(body, { status: res.status });
}
