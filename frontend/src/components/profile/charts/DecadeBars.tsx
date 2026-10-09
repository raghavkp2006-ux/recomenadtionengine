interface DecadeItem {
  decade: string;
  count: number;
}

interface DecadeBarsProps {
  decades: DecadeItem[];
}

export function DecadeBars({ decades }: DecadeBarsProps) {
  if (decades.length === 0) {
    return <p className="text-xs text-zinc-500 py-4">No track era data available.</p>;
  }

  const maxCount = Math.max(...decades.map((d) => d.count), 1);

  return (
    <div className="flex items-end gap-2 h-40 pt-6 pb-2 px-2">
      {decades.map((d) => {
        const heightPct = Math.round((d.count / maxCount) * 100);

        return (
          <div key={d.decade} className="flex-1 flex flex-col items-center gap-2 h-full justify-end group">
            <span className="text-[10px] font-mono text-zinc-400 group-hover:text-zinc-700 dark:group-hover:text-zinc-200 transition-colors">
              {d.count}
            </span>
            <div className="w-full max-w-[36px] bg-zinc-100 dark:bg-zinc-800 rounded-t-md h-full flex items-end overflow-hidden">
              <div
                className="w-full bg-gradient-to-t from-indigo-600 to-indigo-400 rounded-t-md transition-all duration-500 ease-out group-hover:from-indigo-500 group-hover:to-indigo-300"
                style={{ height: `${Math.max(8, heightPct)}%` }}
              />
            </div>
            <span className="text-[11px] font-mono text-zinc-600 dark:text-zinc-400 truncate">
              {d.decade}
            </span>
          </div>
        );
      })}
    </div>
  );
}
