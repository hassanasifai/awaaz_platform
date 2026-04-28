import { requireSession } from "@/lib/session";

export default async function CallsPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Calls</h1>
      <p className="text-slate-600">
        Voice channel — only active when a store has{" "}
        <code className="rounded bg-slate-100 px-2 py-1 font-mono text-xs">voice_enabled</code>{" "}
        set and PTA-allocated CLI numbers configured.
      </p>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
        No calls yet.
      </div>
    </div>
  );
}
