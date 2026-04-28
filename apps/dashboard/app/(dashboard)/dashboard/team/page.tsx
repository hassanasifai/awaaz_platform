import { requireSession } from "@/lib/session";

export default async function TeamPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Team</h1>
      <p className="text-slate-600">
        Invite admins, operators, and viewers to your organization.
      </p>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
        You are the only member so far.
      </div>
    </div>
  );
}
