"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { toast } from "sonner";

export default function NewStorePage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const res = await fetch("/api/stores", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(await res.text());
      const created = await res.json();
      toast.success("Store created");
      router.push(`/dashboard/stores/${created.id}`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="max-w-xl space-y-5">
      <h1 className="text-3xl font-bold">New store</h1>
      <Field label="Store name" name="name" required />
      <Field label="Brand name (used in WA messages)" name="brand_name" required />
      <Field
        label="Slug"
        name="slug"
        required
        pattern="[a-z0-9][a-z0-9-]*"
        help="lowercase, dashes, used in URLs"
      />
      <label className="block">
        <span className="block text-sm font-medium">Platform</span>
        <select
          name="platform"
          required
          className="mt-1 block w-full rounded-md border-slate-300"
        >
          <option value="manual">Manual / generic webhook</option>
          <option value="shopify">Shopify</option>
          <option value="woocommerce">WooCommerce</option>
          <option value="custom">Custom</option>
        </select>
      </label>
      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-brand-600 px-5 py-2 font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {submitting ? "Creating…" : "Create"}
      </button>
    </form>
  );
}

function Field(props: {
  label: string;
  name: string;
  required?: boolean;
  pattern?: string;
  help?: string;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium">{props.label}</span>
      <input
        name={props.name}
        required={props.required}
        pattern={props.pattern}
        className="mt-1 block w-full rounded-md border-slate-300"
      />
      {props.help ? <span className="mt-1 block text-xs text-slate-500">{props.help}</span> : null}
    </label>
  );
}
