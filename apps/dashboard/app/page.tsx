import Link from "next/link";

export default function MarketingHome() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col items-start justify-center gap-8 px-6">
      <span className="rounded-full bg-brand-100 px-3 py-1 text-sm font-medium text-brand-700">
        Awaaz · Conversational Urdu AI for Pakistan
      </span>
      <h1 className="text-5xl font-bold leading-tight tracking-tight">
        WhatsApp-first COD confirmation,
        <br />
        in real Urdu, at scale.
      </h1>
      <p className="max-w-2xl text-lg text-slate-600">
        Awaaz handles confirmation, cancellation, rescheduling, change requests
        and escalation over WhatsApp Business — and optionally voice — for
        Pakistani e-commerce merchants. Built for Shopify, WooCommerce and any
        custom checkout.
      </p>
      <div className="flex gap-3">
        <Link
          href="/sign-up"
          className="rounded-lg bg-brand-600 px-5 py-3 font-semibold text-white shadow-sm hover:bg-brand-700"
        >
          Get started
        </Link>
        <Link
          href="/sign-in"
          className="rounded-lg border border-slate-300 bg-white px-5 py-3 font-semibold text-slate-700 hover:bg-slate-100"
        >
          Sign in
        </Link>
      </div>
    </main>
  );
}
