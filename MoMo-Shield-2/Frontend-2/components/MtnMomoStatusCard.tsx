'use client';

import useSWR from 'swr';
import { Activity, CircleCheck, CircleHelp, Radio } from 'lucide-react';
import { Badge, Card } from '@/components/ui/primitives';
import { apiBase, type MtnMomoStatus } from '@/lib/api';

const fetchStatus = async (url: string): Promise<MtnMomoStatus> => {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`Provider status unavailable (${response.status})`);
  return response.json() as Promise<MtnMomoStatus>;
};

export function MtnMomoStatusCard() {
  const { data, error, isLoading } = useSWR(
    `${apiBase()}/api/v1/integrations/mtn-momo/status`,
    fetchStatus,
    { refreshInterval: 30_000, revalidateOnFocus: true },
  );
  const ready = data?.ready === true;
  const providerConfigured = data?.configured === true;
  const state = isLoading
    ? 'Checking backend…'
    : error
    ? 'Backend unreachable (using fallback simulation)'
    : ready
    ? 'MTN MoMo Sandbox integration ready'
    : providerConfigured
    ? 'Request API key missing'
    : 'Provider credentials simulated (ready for keys)';

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[.08] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-[#ffcc00]/15 text-[#ffcc00]">
            <Radio size={17} />
          </div>
          <div>
            <p className="text-xs font-bold text-white">MTN MoMo OpenAPI Gateway</p>
            <p className="mt-0.5 text-[11px] text-slate-400">Collection &amp; Request-to-Pay API</p>
          </div>
        </div>
        <Badge variant={ready ? 'success' : 'medium'}>{data?.environment ?? 'SANDBOX READY'}</Badge>
      </div>

      <div className="p-6">
        <div className="flex items-center gap-2.5 text-xs font-bold text-white" role="status" aria-live="polite">
          {ready ? <CircleCheck size={16} className="text-emerald-400" /> : <CircleHelp size={16} className="text-amber-400" />}
          {state}
        </div>
        <p className="mt-2 text-xs leading-relaxed text-slate-300">
          {error
            ? 'The Intelligence Core is in standalone offline mock mode. Payment collection requests remain simulated.'
            : providerConfigured
            ? 'Backend credentials configured. Transaction interception and verification operates against MTN Developer Sandbox.'
            : 'Configure MTN_MOMO_API_USER and MTN_MOMO_API_KEY in the backend environment to enable live sandbox disbursement verification.'}
        </p>

        <div className="mt-5 grid gap-2.5 border-t border-white/[.07] pt-4 text-xs font-medium sm:grid-cols-2">
          <span className="flex items-center gap-2 text-slate-300">
            <Activity size={13} className="text-[#ffcc00]" />
            Endpoints: RequestToPay &amp; Status Polling
          </span>
          <span className="text-slate-400">
            Idempotency: UUID v4 Header Enforced
          </span>
        </div>
      </div>
    </Card>
  );
}
