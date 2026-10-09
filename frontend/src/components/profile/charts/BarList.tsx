interface BarItem {
  genre: string;
  weight: number;
}

interface BarListProps {
  items: BarItem[];
  color?: string;
}

export function BarList({ items, color = "#7C6CF0" }: BarListProps) {
  if (items.length === 0) {
    return <p className="text-xs text-zinc-500 py-4">No genres logged yet.</p>;
  }

  const maxWeight = Math.max(...items.map((i) => i.weight), 0.001);

  return (
    <div className="space-y-2.5">
      {items.map((item) => {
        const pct = Math.round((item.weight / maxWeight) * 100);
        const actualPct = Math.round(item.weight * 100);

        return (
          <div key={item.genre} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-zinc-800 dark:text-zinc-200 capitalize truncate max-w-[180px]">
                {item.genre}
              </span>
              <span className="font-mono text-[11px] text-zinc-500">
                {actualPct > 0 ? `${actualPct}%` : `${(item.weight * 100).toFixed(1)}%`}
              </span>
            </div>
            <div className="h-2 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{
                  width: `${Math.max(4, pct)}%`,
                  backgroundColor: color,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
