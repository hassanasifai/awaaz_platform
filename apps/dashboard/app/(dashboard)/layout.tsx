import Link from "next/link";

import { requireSession } from "@/lib/session";
import { SignOutButton } from "@/components/sign-out-button";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/conversations", label: "Conversations" },
  { href: "/dashboard/orders", label: "Orders" },
  { href: "/dashboard/calls", label: "Calls" },
  { href: "/dashboard/stores", label: "Stores" },
  { href: "/dashboard/analytics", label: "Analytics" },
  { href: "/dashboard/integrations", label: "Integrations" },
  { href: "/dashboard/billing", label: "Billing" },
  { href: "/dashboard/audit", label: "Audit" },
  { href: "/dashboard/team", label: "Team" },
] as const;

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await requireSession();

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white p-4 lg:block">
        <Link href="/dashboard" className="mb-8 block text-xl font-bold">
          Awaaz
        </Link>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <span className="text-sm text-slate-500">
            Signed in as <strong>{session.user.email}</strong>
          </span>
          <SignOutButton />
        </header>
        <div className="px-6 py-8">{children}</div>
      </main>
    </div>
  );
}
