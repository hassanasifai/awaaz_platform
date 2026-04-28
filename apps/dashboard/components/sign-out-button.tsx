"use client";

import { useRouter } from "next/navigation";

import { signOut } from "@/lib/auth-client";

export function SignOutButton() {
  const router = useRouter();
  return (
    <button
      onClick={async () => {
        await signOut();
        router.push("/sign-in");
      }}
      className="rounded-md border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
    >
      Sign out
    </button>
  );
}
