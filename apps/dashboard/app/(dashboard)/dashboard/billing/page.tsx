import { requireSession } from "@/lib/session";

export default async function BillingPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Billing</h1>
      <p className="text-slate-600">
        Per-conversation usage is reported to Stripe hourly. Cost cap defaults
        to $0.05 / conversation; configure higher in store settings if needed.
      </p>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
        Connect Stripe in <code>.env</code> to see usage records.
      </div>
    </div>
  );
}
