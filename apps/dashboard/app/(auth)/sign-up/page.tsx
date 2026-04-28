"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { toast } from "sonner";

import { signUp } from "@/lib/auth-client";

export default function SignUpPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    const data = new FormData(event.currentTarget);
    const result = await signUp.email({
      email: String(data.get("email") ?? ""),
      password: String(data.get("password") ?? ""),
      name: String(data.get("name") ?? ""),
    });
    setSubmitting(false);
    if (result?.error) {
      toast.error(result.error.message ?? "Sign-up failed");
      return;
    }
    router.push("/onboarding");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="mb-1 text-3xl font-bold">Create your workspace</h1>
      <p className="mb-8 text-slate-600">
        Awaaz takes ~5 minutes to set up after this.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Your name" name="name" type="text" required autoComplete="name" />
        <Field label="Email" name="email" type="email" required autoComplete="email" />
        <Field
          label="Password"
          name="password"
          type="password"
          required
          minLength={12}
          autoComplete="new-password"
          help="Minimum 12 characters."
        />
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-brand-600 px-4 py-2 font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {submitting ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        Already on Awaaz?{" "}
        <Link href="/sign-in" className="font-semibold text-brand-700">
          Sign in
        </Link>
      </p>
    </main>
  );
}

function Field(props: {
  label: string;
  name: string;
  type: string;
  required?: boolean;
  minLength?: number;
  autoComplete?: string;
  help?: string;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium">{props.label}</span>
      <input
        name={props.name}
        type={props.type}
        required={props.required}
        minLength={props.minLength}
        autoComplete={props.autoComplete}
        className="mt-1 block w-full rounded-md border-slate-300"
      />
      {props.help ? <span className="mt-1 block text-xs text-slate-500">{props.help}</span> : null}
    </label>
  );
}
