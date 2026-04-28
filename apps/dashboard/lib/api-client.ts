/**
 * BFF API client — consumed by both server components and client components.
 *
 * On the server we forward the session cookie to the FastAPI control plane
 * via a Bearer token issued by the Better Auth server-to-server flow.  On
 * the client we go through Next.js route handlers under `/api/*` so the
 * browser never sees the API base URL or cross-origin cookies.
 */

import "server-only";

import { z } from "zod";

const ApiBase =
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API ${status}`);
  }
}

export async function api<T>(
  path: string,
  init: RequestInit & { schema: z.ZodType<T> },
): Promise<T> {
  const url = path.startsWith("http") ? path : `${ApiBase}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  const body = await safeJson(res);
  if (!res.ok) throw new ApiError(res.status, body);
  return init.schema.parse(body);
}

async function safeJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// ---------------------------------------------------------------- schemas
export const OrgSchema = z.object({
  id: z.string().uuid(),
  slug: z.string(),
  name: z.string(),
  country_code: z.string(),
  timezone: z.string(),
  status: z.string(),
  created_at: z.string(),
});
export type Org = z.infer<typeof OrgSchema>;

export const StoreSchema = z.object({
  id: z.string().uuid(),
  org_id: z.string().uuid(),
  slug: z.string(),
  name: z.string(),
  brand_name: z.string(),
  platform: z.string(),
  timezone: z.string(),
  currency: z.string(),
  wa_provider: z.string(),
  wa_phone_number_id: z.string().nullable(),
  voice_enabled: z.boolean(),
  voice_caller_id: z.string().nullable(),
  per_conversation_cost_cap_usd: z.number(),
  per_call_cost_cap_usd: z.number(),
  monthly_budget_usd: z.number().nullable(),
  status: z.string(),
  created_at: z.string(),
  agent_config: z.record(z.unknown()),
});
export type Store = z.infer<typeof StoreSchema>;

export const ConversationSchema = z.object({
  id: z.string().uuid(),
  channel: z.enum(["whatsapp", "voice", "sms"]),
  state: z.string(),
  outcome: z.string().nullable(),
  outcome_reason: z.string().nullable(),
  cost_usd: z.number(),
  tokens_input: z.number(),
  tokens_output: z.number(),
  opened_at: z.string(),
  closed_at: z.string().nullable(),
  last_inbound_at: z.string().nullable(),
  last_outbound_at: z.string().nullable(),
});
export type Conversation = z.infer<typeof ConversationSchema>;

export const OrderSchema = z.object({
  id: z.string().uuid(),
  external_order_id: z.string(),
  customer_phone_masked: z.string(),
  customer_name_masked: z.string().nullable(),
  confirmation_status: z.string(),
  attempt_count: z.number(),
  next_attempt_at: z.string().nullable(),
  total: z.string().or(z.number()),
  currency: z.string(),
  placed_at: z.string(),
  tags: z.array(z.string()),
});
export type Order = z.infer<typeof OrderSchema>;
