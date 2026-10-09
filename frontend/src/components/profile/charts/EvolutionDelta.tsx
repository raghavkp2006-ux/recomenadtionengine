import { TrendingUp, TrendingDown } from "lucide-react";

interface DeltaItem {
  genre: string;
  delta: number;
}

interface EvolutionDeltaProps {
  rising: DeltaItem[];
  fading: DeltaItem[];
}

export function EvolutionDelta({ rising, fading }: EvolutionDeltaProps) {
  const hasData = rising.length > 0 || fading.length > 0;

  if (!hasData) {
    return (
      <div className="py-6 text-center text-xs text-zinc-500">
        Listen more over time to see genre evolution shifts between short-term and long-term listening.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {/* Rising genres */}
      <div className="p-4 rounded-xl bg-emerald-50/30 dark:bg-emerald-950/20 border border-emerald-500/20 space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
          <TrendingUp className="w-4 h-4" />
          <span>Surging Recently</span>
        </div>
        <div className="space-y-1.5 pt-1">
          {rising.length > 0 ? (
            rising.map((item) => (
              <div
                key={item.genre}
                className="flex items-center justify-between text-xs py-1 border-b border-emerald-500/10 last:border-none"
              >
                <span className="font-medium text-zinc-800 dark:text-zinc-200 capitalize truncate max-w-[150px]">
                  {item.genre}
                </span>
                <span className="font-mono text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                  +{Math.round(item.delta * 100)}%
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-zinc-400">No significant surge</p>
          )}
        </div>
      </div>

      {/* Fading genres */}
      <div className="p-4 rounded-xl bg-amber-50/30 dark:bg-amber-950/20 border border-amber-500/20 space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
          <TrendingDown className="w-4 h-4" />
          <span>Fading Back</span>
        </div>
        <div className="space-y-1.5 pt-1">
          {fading.length > 0 ? (
            fading.map((item) => (
              <div
                key={item.genre}
                className="flex items-center justify-between text-xs py-1 border-b border-amber-500/10 last:border-none"
              >
                <span className="font-medium text-zinc-800 dark:text-zinc-200 capitalize truncate max-w-[150px]">
                  {item.genre}
                </span>
                <span className="font-mono text-[11px] font-semibold text-amber-600 dark:text-amber-400">
                  -{Math.round(item.delta * 100)}%
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-zinc-400">No significant fade</p>
          )}
        </div>
      </div>
    </div>
  );
}
