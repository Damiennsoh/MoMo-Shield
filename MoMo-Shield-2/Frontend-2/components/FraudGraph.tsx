import { Network } from 'lucide-react';
import { Card } from '@/components/ui/primitives';

export function FraudGraph() {
  return (
    <Card id="campaigns" className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-white/[.06] px-5 py-4">
        <Network size={14} className="text-[#ffcc00]" />
        <h2 className="text-[12px] font-semibold text-slate-100">Fraud network map</h2>
      </div>
      <div className="grid min-h-[260px] place-items-center px-6 py-10 text-center sm:min-h-[300px]">
        <div role="status" className="max-w-xs">
          <Network size={24} className="mx-auto text-slate-500" aria-hidden="true" />
          <p className="mt-3 text-[11px] font-medium text-slate-300">Relationship data not received</p>
          <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500">Linked-account analysis will appear when the connected backend supplies verified graph data.</p>
        </div>
      </div>
    </Card>
  );
}
