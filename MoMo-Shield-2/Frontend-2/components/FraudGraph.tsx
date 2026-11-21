'use client';

import { useState } from 'react';
import { Network, ShieldAlert, Users, Radio, ArrowUpRight } from 'lucide-react';
import { Card, Badge } from '@/components/ui/primitives';

interface Node {
  id: string;
  label: string;
  type: 'syndicate' | 'mule' | 'victim' | 'caller';
  x: number;
  y: number;
  risk: number;
}

interface Edge {
  from: string;
  to: string;
  label: string;
}

const NODES: Node[] = [
  { id: 'S1', label: 'Syndicate Hub (Kumasi)', type: 'syndicate', x: 260, y: 70, risk: 96 },
  { id: 'M1', label: 'Mule Wallet · +23324***890', type: 'mule', x: 130, y: 150, risk: 88 },
  { id: 'M2', label: 'Cash-out Agent · Circle', type: 'mule', x: 390, y: 140, risk: 82 },
  { id: 'C1', label: 'Nuisance Caller · +23355***102', type: 'caller', x: 100, y: 250, risk: 78 },
  { id: 'V1', label: 'Victim Subscriber (Sandbox)', type: 'victim', x: 260, y: 230, risk: 15 },
  { id: 'M3', label: 'Secondary Wallet · +23320***441', type: 'mule', x: 410, y: 240, risk: 70 },
];

const EDGES: Edge[] = [
  { from: 'S1', to: 'M1', label: 'GHS 2,500' },
  { from: 'S1', to: 'M2', label: 'GHS 1,800' },
  { from: 'M1', to: 'V1', label: 'Fake Credit' },
  { from: 'C1', to: 'V1', label: 'Urgent Call' },
  { from: 'M2', to: 'M3', label: 'Layering' },
];

export function FraudGraph() {
  const [selectedNode, setSelectedNode] = useState<Node | null>(NODES[0]);

  return (
    <Card id="campaigns" className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[.08] px-5 py-4">
        <div className="flex items-center gap-2.5">
          <Network size={16} className="text-[#ffcc00]" />
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-white">
            Syndicate Graph Intelligence
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="high">ACTIVE RING DETECTED</Badge>
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

            {/* Connecting Edges */}
            {EDGES.map((edge) => {
              const fromNode = NODES.find((n) => n.id === edge.from)!;
              const toNode = NODES.find((n) => n.id === edge.to)!;
              return (
                <g key={`${edge.from}-${edge.to}`}>
                  <line
                    x1={fromNode.x}
                    y1={fromNode.y}
                    x2={toNode.x}
                    y2={toNode.y}
                    stroke="url(#edgeGrad)"
                    strokeWidth="1.8"
                    strokeDasharray="4 3"
                    className="animate-pulse"
                  />
                  <text
                    x={(fromNode.x + toNode.x) / 2}
                    y={(fromNode.y + toNode.y) / 2 - 5}
                    fill="#94a3b8"
                    fontSize="9"
                    fontFamily="monospace"
                    textAnchor="middle"
                  >
                    {edge.label}
                  </text>
                </g>
              );
            })}

            {/* Nodes */}
            {NODES.map((node) => {
              const isSelected = selectedNode?.id === node.id;
              const fill =
                node.type === 'syndicate'
                  ? '#dc2626'
                  : node.type === 'mule'
                  ? '#ea580c'
                  : node.type === 'caller'
                  ? '#8b5cf6'
                  : '#10b981';

              return (
                <g
                  key={node.id}
                  onClick={() => setSelectedNode(node)}
                  className="cursor-pointer group"
                >
                  {/* Glow circle */}
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={isSelected ? 18 : 14}
                    fill={fill}
                    fillOpacity={isSelected ? 0.4 : 0.2}
                    stroke={fill}
                    strokeWidth={isSelected ? 2.5 : 1.5}
                    className="transition-all"
                  />
                  <circle cx={node.x} cy={node.y} r={isSelected ? 9 : 7} fill={fill} />
                  <text
                    x={node.x}
                    y={node.y + 24}
                    fill="#f1f5f9"
                    fontSize="10"
                    fontWeight="bold"
                    textAnchor="middle"
                    className="pointer-events-none drop-shadow-md"
                  >
                    {node.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Selected Node Details Bar */}
        {selectedNode && (
          <div className="mt-3.5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[.1] bg-white/[.03] p-3 text-xs">
            <div className="flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  selectedNode.type === 'victim' ? 'bg-emerald-400' : 'bg-rose-500'
                }`}
              />
              <span className="font-bold text-white">{selectedNode.label}</span>
              <span className="text-[10px] text-slate-400 font-mono">
                Type: {selectedNode.type.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400">Risk Assessment:</span>
              <Badge variant={selectedNode.risk >= 75 ? 'high' : 'low'}>
                Score {selectedNode.risk}/100
              </Badge>
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-white/[.07] pt-2.5 text-[10px] text-slate-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-rose-500" /> Syndicate Hub
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-orange-500" /> Mule Wallet
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-purple-500" /> Caller Spoof
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-400" /> Victim Node
            </span>
          </div>
          <span>Cross-account link analysis</span>
        </div>
      </div>
    </Card>
  );
}
