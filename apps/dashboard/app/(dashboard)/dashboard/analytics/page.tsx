import { requireSession } from "@/lib/session";

export default async function AnalyticsPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Analytics</h1>
      <p className="text-slate-600">
        Confirmation rate, fake-order rate, peak hours, cost per outcome —
        per store and per agent version.
      </p>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
        Charts populate after first 24 h of conversations.
      </div>
    </div>
  );
}
