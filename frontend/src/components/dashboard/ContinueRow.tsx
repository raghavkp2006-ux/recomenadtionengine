import { Clock, Tv, Music, MapPin, History, Film } from "lucide-react"
import { motion } from "framer-motion"
import type { RecentItem, Category } from "../../types"
import { Card } from "../interchange"

const CATEGORY_ICONS: Record<Category, React.ElementType> = {
  anime:      Tv,
  music:      Music,
  places:     MapPin,
  movie:      Film,
}

function timeAgo(isoDate: string): string {
  const seconds = Math.floor((Date.now() - new Date(isoDate).getTime()) / 1000)
  if (seconds < 60)  return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60)  return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24)    return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

interface ContinueRowProps {
  items: RecentItem[]
  loading: boolean
}

export function ContinueRow({ items, loading }: ContinueRowProps) {
  return (
    <section className="space-y-3 min-w-0">
      {/* Section header */}
      <div className="flex items-center gap-3">
        <div
          className="w-2 h-2 rounded-full shrink-0 bg-[#A1A1AA] dark:bg-[#A1A1AA]"
        />
        <h2 className="text-sm font-display font-semibold tracking-wide uppercase text-foreground">
          Continue
        </h2>
        <History className="h-4 w-4 text-muted-foreground opacity-60" />
      </div>

      {loading ? (
        <div className="flex gap-3 overflow-x-auto overflow-y-hidden scrollbar-hide">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card
              key={i}
              className="w-48 shrink-0 overflow-hidden"
            >
              <div className="h-20 w-full animate-pulse bg-black/10 dark:bg-white/10 transition-colors duration-150 ease-out" />
              <div className="p-2.5 space-y-1.5">
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
            No history yet — start exploring to build your trail.
          </p>
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto overflow-y-hidden scrollbar-hide snap-x snap-mandatory pb-1">
          {items.map((item, i) => (
            <RecentCard key={item.id} item={item} index={i} />
          ))}
        </div>
      )}
    </section>
  )
}

function RecentCard({ item, index }: { item: RecentItem; index: number }) {
  const Icon = CATEGORY_ICONS[item.category]

  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, duration: 0.2, ease: "easeOut" }}
      whileHover={{ y: -6, transition: { duration: 0.2 } }}
      className="snap-start shrink-0 w-48 cursor-pointer group"
    >
      <Card
        className="relative overflow-hidden h-full"
      >
        

        {/* Image */}
        <div className="relative h-28 overflow-hidden">
          {item.imageUrl ? (
            <img
              src={item.imageUrl}
              alt={item.title}
              className="h-full w-full object-cover transition-transform duration-[100ms] group-hover:scale-[1.02]"
              loading="lazy"
            />
          ) : (
            <div
              className="h-full w-full flex items-center justify-center bg-black/5 dark:bg-white/5 transition-colors duration-150 ease-out"
            >
            <Icon className="h-10 w-10 text-[#A1A1AA] dark:text-[#A1A1AA] opacity-40" />
            </div>
          )}
          <div
            className="absolute inset-0 bg-gradient-to-t from-[#FFFFFF] dark:from-[#18181B] to-transparent via-[#FFFFFF]/60 dark:via-[#18181B]/60 transition-colors duration-150 ease-out"
          />
        </div>

        <div className="p-3 space-y-1.5">
          <h3 className="text-xs font-sans font-semibold leading-snug line-clamp-2 text-[#18181B] dark:text-[#FAFAFA] transition-colors duration-150 ease-out">
            {item.title}
          </h3>
          <div className="flex items-center gap-1.5 text-[10px] text-[#71717A] dark:text-[#A1A1AA] font-mono transition-colors duration-150 ease-out">
            <Clock className="h-3 w-3 shrink-0" />
            <span>{timeAgo(item.viewedAt)}</span>
          </div>
        </div>

        {/* Spacer to match RecommendationRow height feel */}
        <div className="h-2" />
      </Card>
    </motion.div>
  )
}

