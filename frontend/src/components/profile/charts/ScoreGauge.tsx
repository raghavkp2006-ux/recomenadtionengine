interface ScoreGaugeProps {
  label: string;
  value: number; // 0 to 100 or 0 to 1
  isPercentage?: boolean;
  color?: string;
  description?: string;
}

export function ScoreGauge({
  label,
  value,
  isPercentage = true,
  color = "#7C6CF0",
  description,
}: ScoreGaugeProps) {
  // Normalize value to 0-100 range
  const displayVal = isPercentage && value <= 1 ? Math.round(value * 100) : Math.round(value);
  const normalized = Math.max(0, Math.min(100, displayVal));

  const radius = 38;
  const strokeWidth = 7;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (normalized / 100) * circumference;

  return (
    <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200/70 dark:border-zinc-800 flex flex-col items-center text-center">
      <div className="relative w-24 h-24 flex items-center justify-center my-1">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          {/* Background circle */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            className="text-zinc-200 dark:text-zinc-800"
            strokeWidth={strokeWidth}
          />
          {/* Progress circle */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold font-mono text-zinc-900 dark:text-zinc-100">
            {displayVal}
            <span className="text-xs font-normal text-zinc-400">%</span>
          </span>
        </div>
      </div>

      <h4 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 mt-1">
        {label}
      </h4>
      {description && (
        <p className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5 max-w-[140px]">
          {description}
        </p>
      )}
    </div>
  );
}
