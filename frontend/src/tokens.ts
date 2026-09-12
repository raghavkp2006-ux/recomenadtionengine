/**
 * tokens.ts — Interchange Design System tokens.
 *
 * Single source of truth for colors, typography stacks, surface styles,
 * and domain-keyed palettes. Every shared component and (eventually)
 * every page imports from here — no ad-hoc hex strings.
 *
 * Palette: warm parchment + deep ink, with three domain accent hues
 * and a muted interchange violet for UI chrome.
 */

// ── Colors ──────────────────────────────────────────────────────────

export const colors = {
  /** Deep ink background / primary text-on-light */
  ink:         "#10141B",
  /** Warm parchment surface */
  paper:       "#F4EFE4",
  /** Music domain accent — warm red-orange */
  music:       "#E8553F",
  /** Anime domain accent — soft teal-green */
  anime:       "#4F9C8C",
  /** Tourism domain accent — warm golden amber */
  tourism:     "#E3A857",
  /** Movies domain accent — indigo */
  movies:      "#6366F1",
  /** UI chrome / interchange violet */
  interchange: "#8B87A8",
  /** Error / Destructive state */
  error:       "#E04336",
} as const

/** Convenience type for the content domains */
export type Domain = "music" | "anime" | "tourism" | "movies"

/** Map a domain key to its accent hex */
export const domainColor: Record<Domain, string> = {
  music:   colors.music,
  anime:   colors.anime,
  tourism: colors.tourism,
  movies:  colors.movies,
}

// ── Derived palette helpers ─────────────────────────────────────────

/** Ink at various alpha levels (for overlays, shadows, scrim) */
export const inkAlpha = (a: number) => `rgba(16,20,27,${a})`

/** Paper at various alpha levels */
export const paperAlpha = (a: number) => `rgba(244,239,228,${a})`

/** Domain accent at an alpha level */
export const domainAlpha = (domain: Domain, a: number): string => {
  const map: Record<Domain, [number, number, number]> = {
    music:   [232, 85, 63],
    anime:   [79, 156, 140],
    tourism: [227, 168, 87],
    movies:  [99, 102, 241],
  }
  const [r, g, b] = map[domain]
  return `rgba(${r},${g},${b},${a})`
}

/** Error at an alpha level */
export const errorAlpha = (a: number) => `rgba(224,67,54,${a})`

// ── Typography ──────────────────────────────────────────────────────

export const fontFamily = {
  /** Display / headings — Fraunces optical-size serif */
  display: "'Fraunces', 'Georgia', serif",
  /** Body copy — Inter variable */
  body:    "'Inter', system-ui, sans-serif",
  /** Numerals, metadata, badges — JetBrains Mono */
  mono:    "'JetBrains Mono', monospace",
} as const

// ── Surface styles (as CSSProperties objects) ────────────────────────

/** The standard "parchment card" surface — warm paper bg, ink text, subtle shadow. */
export const CARD_SURFACE = {
  background:   colors.paper,
  color:        colors.ink,
  borderRadius: "0.75rem",
  border:       `1px solid ${paperAlpha(0.85)}`,
  boxShadow:    `0 1px 3px ${inkAlpha(0.06)}, 0 4px 16px ${inkAlpha(0.04)}`,
} as const

/**
 * The legacy glass-panel surface — kept here so components migrated
 * incrementally can still reference it via tokens instead of inline objects.
 */
export const GLASS_PANEL = {
  background:     "rgba(18,24,31,0.75)",
  backdropFilter: "blur(10px)",
  border:         "1px solid rgba(255,255,255,0.06)",
  borderRadius:   "0.75rem",
} as const
