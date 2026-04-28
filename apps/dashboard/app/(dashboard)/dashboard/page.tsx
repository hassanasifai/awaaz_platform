import { Card } from "@/components/card";

export default async function DashboardOverview() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Overview</h1>
      <p className="max-w-prose text-slate-600">
        Real-time stats appear once you connect a store and run your first
        conversation. Use <strong>Stores → New store</strong> to get started.
      </p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card title="Conversations (24h)" value="—" hint="WhatsApp + voice + SMS" />
        <Card title="Confirmation rate" value="—" hint="confirmed / total" />
        <Card title="Avg cost / conv" value="—" hint="USD" />
        <Card title="Open escalations" value="—" hint="merchant queue" />
      </div>
    </div>
  );
}
