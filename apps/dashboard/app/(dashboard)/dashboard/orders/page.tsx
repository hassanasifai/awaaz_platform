import { requireSession } from "@/lib/session";

export default async function OrdersPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Orders</h1>
      <p className="text-slate-600">
        COD orders by status. PII (phone, name, address) is masked here; full
        plaintext is only shown to operators with elevated roles inside an
        order detail page.
      </p>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
        Connect a Shopify or WooCommerce store, or POST to{" "}
        <code className="rounded bg-slate-100 px-2 py-1 font-mono text-xs">
          /v1/orders/intake
        </code>
        .
      </div>
    </div>
  );
}
