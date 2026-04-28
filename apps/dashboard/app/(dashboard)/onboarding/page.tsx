import Link from "next/link";

import { requireSession } from "@/lib/session";

export default async function OnboardingPage() {
  await requireSession();
  return (
    <main className="mx-auto max-w-3xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Welcome to Awaaz</h1>
      <ol className="space-y-4">
        <Step n={1} title="Create your organization">
          A workspace for your team. <Link href="/dashboard" className="text-brand-700">Skip if you've already created one →</Link>
        </Step>
        <Step n={2} title="Add your first store">
          Each store has its own WA Cloud API phone number and agent prompt.{" "}
          <Link href="/dashboard/stores/new" className="text-brand-700">Add store →</Link>
        </Step>
        <Step n={3} title="Connect WhatsApp Business">
          Paste your Meta WA access token, phone-number-id, business-account-id and app secret in the store settings.
        </Step>
        <Step n={4} title="Submit your utility template">
          We use{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs">order_confirmation_v1</code>{" "}
          by default. Approval takes ~5–10 min.
        </Step>
        <Step n={5} title="Send a test conversation">
          From the store page, hit <strong>Test conversation</strong> and enter your own phone.
        </Step>
      </ol>
    </main>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-4 rounded-lg border border-slate-200 bg-white p-4">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
        {n}
      </span>
      <div>
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-slate-600">{children}</p>
      </div>
    </li>
  );
}
