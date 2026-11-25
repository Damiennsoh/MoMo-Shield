'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Network, FileDown, Radar } from 'lucide-react';
import { Card, Badge } from '@/components/ui/primitives';
import {
  fetchEvidencePack,
  fetchFundFlow,
  type FundFlowEdge,
  type FundFlowGraph,
  type FundFlowNode,
} from '@/lib/api';

const ROLE_COLORS: Record<string, string> = {
  suspect: '#dc2626',
  mule: '#ea580c',
  collector: '#f59e0b',
  caller: '#8b5cf6',
  payer: '#0ea5e9',
  node: '#64748b',
};

const KIND_LABELS: Record<string, string> = {
  sms: 'SMS',
  call: 'Call',
  payment: 'Payment',
  payment_request: 'Req',
  switch: 'Switch',
  bank_transfer: 'Bank',
};

const MAX_NODES = 10;
const CX = 260;
const CY = 155;

function maskMsisdn(msisdn: string): string {
  const digits = msisdn.replace(/\D/g, '');
  if (digits.length < 7) return msisdn;
  return `${digits.slice(0, 5)} ••• ${digits.slice(-4)}`;
}

function nodePositions(nodes: FundFlowNode[]): Map<string, { x: number; y: number }> {
  const pos = new Map<string, { x: number; y: number }>();
  if (nodes.length === 0) return pos;
  const sorted = [...nodes].sort((a, b) => b.in_count + b.out_count - (a.in_count + a.out_count));
  pos.set(sorted[0].id, { x: CX, y: CY });
  const rest = sorted.slice(1);
  rest.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(rest.length, 1) - Math.PI / 2;
    pos.set(n.id, {
      x: CX + 195 * Math.cos(angle),
      y: CY + 105 * Math.sin(angle),
    });
  });
  return pos;
}

function edgeLabel(edge: FundFlowEdge): string {
  if (edge.amount) return `GH₵ ${edge.amount.toLocaleString()}`;
  return KIND_LABELS[edge.kind] ?? edge.kind;
}

export function FraudGraph() {
  const [graph, setGraph] = useState<FundFlowGraph | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [packBusy, setPackBusy] = useState(false);
  const [packNote, setPackNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setGraph(await fetchFundFlow());
    } catch {
      /* backend unreachable — keep last snapshot */
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  const { nodes, edges, positions } = useMemo(() => {
    const allNodes = graph?.nodes ?? [];
    const allEdges = graph?.edges ?? [];
    const top = [...allNodes]
      .sort((a, b) => b.in_count + b.out_count - (a.in_count + a.out_count))
      .slice(0, MAX_NODES);
    const ids = new Set(top.map((n) => n.id));
    return {
      nodes: top,
      edges: allEdges.filter((e) => ids.has(e.from) && ids.has(e.to)),
      positions: nodePositions(top),
    };
  }, [graph]);

  const selected = nodes.find((n) => n.id === selectedId) ?? null;
  const selectedEdges = useMemo(
    () => edges.filter((e) => e.from === selectedId || e.to === selectedId).slice(-8),
    [edges, selectedId],
  );

  const downloadEvidencePack = async () => {
    if (!selected) return;
    setPackBusy(true);
    setPackNote(null);
    try {
      const pack = await fetchEvidencePack(selected.id);
      const blob = new Blob([JSON.stringify(pack, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `momo-shield-evidence-${selected.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setPackNote(
        `Pack exported — ${pack.incident_summary.observed_edges} observed edges, ` +
        `GH₵ ${pack.incident_summary.observed_value_ghs.toLocaleString()} traced.`,
      );
    } catch {
      setPackNote('Evidence pack unavailable — backend unreachable.');
    } finally {
      setPackBusy(false);
    }
  };

  const flaggedCount = nodes.filter((n) => n.flagged).length;

  return (
    <Card id="campaigns" className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[.08] px-5 py-4">
        <div className="flex items-center gap-2.5">
          <Network size={16} className="text-[#ffcc00]" />
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-white">
            Fund-Flow Intelligence
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {flaggedCount > 0 && <Badge variant="high">{flaggedCount} FLAGGED</Badge>}
          <Badge variant={nodes.length ? 'low' : 'low'}>{graph?.edge_count ?? 0} edges</Badge>
        </div>
      </div>

      <div className="p-4 sm:p-5">
        <div className="relative w-full rounded-xl border border-white/[.08] bg-[#070b10] p-2 overflow-hidden shadow-inner">
          <svg viewBox="0 0 520 310" className="w-full h-auto max-h-[300px]">
            <defs>
              <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.6" />
                <stop offset="100%" stopColor="#ffcc00" stopOpacity="0.4" />
              </linearGradient>
            </defs>

            {edges.map((edge, i) => {
              const a = positions.get(edge.from);
              const b = positions.get(edge.to);
              if (!a || !b) return null;
              const blocked = ['REJECT', 'BLOCKED', 'DELAY'].includes(edge.decision);
              return (
                <g key={`${edge.from}-${edge.to}-${i}`}>
                  <line
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={blocked ? '#ef4444' : 'url(#edgeGrad)'}
                    strokeWidth={blocked ? 2.4 : 1.6}
                    strokeDasharray="4 3"
                    strokeOpacity={blocked ? 0.95 : 0.55}
                  />
                  <text
                    x={(a.x + b.x) / 2}
                    y={(a.y + b.y) / 2 - 5}
                    fill="#94a3b8"
                    fontSize="9"
                    fontFamily="monospace"
                    textAnchor="middle"
                  >
                    {edgeLabel(edge)}
                  </text>
                </g>
              );
            })}

            {nodes.map((node) => {
              const pos = positions.get(node.id);
              if (!pos) return null;
              const isSelected = selectedId === node.id;
              const fill = ROLE_COLORS[node.role] ?? ROLE_COLORS.node;
              const degree = node.in_count + node.out_count;
              const r = Math.min(8 + degree, 16);
              return (
                <g
                  key={node.id}
                  onClick={() => setSelectedId(node.id)}
                  className="cursor-pointer"
                >
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={isSelected ? r + 5 : r + 2}
                    fill={fill}
                    fillOpacity={isSelected ? 0.4 : 0.18}
                    stroke={fill}
                    strokeWidth={isSelected ? 2.5 : 1.4}
                  />
                  <circle cx={pos.x} cy={pos.y} r={Math.max(r - 3, 4)} fill={fill} />
                  <text
                    x={pos.x}
                    y={pos.y + r + 14}
                    fill="#f1f5f9"
                    fontSize="9"
                    fontWeight="bold"
                    textAnchor="middle"
                    className="pointer-events-none drop-shadow-md"
                  >
                    {maskMsisdn(node.id)}
                  </text>
                  <text
                    x={pos.x}
                    y={pos.y + r + 25}
                    fill={node.flagged ? '#f87171' : '#64748b'}
                    fontSize="8"
                    textAnchor="middle"
                    className="pointer-events-none"
                  >
                    {node.role.toUpperCase()}
                    {node.flagged ? ' · LEDGER' : ''}
                  </text>
                </g>
              );
            })}

            {nodes.length === 0 && (
              <text
                x={CX}
                y={CY}
                fill="#475569"
                fontSize="12"
                textAnchor="middle"
              >
                No observed relationships yet — plug-in events populate this map.
              </text>
            )}
          </svg>
        </div>

        {selected && (
          <div className="mt-3.5 space-y-2 rounded-xl border border-white/[.1] bg-white/[.03] p-3.5 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[.08] pb-2">
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: ROLE_COLORS[selected.role] ?? '#64748b' }}
                />
                <span className="font-mono text-sm font-bold text-white">{selected.id}</span>
                <span className="rounded bg-white/[.06] px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-400">
                  {selected.role}
                </span>
                {selected.flagged && <Badge variant="high">THREAT LEDGER</Badge>}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-400">
                  {selected.in_count} in / {selected.out_count} out · GH₵ {selected.volume.toLocaleString()}
                </span>
                <button
                  type="button"
                  onClick={() => void downloadEvidencePack()}
                  disabled={packBusy}
                  className="flex items-center gap-1.5 rounded-lg border border-[#ffcc00]/40 bg-[#ffcc00]/10 px-2.5 py-1 text-[10px] font-bold text-[#ffcc00] transition hover:bg-[#ffcc00]/20 disabled:opacity-50"
                >
                  <FileDown size={11} />
                  {packBusy ? 'Building…' : 'Evidence Pack'}
                </button>
              </div>
            </div>
            <p className="text-[11px] leading-relaxed text-slate-300">
              <strong className="font-semibold text-[#ffcc00]">Observed traffic: </strong>
              {selected.kinds.join(', ') || 'none'} · {selected.pay_in} payment hops in,{' '}
              {selected.pay_out} out
              {selected.ledger_reports > 0 && ` · ${selected.ledger_reports} ledger confirmations`}
            </p>
            {selectedEdges.length > 0 && (
              <div className="space-y-1">
                {selectedEdges.map((e, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-md bg-white/[.02] px-2 py-1 font-mono text-[9px] text-slate-400"
                  >
                    <span>
                      {maskMsisdn(e.from === selected.id ? e.to : e.from)} · {KIND_LABELS[e.kind] ?? e.kind}
                    </span>
                    <span>
                      {e.amount ? `GH₵ ${e.amount}` : ''} {e.decision}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {packNote && <p className="text-[10px] text-emerald-300">{packNote}</p>}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-white/[.07] pt-2.5 text-[10px] text-slate-400">
          <div className="flex flex-wrap items-center gap-3">
            {Object.entries(ROLE_COLORS).map(([role, color]) => (
              <span key={role} className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full" style={{ background: color }} />
                {role}
              </span>
            ))}
          </div>
          <span className="flex items-center gap-1">
            <Radar size={10} /> Live plug-in telemetry · click a node for its evidence pack
          </span>
        </div>
      </div>
    </Card>
  );
}
