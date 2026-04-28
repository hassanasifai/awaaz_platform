import { requireSession } from "@/lib/session";

export default async function IntegrationsPage() {
  await requireSession();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Integrations</h1>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <IntegrationCard
          name="Shopify"
          description="Public OAuth app — auto-sync orders, tag back outcomes."
          status="Available"
        />
        <IntegrationCard
          name="WooCommerce"
          description="WP plugin — paste API key, sync new orders."
          status="Available"
        />
        <IntegrationCard
          name="WhatsApp Business Cloud (Meta)"
          description="Direct integration. No BSP markup."
          status="Required"
        />
        <IntegrationCard
          name="360dialog"
          description="WA BSP alternative."
          status="Available"
        />
        <IntegrationCard
          name="Twilio (voice)"
          description="MVP voice telephony — $0.18/min PK mobile."
          status="Optional"
        />
        <IntegrationCard
          name="PTCL / Nayatel SIP"
          description="Production voice trunk — ~Rs 2/min."
          status="Optional"
        />
      </div>
    </div>
  );
}

function IntegrationCard({
  name,
  description,
  status,
}: {
  name: string;
  description: string;
  status: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{name}</h3>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{status}</span>
      </div>
      <p className="mt-2 text-sm text-slate-600">{description}</p>
    </div>
  );
}
