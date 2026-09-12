import {
  Star,
  Heart,
  Eye,
  PlusCircle,
  Tv,
  Music,
  MapPin,
  Activity,
  Film,
} from "lucide-react"
import { motion } from "framer-motion"
import type { ActivityItem, ActivityAction, Category } from "../../types"
import { Card } from "../interchange"

// ── Action icons & accent colors ─────────────────────────────────────

const ACTION_ICONS: Record<ActivityAction, React.ElementType> = {
  rated:  Star,
  liked:  Heart,
  viewed: Eye,
  added:  PlusCircle,
}

const ACTION_COLORS: Record<ActivityAction, string> = {
  rated:  "#E3A857",
  liked:  "#FF7A59",
  viewed: "#7C6CF0",
  added:  "#3ED6C4",
}

const CATEGORY_ICONS: Record<Category, React.ElementType> = {
  anime:      Tv,
  music:      Music,
  places:     MapPin,
  movie:      Film,
}

// ── Helpers ───────────────────────────────────────────────────────────

function timeAgo(isoDate: string): string {
  const seconds = Math.floor((Date.now() - new Date(isoDate).getTime()) / 1000)
  if (seconds < 60)  return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60)  return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24)    return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function describeAction(item: ActivityItem): string {
  switch (item.action) {
    case "rated":  return `Rated ${item.itemTitle} ${item.detail} star${item.detail !== "1" ? "s" : ""}`
    case "liked":  return `Liked ${item.itemTitle}`
    case "viewed": return `Viewed ${item.itemTitle}`
    case "added":  return `Added ${item.itemTitle} to list`
  }
}

// ── Component ─────────────────────────────────────────────────────────

interface ActivityFeedProps {
  items: ActivityItem[]
  loading: boolean
}

export function ActivityFeed({ items, loading }: ActivityFeedProps) {
  return (
    <section className="space-y-3 min-w-0">
      {/* Section header */}
      <div className="flex items-center gap-3">
        <div
          className="w-2 h-2 rounded-full shrink-0 bg-[#A1A1AA] dark:bg-[#A1A1AA]"
        />
        <h2 className="text-sm font-display font-semibold tracking-wide uppercase text-foreground">
          Activity
        </h2>
        <Activity className="h-4 w-4 text-muted-foreground opacity-60" />
      </div>

      {loading ? (
        <div className="flex gap-3 overflow-x-auto overflow-y-hidden scrollbar-hide">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card
              key={i}
              className="w-48 shrink-0 overflow-hidden"
            >
              <div className="h-20 w-full animate-pulse bg-black/10 dark:bg-white/10 transition-colors duration-150 ease-out" />
              <div className="p-3 space-y-1.5">
                <div className="h-2 w-3/4 rounded-full animate-pulse bg-black/10 dark:bg-white/10 transition-colors duration-150 ease-out" />
                <div className="h-2 w-1/2 rounded-full animate-pulse bg-black/10 dark:bg-white/10 transition-colors duration-150 ease-out" />
              </div>
            </Card>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div
          className="rounded-xl border border-dashed border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out px-4 py-5 text-center"
        >
          <p className="text-sm font-sans text-muted-foreground">
            No activity yet — start exploring to build your trail.
          </p>
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto overflow-y-hidden scrollbar-hide snap-x snap-mandatory pb-1">
          {items.map((item, i) => (
            <ActivityCard key={item.id} item={item} index={i} />
          ))}
        </div>
      )}
    </section>
  )
}

// ── Activity card ──────────────────────────────────────────────────────

function ActivityCard({ item, index }: { item: ActivityItem; index: number }) {
  const ActionIcon   = ACTION_ICONS[item.action]
  const CategoryIcon = CATEGORY_ICONS[item.category]
  const actionColor  = ACTION_COLORS[item.action]

  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, duration: 0.2, ease: "easeOut" }}
      whileHover={{ y: -6, transition: { duration: 0.2 } }}
      className="snap-start shrink-0 w-48 cursor-default group"
    >
      <Card
        className="relative overflow-hidden h-full"
      >
        

        {/* Icon section (instead of image) */}
        <div className="relative h-20 overflow-hidden flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{ backgroundColor: `${actionColor}12` }}
          />
          <ActionIcon className="h-8 w-8 relative z-10" style={{ color: actionColor, opacity: 0.8 }} />
          {/* Scrim */}
          <div
            className="absolute inset-0 z-20 bg-gradient-to-t from-[#FFFFFF] dark:from-[#18181B] to-transparent via-[#FFFFFF]/60 dark:via-[#18181B]/60 transition-colors duration-150 ease-out"
          />
        </div>

        <div className="p-3 space-y-1.5">
          <h3 className="text-xs font-sans font-semibold leading-snug line-clamp-2 text-[#18181B] dark:text-[#FAFAFA] transition-colors duration-150 ease-out">
            {describeAction(item)}
          </h3>
          <div className="flex items-center gap-1.5 mt-1">
            <CategoryIcon className="h-3 w-3 text-[#A1A1AA] dark:text-[#71717A]" />
            <span className="text-[10px] text-[#71717A] dark:text-[#A1A1AA] font-mono transition-colors duration-150 ease-out">
              {timeAgo(item.timestamp)}
            </span>
          </div>
        </div>

        {/* Spacer to match RecommendationRow height feel */}
        <div className="h-2" />
      </Card>
    </motion.div>
  )
}
