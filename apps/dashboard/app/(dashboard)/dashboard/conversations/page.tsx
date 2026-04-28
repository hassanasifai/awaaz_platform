import { Suspense } from "react";

import { requireSession } from "@/lib/session";

export default async function ConversationsPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Conversations</h1>
      <p className="text-slate-600">
        WhatsApp / voice / SMS threads, filterable by store, channel, and outcome.
      </p>
      <Suspense fallback={<p className="text-slate-500">Loading…</p>}>
        <ConversationsTable />
      </Suspense>
    </div>
  );
}

async function ConversationsTable() {
  // Once a store is selected, fetch via the BFF route.  Until then we render
  // an empty state so the page is useful pre-onboarding.
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
      Select a store from the picker to load conversations.
    </div>
  );
}
