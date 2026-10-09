import React from "react";
import { GitMerge, ArrowRight } from "lucide-react";
import { Card } from "../interchange/Card";
import type { TasteBridge } from "../../api/profile";

interface BridgesPanelProps {
  bridges: TasteBridge[];
  loading?: boolean;
}

export const BridgesPanel: React.FC<BridgesPanelProps> = ({ bridges, loading }) => {
  if (loading) {
    return (
      <Card className="p-5 animate-pulse bg-zinc-900/40 border-zinc-800">
        <div className="h-4 w-40 bg-zinc-800 rounded mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-zinc-800/60 rounded-lg" />
          ))}
        </div>
      </Card>
    );
  }

  if (!bridges || bridges.length === 0) return null;

  return (
    <Card className="p-5 bg-zinc-900/60 border-zinc-800">
      <div className="flex items-center gap-2 mb-3">
        <GitMerge className="w-4 h-4 text-cyan-400" />
        <h3 className="text-sm font-semibold text-zinc-100">Cross-Domain Bridges</h3>
      </div>
      <p className="text-xs text-zinc-400 mb-4">
        Discovered pathways showing how affinities in one medium predict choices in another.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {bridges.map((bridge, idx) => (
          <div
            key={idx}
            className="p-3.5 rounded-lg bg-zinc-950/60 border border-zinc-800/80 hover:border-zinc-700/80 transition-all flex flex-col justify-between"
          >
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-zinc-800 text-zinc-200">
                  {bridge.from.label}
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-zinc-500" />
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-400 border border-cyan-800/40">
                  {bridge.to.label}
                </span>
              </div>
              <span className="text-[11px] font-mono text-zinc-400">
                {Math.round(bridge.strength * 100)}% match
              </span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">{bridge.reason}</p>
          </div>
        ))}
      </div>
    </Card>
  );
};
