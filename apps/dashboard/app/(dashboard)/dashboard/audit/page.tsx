import { requireSession } from "@/lib/session";

export default async function AuditPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Audit log</h1>
      <p className="text-slate-600">
        Every operator action and system event is recorded here. Retained for
        90 days by default.
      </p>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
        Empty.
      </div>
    </div>
  );
}
