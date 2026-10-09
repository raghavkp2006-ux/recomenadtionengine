interface GenreItem {
  genre: string;
  weight: number;
}

interface GenreRadarProps {
  genres: GenreItem[];
  size?: number;
}

export function GenreRadar({ genres, size = 320 }: GenreRadarProps) {
  // Take top 6 genres
  const items = genres.slice(0, 6);
  if (items.length < 3) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-zinc-500">
        Need at least 3 genres to plot radar
      </div>
    );
  }

  const center = size / 2;
  const radius = center - 50;
  const total = items.length;
  const maxWeight = Math.max(...items.map((i) => i.weight), 0.01);

  // Concentric levels (25%, 50%, 75%, 100%)
  const levels = [0.25, 0.5, 0.75, 1];

  const getCoordinates = (index: number, valueRatio: number) => {
    const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
    const r = radius * valueRatio;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  // Polygon points
  const points = items
    .map((item, i) => {
      const ratio = item.weight / maxWeight;
      const { x, y } = getCoordinates(i, ratio);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width={size} height={size} className="overflow-visible">
        {/* Background web rings */}
        {levels.map((lvl) => {
          const levelPoints = items
            .map((_, i) => {
              const { x, y } = getCoordinates(i, lvl);
              return `${x},${y}`;
            })
            .join(" ");
          return (
            <polygon
              key={lvl}
              points={levelPoints}
              fill="none"
              stroke="currentColor"
              className="text-zinc-200 dark:text-zinc-800"
              strokeWidth="1"
              strokeDasharray={lvl === 1 ? undefined : "3 3"}
            />
          );
        })}

        {/* Axis spokes */}
        {items.map((item, i) => {
          const { x, y } = getCoordinates(i, 1);
          return (
            <line
              key={item.genre}
              x1={center}
              y1={center}
              x2={x}
              y2={y}
              stroke="currentColor"
              className="text-zinc-200 dark:text-zinc-800"
              strokeWidth="1"
            />
          );
        })}

        {/* Data polygon */}
        <polygon
          points={points}
          fill="url(#radarGradient)"
          stroke="#7C6CF0"
          strokeWidth="2.5"
          className="transition-all duration-300"
        />

        {/* Gradient definition */}
        <defs>
          <radialGradient id="radarGradient" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#7C6CF0" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#7C6CF0" stopOpacity="0.1" />
          </radialGradient>
        </defs>

        {/* Data points & labels */}
        {items.map((item, i) => {
          const ratio = item.weight / maxWeight;
          const { x, y } = getCoordinates(i, ratio);
          const outer = getCoordinates(i, 1.2);
          const isRight = outer.x > center;
          const isCenter = Math.abs(outer.x - center) < 5;

          return (
            <g key={item.genre}>
              <circle
                cx={x}
                cy={y}
                r="4"
                fill="#7C6CF0"
                className="transition-all duration-300"
              />
              <text
                x={outer.x}
                y={outer.y}
                textAnchor={isCenter ? "middle" : isRight ? "start" : "end"}
                dominantBaseline="central"
                className="fill-zinc-700 dark:fill-zinc-300 text-[11px] font-medium capitalize"
              >
                {item.genre}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
