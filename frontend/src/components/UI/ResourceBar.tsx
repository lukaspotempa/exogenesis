type Props = {
  value?: number | null
  min?: number
  max?: number
  center?: number
  color?: string
  ariaLabel?: string
}

export default function ResourceBar({ value, min = 0, max = 2, center = 1, color = '#60a5fa', ariaLabel }: Props) {
  if (value == null || Number.isNaN(value)) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex-1 h-3 rounded bg-white/5" />
        <div className="text-sm font-semibold">—</div>
      </div>
    )
  }

  const clamped = Math.min(Math.max(value, min), max)
  const range = max - min === 0 ? 1 : max - min
  const fillPct = Math.min(100, Math.max(0, ((clamped - min) / range) * 100))

  // position of the center marker (e.g., 1.0) as percentage from left
  const centerPct = Math.min(100, Math.max(0, ((center - min) / range) * 100))

  return (
    <div className="flex items-center gap-3" role="group" aria-label={ariaLabel}>
      <div className="flex-1 h-3 rounded bg-white/5 relative overflow-hidden">
        <div
          className="absolute left-0 top-0 bottom-0 rounded-l"
          style={{ width: `${fillPct}%`, background: color }}
          aria-hidden
        />

        {/* Center line */}
        <div
          className="absolute top-0 bottom-0 w-px bg-white/90 -translate-x-1/2"
          style={{ left: `${centerPct}%` }}
        />
      </div>

      <div className="text-sm font-semibold tabular-nums">{Number(value).toFixed(2)}</div>
    </div>
  )
}
