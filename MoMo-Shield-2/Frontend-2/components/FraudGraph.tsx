import { Expand, Network, RotateCcw } from 'lucide-react';
import { Badge } from '@/components/ui/primitives';

const nodes = [
  { x: 210, y: 150, r: 18, kind: 'bad' }, { x: 108, y: 84, r: 13, kind: 'bad' }, { x: 316, y: 83, r: 12, kind: 'bad' },
  { x: 348, y: 184, r: 11, kind: 'bad' }, { x: 103, y: 220, r: 10, kind: 'bad' }, { x: 250, y: 51, r: 8, kind: 'bad' },
  { x: 210, y: 264, r: 8, kind: 'user' }, { x: 43, y: 147, r: 7, kind: 'user' }, { x: 390, y: 116, r: 7, kind: 'user' },
  { x: 291, y: 244, r: 6, kind: 'user' }, { x: 151, y: 41, r: 6, kind: 'user' }, { x: 52, y: 263, r: 6, kind: 'user' },
  { x: 315, y: 31, r: 6, kind: 'user' }, { x: 390, y: 257, r: 5, kind: 'user' },
];
const edges = [[0,1],[0,2],[0,3],[0,4],[1,5],[2,5],[2,8],[3,9],[4,11],[1,7],[3,13],[5,12],[0,6],[2,9],[4,6]];
export function FraudGraph() {
  return <div id="campaigns" className="overflow-hidden rounded-2xl border border-white/[.07] bg-[#0b1118]">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[.06] px-5 py-4"><div><div className="flex items-center gap-2"><Network size={14} className="text-[#ffcc00]" /><h2 className="text-[12px] font-semibold text-slate-100">Fraud network map</h2><Badge variant="outline">LIVE GRAPH</Badge></div><p className="mt-1.5 text-[10px] text-slate-500">Shared identifiers across flagged mobile money accounts</p></div><div className="flex items-center gap-2"><span className="hidden items-center gap-1.5 text-[9px] text-slate-500 sm:flex"><i className="h-1.5 w-1.5 rounded-full bg-rose-400" />Suspected ring <i className="ml-2 h-1.5 w-1.5 rounded-full bg-emerald-400" />Victim node</span><button aria-label="Refresh graph" className="grid h-7 w-7 place-items-center rounded-md border border-white/[.07] text-slate-500"><RotateCcw size={12} /></button><button aria-label="Expand graph" className="hidden h-7 w-7 place-items-center rounded-md border border-white/[.07] text-slate-500 sm:grid"><Expand size={12} /></button></div></div>
    <div className="panel-grid relative h-[260px] sm:h-[300px]"><svg viewBox="0 0 430 300" preserveAspectRatio="xMidYMid meet" className="h-full w-full">
      <defs><radialGradient id="ringGlow"><stop stopColor="#fb5263" stopOpacity=".19" /><stop offset="1" stopColor="#fb5263" stopOpacity="0" /></radialGradient><filter id="nodeGlow"><feGaussianBlur stdDeviation="4" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
      <circle cx="211" cy="150" r="112" fill="url(#ringGlow)" />
      {edges.map(([a,b], idx) => { const start = nodes[a], end = nodes[b], red = start.kind === 'bad' && end.kind === 'bad'; return <line key={idx} x1={start.x} y1={start.y} x2={end.x} y2={end.y} stroke={red ? '#fa596a' : '#667989'} strokeOpacity={red ? '.48' : '.24'} strokeWidth={red ? 1.5 : 1} strokeDasharray={red ? '0' : '3 5'} />; })}
      {nodes.map((node, idx) => <g key={idx} className="graph-node"><circle cx={node.x} cy={node.y} r={node.r + 9} fill={node.kind === 'bad' ? 'url(#ringGlow)' : 'transparent'} /><circle cx={node.x} cy={node.y} r={node.r} fill={node.kind === 'bad' ? '#43202a' : '#11332e'} stroke={node.kind === 'bad' ? '#fb6474' : '#43d6a2'} strokeWidth={node.r > 10 ? 1.6 : 1.2} filter={node.r > 10 ? 'url(#nodeGlow)' : ''} /><circle cx={node.x} cy={node.y} r={2.5} fill={node.kind === 'bad' ? '#ff8793' : '#68efbd'} />{idx === 0 && <text x={node.x} y={node.y + 34} textAnchor="middle" fill="#e8b5bc" fontSize="8" fontFamily="monospace">RING-024</text>}</g>)}
    </svg><div className="absolute bottom-3 left-3 rounded-lg border border-white/[.07] bg-[#0b1118]/90 px-3 py-2 backdrop-blur"><p className="text-[8px] uppercase tracking-[.12em] text-slate-600">Cluster confidence</p><p className="mt-1 font-mono text-[12px] font-semibold text-rose-300">96.8% <span className="text-[9px] font-normal text-slate-600">· 7 linked nodes</span></p></div><div className="absolute right-3 top-3 rounded-md border border-rose-400/15 bg-rose-400/[.06] px-2 py-1 text-[8px] font-semibold uppercase tracking-[.12em] text-rose-300"><span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-rose-400" />Ring activity detected</div></div>
  </div>;
}
