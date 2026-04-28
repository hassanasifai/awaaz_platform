import Link from "next/link";

import { requireSession } from "@/lib/session";

export default async function StoresPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Stores</h1>
        <Link
          href="/dashboard/stores/new"
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        >
          + New store
        </Link>
      </div>
      <p className="text-slate-600">
        Each store has its own WhatsApp Cloud API phone number, voice provider,
        and agent prompt overrides. PII is encrypted per-org via a dedicated
        KMS CMK.
      </p>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
        No stores yet — create your first one.
      </div>
    </div>
  );
}
