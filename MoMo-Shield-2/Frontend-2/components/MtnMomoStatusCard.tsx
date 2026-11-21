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
  const state = isLoading ? 'Checking backend' : error ? 'Backend unreachable' : ready ? 'Sandbox integration ready' : providerConfigured ? 'Request API key missing' : 'Provider credentials missing';

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[.06] px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#ffcc00]/[.09] text-[#ffcc00]"><Radio size={15} /></div>
          <div>
            <p className="text-[11px] font-semibold text-slate-200">MTN MoMo Collection</p>
            <p className="mt-1 text-[9px] text-slate-600">Provider status from Intelligence Core</p>
          </div>
        </div>
        <Badge variant={ready ? 'success' : 'medium'}>{data?.environment ?? 'SANDBOX'}</Badge>
      </div>
      <div className="p-5">
        <div className="flex items-center gap-2 text-[10px] font-medium text-slate-300" role="status" aria-live="polite">
          {ready ? <CircleCheck size={14} className="text-emerald-400" /> : <CircleHelp size={14} className="text-amber-400" />}
          {state}
        </div>
        <p className="mt-2 text-[9px] leading-relaxed text-slate-500">
          {error
            ? 'The backend did not return provider status. No connection is assumed.'
            : providerConfigured
              ? 'Backend credentials are present. Payment requests remain sandbox-only and require an authenticated explicit action.'
              : 'Add the MTN API user, API key, subscription key, and request API key to the backend environment. Secrets are never sent to this browser.'}
        </p>
        <div className="mt-4 grid gap-2 border-t border-white/[.06] pt-4 text-[9px] sm:grid-cols-2">
          <span className="flex items-center gap-1.5 text-slate-500"><Activity size={11} />Payment API: RequestToPay + status</span>
          <span className="text-slate-500">Not an SMS/USSD/voice signal feed</span>
        </div>
      </div>
    </Card>
  );
}
