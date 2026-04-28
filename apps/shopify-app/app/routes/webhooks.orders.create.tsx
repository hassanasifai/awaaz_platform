import type { ActionFunctionArgs } from "@remix-run/node";

import { authenticate } from "../shopify.server";

/**
 * Inbound `orders/create` webhook from Shopify.  Shopify's middleware verifies
 * HMAC-SHA256.  We then forward to Awaaz with our own signed payload so the
 * control plane can ingest and dispatch a WhatsApp message.
 */
export const action = async ({ request }: ActionFunctionArgs) => {
  const { shop, topic, payload } = await authenticate.webhook(request);

  const awaazApi = process.env.AWAAZ_API_BASE_URL ?? "http://localhost:8000";
  const sharedSecret = process.env.AWAAZ_SHARED_SECRET ?? "";

  const body = JSON.stringify({ shop, topic, payload });
  const signature = await sign(body, sharedSecret);

  const res = await fetch(`${awaazApi}/v1/integrations/shopify/orders/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Awaaz-Signature": `sha256=${signature}`,
    },
    body,
  });

  if (!res.ok) {
    return new Response("forward failed", { status: 502 });
  }
  return new Response();
};

async function sign(payload: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
