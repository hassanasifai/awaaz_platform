/**
 * Shopify app server-side instance.
 *
 * Webhook validation is handled by `shopifyApp` itself (HMAC-SHA256 against
 * the X-Shopify-Hmac-Sha256 header), so our route handlers can focus on
 * forwarding the verified payload to the Awaaz control plane.
 */

import "@shopify/shopify-app-remix/adapters/node";
import {
  ApiVersion,
  AppDistribution,
  shopifyApp,
} from "@shopify/shopify-app-remix/server";
import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";

export const shopify = shopifyApp({
  apiKey: process.env.SHOPIFY_API_KEY!,
  apiSecretKey: process.env.SHOPIFY_API_SECRET!,
  apiVersion: ApiVersion.January26,
  scopes: process.env.SHOPIFY_SCOPES?.split(",") ?? [
    "read_orders",
    "write_orders",
    "read_customers",
    "read_products",
  ],
  appUrl: process.env.SHOPIFY_APP_URL ?? "https://app.awaaz.pk",
  authPathPrefix: "/auth",
  sessionStorage: new PrismaSessionStorage(/* configured at boot */ {} as any),
  distribution: AppDistribution.AppStore,
  isEmbeddedApp: true,
  future: {
    unstable_newEmbeddedAuthStrategy: true,
  },
  hooks: {
    afterAuth: async ({ session }) => {
      // Forward the new install to Awaaz so a Store row exists.
      await fetch(`${process.env.AWAAZ_API_BASE_URL}/v1/integrations/shopify/install`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Awaaz-Signature": "via-shared-secret",
        },
        body: JSON.stringify({
          shop_domain: session.shop,
          access_token: session.accessToken,
          scope: session.scope,
        }),
      });
    },
  },
});

export const authenticate = shopify.authenticate;
export const unauthenticated = shopify.unauthenticated;
export const login = shopify.login;
export const registerWebhooks = shopify.registerWebhooks;
export const sessionStorage = shopify.sessionStorage;
