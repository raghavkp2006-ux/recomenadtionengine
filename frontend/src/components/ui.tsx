/**
 * components/ui.tsx — Canonical UI primitives for Poly_Taste
 *
 * Button is re-exported from ./ui/button (cva + Radix Slot) so all
 * consumers (AnimeDetail, AnimeGrid, ActivityFeed, ContinueRow, TopBar)
 * share the same implementation as hero.tsx which imports from ./ui/button.
 */
import * as React from "react"
import { cn } from "@/lib/utils"
import { colors, inkAlpha, paperAlpha, domainColor, domainAlpha, CARD_SURFACE } from "../tokens"

// ── Re-export canonical Button ───────────────────────────────────────
export { Button, buttonVariants } from "./ui/button"
export type { ButtonProps } from "./ui/button"

// ── Re-export canonical Input ────────────────────────────────────────
export { Input } from "./ui/input"
export type { InputProps } from "./ui/input"

// ── Card (glass-card variant) ─────────────────────────────────────────

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "overflow-hidden",
        className
      )}
      style={CARD_SURFACE}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col space-y-1.5 p-5", className)}
      {...props}
    />
  )
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("font-display font-semibold leading-none tracking-tight", className)}
      style={{ color: colors.ink }}
      {...props}
    />
  )
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("p-5 pt-0", className)} {...props} />
  )
}

// ── Tabs ──────────────────────────────────────────────────────────────

export function Tabs({ defaultValue, children }: any) {
  const [active, setActive] = React.useState(defaultValue)
  return (
    <div className="w-full">
      {React.Children.map(children, (child) => {
        if (child.type === TabsList) return React.cloneElement(child, { active, setActive })
        if (child.type === TabsContent) return child.props.value === active ? child : null
        return child
      })}
    </div>
  )
}

export function TabsList({ active, setActive, children, className }: any) {
  return (
    <div
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-lg p-1",
        className
      )}
      style={{
        backgroundColor: inkAlpha(0.04),
        border: `1px solid ${inkAlpha(0.06)}`,
        color: inkAlpha(0.6),
      }}
    >
      {React.Children.map(children, (child) =>
        React.cloneElement(child, { active, setActive })
      )}
    </div>
  )
}

export function TabsTrigger({ value, active, setActive, children, className }: any) {
  const isActive = active === value
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5",
        "text-sm font-sans font-medium",
        "transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        className
      )}
      style={isActive ? {
        backgroundColor: colors.paper,
        color: colors.ink,
        boxShadow: `0 1px 3px ${inkAlpha(0.05)}`,
        border: `1px solid ${inkAlpha(0.1)}`,
      } : {
        color: inkAlpha(0.7),
      }}
      onClick={() => setActive(value)}
    >
      {children}
    </button>
  )
}

export function TabsContent({ children, className }: any) {
  return (
    <div
      className={cn(
        "mt-2 ring-offset-background",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        className
      )}
    >
      {children}
    </div>
  )
}

// ── Switch ───────────────────────────────────────────────────────────

export function Switch({ checked, onCheckedChange }: any) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full",
        "border-2 border-transparent",
        "transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50"
      )}
      style={{ backgroundColor: checked ? colors.interchange : inkAlpha(0.1) }}
    >
      <span
        className={cn(
          "pointer-events-none block h-4 w-4 rounded-full",
          "shadow-lg ring-0 transition-transform duration-200",
          checked ? "translate-x-4" : "translate-x-0"
        )}
        style={{ backgroundColor: colors.paper }}
      />
    </button>
  )
}

// ── Skeleton ─────────────────────────────────────────────────────────

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-lg bg-black/10 dark:bg-white/10 transition-colors duration-150 ease-out", className)}
      {...props}
    />
  )
}

// ── Badge ─────────────────────────────────────────────────────────────

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "outline" | "success" | "music" | "anime"
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const styleMap: Record<NonNullable<BadgeProps["variant"]>, React.CSSProperties> = {
    default:   { backgroundColor: inkAlpha(0.1), color: colors.ink, border: `1px solid ${inkAlpha(0.1)}` },
    secondary: { backgroundColor: paperAlpha(0.5), color: inkAlpha(0.7), border: `1px solid ${inkAlpha(0.1)}` },
    outline:   { backgroundColor: "transparent", color: colors.ink, border: `1px solid ${inkAlpha(0.2)}` },
    success:   { backgroundColor: "rgba(52,211,153,0.1)", color: "#10B981", border: "1px solid rgba(52,211,153,0.2)" },
    music:     { backgroundColor: domainAlpha("music", 0.15), color: domainColor.music, border: `1px solid ${domainAlpha("music", 0.25)}` },
    anime:     { backgroundColor: domainAlpha("anime", 0.15), color: domainColor.anime, border: `1px solid ${domainAlpha("anime", 0.25)}` },
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-sans font-semibold transition-colors",
        className
      )}
      style={styleMap[variant]}
      {...props}
    />
  )
}

// ── Avatar ────────────────────────────────────────────────────────────

export function Avatar({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative flex h-9 w-9 shrink-0 overflow-hidden rounded-full",
        className
      )}
      style={{
        backgroundColor: colors.ink,
        border: `1px solid ${inkAlpha(0.1)}`,
      }}
      {...props}
    />
  )
}

export function AvatarFallback({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "flex h-full w-full items-center justify-center rounded-full",
        "text-white text-sm font-display font-semibold",
        className
      )}
      style={{
        background: `linear-gradient(to bottom right, ${colors.interchange}, ${colors.ink})`,
      }}
      {...props}
    />
  )
}

// ── ScrollArea (horizontal snap) ──────────────────────────────────────

export function ScrollArea({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex overflow-x-auto scrollbar-hide scroll-smooth snap-x snap-mandatory gap-4 pb-2",
        className
      )}
      {...props}
    />
  )
}

// ── Tooltip (CSS-only) ────────────────────────────────────────────────

interface TooltipProps extends React.HTMLAttributes<HTMLDivElement> {
  content: string
}

export function Tooltip({ content, children, className, ...props }: TooltipProps) {
  return (
    <div className={cn("group/tooltip relative inline-flex", className)} {...props}>
      {children}
      <span
        className={cn(
          "pointer-events-none absolute left-1/2 -translate-x-1/2 -top-9 z-50",
          "whitespace-nowrap rounded-lg px-2.5 py-1.5",
          "text-xs",
          "opacity-0 transition-opacity duration-150",
          "group-hover/tooltip:opacity-100"
        )}
        style={{ ...CARD_SURFACE, padding: "6px 10px" }}
      >
        {content}
      </span>
    </div>
  )
}

// ── Re-export ChromaGrid ─────────────────────────────────────────────
export { ChromaGrid } from "./ui/ChromaGrid"
export type { ChromaItem, ChromaGridProps } from "./ui/ChromaGrid"
