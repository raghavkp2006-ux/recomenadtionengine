import { Tv, Music, MapPin, AlertCircle, ExternalLink, Film } from "lucide-react"
import { motion } from "framer-motion"
import { getHighResImageUrl } from "../../lib/utils"
import type { Recommendation, Category, PageId } from "../../types"
import { api } from "../../api"
import { fontFamily } from "../../tokens"
import { StationBadge, Card } from "../interchange"

// ── Domain meta ──────────────────────────────────────────────────────

export const DOMAIN: Record<Category, {
  icon: React.ElementType
  domainKey: "anime" | "music" | "tourism" | "movies"
  label: string
}> = {
  anime: {
    icon:     Tv,
    domainKey: "anime",
    label:    "Anime",
  },
  music: {
    icon:     Music,
    domainKey: "music",
    label:    "Music",
  },
  places: {
    icon:     MapPin,
    domainKey: "tourism",
    label:    "Places",
  },
  movie: {
    icon:     Film,
    domainKey: "movies",
    label:    "Movies",
  },
}

// ── Main component ───────────────────────────────────────────────────

interface RecommendationRowProps {
  category: Category
  items: Recommendation[]
  loading: boolean
  error: string | null
  onRetry: () => void
  onNavigate: (page: PageId) => void
  isConnected?: boolean
}

export function RecommendationRow({
  category,
  items,
  loading,
  error,
  onRetry,
  onNavigate,
  isConnected = true,
}: RecommendationRowProps) {
  const meta = DOMAIN[category]
  const Icon = meta.icon
  const color = "#A1A1AA"

  return (
    <section className="space-y-3 min-w-0">
      {/* Section header */}
      <div className="flex items-center gap-3 min-w-0">
        {/* Domain dot */}
        <div
          className="w-2 h-2 rounded-full shrink-0"
          style={{
            backgroundColor: color,
          }}
        />
        <h2 
          className="text-sm font-semibold tracking-wide uppercase text-[#71717A] dark:text-[#A1A1AA] transition-colors duration-150 ease-out"
          style={{ fontFamily: fontFamily.display }}
        >
          {meta.label}
        </h2>
        {/* Section icon */}
        <Icon className="h-4 w-4" style={{ color: color, opacity: 0.7 }} />

        {isConnected && items.length > 0 && (
          <span
            className="ml-auto shrink-0 text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border border-[#E4E4E7] dark:border-[#27272A] bg-[#FAFAFA] dark:bg-[#0A0A0B] transition-colors duration-150 ease-out"
            style={{
              fontFamily: fontFamily.mono,
              color: color,
            }}
          >
            {items.length} signals
          </span>
        )}
      </div>

      {/* Content */}
      <div className="min-w-0">
        {loading ? (
          <SignalCardSkeleton category={category} />
        ) : error ? (
          <ErrorState message={error} onRetry={onRetry} category={category} />
        ) : (!isConnected || items.length === 0) ? (
          <EmptyState
            category={category}
            meta={meta}
            onNavigate={onNavigate}
            isConnected={isConnected}
          />
        ) : (
          <div className="flex gap-4 pb-3 overflow-x-auto overflow-y-hidden scrollbar-hide snap-x snap-mandatory">
            {items.map((item, i) => (
              <SignalCard
                key={item.id}
                item={item}
                index={i}
                category={category}
                meta={meta}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

// ── Signal Card ──────────────────────────────────────────────────────

export function SignalCard({
  item,
  index,
  category,
  meta,
  onNavigate,
}: {
  item: Recommendation
  index: number
  category: Category
  meta: typeof DOMAIN[Category]
  onNavigate: (page: PageId) => void
}) {
  const handleClick = () => {
    if (category === "anime") onNavigate("anime")
    else                      onNavigate("music")
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        delay:    index * 0.06,
        duration: 0.2,
        ease:     [0.22, 1, 0.36, 1],
      }}
      className="snap-start shrink-0 w-48"
    >
      <Card
        domain={meta.domainKey}
        onClick={handleClick}
        className="h-full flex flex-col relative"
      >
        {category === "music" && item.id && (
          <a
            href={`https://open.spotify.com/track/${item.id}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="absolute top-2 right-2 z-20 p-1.5 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors"
            title="Open in Spotify"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
        {/* Image */}
        <div className="relative h-28 overflow-hidden shrink-0">
          {item.imageUrl ? (
            <img
              src={getHighResImageUrl(item.imageUrl)}
              alt={item.title}
              className="h-full w-full object-cover transition-transform duration-[100ms] hover:scale-[1.02]"
              loading="lazy"
            />
          ) : (
            <div
              className="h-full w-full flex items-center justify-center bg-[#F4F4F5] dark:bg-[#27272A] transition-colors duration-150 ease-out"
            >
              <meta.icon className="h-10 w-10 text-[#A1A1AA] dark:text-[#71717A] opacity-60" />
            </div>
          )}
          <div
            className="absolute inset-0 bg-gradient-to-t from-[#FFFFFF] dark:from-[#18181B] to-transparent via-[#FFFFFF]/60 dark:via-[#18181B]/60 transition-colors duration-150 ease-out"
          />
        </div>

        {/* Content */}
        <div className="p-3 space-y-1.5 flex-1 relative z-10 -mt-4">
          <h3 className="text-sm font-semibold leading-snug line-clamp-2 text-[#18181B] dark:text-[#FAFAFA] transition-colors duration-150 ease-out">
            {item.title}
          </h3>
          <p className="text-[10px] line-clamp-2 leading-relaxed text-[#71717A] dark:text-[#A1A1AA] transition-colors duration-150 ease-out">
            {item.reason}
          </p>
        </div>

        {/* Score badge — bottom right */}
        <div className="absolute bottom-3 right-3">
          <StationBadge value={item.score} domain={meta.domainKey} size={40} />
        </div>
      </Card>
    </motion.div>
  )
}

// ── Skeleton ─────────────────────────────────────────────────────────

function SignalCardSkeleton({ category: _category }: { category: Category }) {
  return (
    <div className="flex gap-4 overflow-x-auto overflow-y-hidden scrollbar-hide">
      {Array.from({ length: 5 }).map((_, i) => (
        <Card key={i} className="w-48 shrink-0 overflow-hidden relative">
          <div
            className="h-1 w-full bg-[#E4E4E7] dark:bg-[#27272A] transition-colors duration-150 ease-out"
          />
          <div
            className="h-28 animate-pulse bg-[#E4E4E7] dark:bg-[#27272A] transition-colors duration-150 ease-out"
            style={{ borderRadius: 0 }}
          />
          <div className="p-3 space-y-2">
            <div className="h-2.5 w-3/4 rounded-full animate-pulse bg-[#E4E4E7] dark:bg-[#27272A] transition-colors duration-150 ease-out" />
            <div className="h-2 w-full rounded-full animate-pulse bg-[#E4E4E7] dark:bg-[#27272A] transition-colors duration-150 ease-out" />
            <div className="h-2 w-2/3 rounded-full animate-pulse bg-[#E4E4E7] dark:bg-[#27272A] transition-colors duration-150 ease-out" />
          </div>
          <div className="absolute bottom-3 right-3 w-10 h-10 rounded-full animate-pulse bg-[#E4E4E7] dark:bg-[#27272A] transition-colors duration-150 ease-out" />
        </Card>
      ))}
    </div>
  )
}

// ── Error state ───────────────────────────────────────────────────────

function ErrorState({
  message,
  onRetry,
  category: _category,
}: {
  message: string
  onRetry: () => void
  category: Category
}) {
  const color = "#A1A1AA"
  return (
    <Card className="flex items-center gap-3 p-3">
      <AlertCircle className="h-4 w-4 shrink-0" style={{ color }} />
      <p className="text-sm flex-1 text-[#18181B] dark:text-[#FAFAFA] transition-colors duration-150 ease-out">{message}</p>
      <button
        onClick={onRetry}
        className="text-xs uppercase tracking-wider px-3 py-1.5 rounded-lg transition-opacity hover:opacity-80 bg-[#FAFAFA] dark:bg-[#0A0A0B] transition-colors duration-150 ease-out"
        style={{ fontFamily: fontFamily.mono, color }}
      >
        Retry
      </button>
    </Card>
  )
}

// ── Empty state ────────────────────────────────────────────────────────

const EMPTY_COPY: Record<Category, { title: string; description: string; action?: string }> = {
  anime: {
    title:       "No anime signals yet",
    description: "Connect AniList or like a few anime to get recommendations",
    action:      "Browse Anime",
  },
  music: {
    title:       "No music signals yet",
    description: "Connect Spotify to activate your music signal.",
  },
  places: {
    title:       "No place signals yet",
    description: "Connect music or anime to discover spots tailored to your vibe",
    action:      "Explore Places",
  },
  movie: {
    title:       "No movie signals yet",
    description: "Rate or like some movies to build your taste profile",
    action:      "Explore Movies",
  },
}

function EmptyState({
  category,
  meta,
  onNavigate,
  isConnected = true,
}: {
  category: Category
  meta: typeof DOMAIN[Category]
  onNavigate: (page: PageId) => void
  isConnected?: boolean
}) {
  const Icon = meta.icon
  const color = "#A1A1AA"

  let title = EMPTY_COPY[category].title
  let description = EMPTY_COPY[category].description
  let action = EMPTY_COPY[category].action

  const isMusic = category === "music"
  const isAnime = category === "anime"

  if (!isConnected) {
    if (isMusic) {
      title = "Connect Spotify to see real picks here"
      description = "Link your Spotify account to activate your music signal."
      action = "Connect Spotify"
    } else if (isAnime) {
      title = "Connect AniList to see real picks here"
      description = "Link your AniList account to activate your anime signal."
      action = "Connect AniList"
    }
  }

  const handleAction = () => {
    if (!isConnected) {
      if (isMusic) {
        window.location.href = api.spotify.loginUrl
      } else if (isAnime) {
        window.location.href = api.anilist.loginUrl
      }
    } else {
      if (category === "anime") onNavigate("anime")
      else if (category === "places") onNavigate("places")
      else onNavigate("music")
    }
  }

  return (
    <Card className="flex items-center gap-3 p-4">
      <div
        className="flex items-center justify-center w-10 h-10 rounded-lg shrink-0 bg-[#FAFAFA] dark:bg-[#0A0A0B] transition-colors duration-150 ease-out"
        style={{ color: color }}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[#18181B] dark:text-[#FAFAFA] transition-colors duration-150 ease-out">{title}</p>
        <p className="text-xs mt-0.5 text-[#71717A] dark:text-[#A1A1AA] transition-colors duration-150 ease-out">{description}</p>
      </div>
      {action && (
        <button
          onClick={handleAction}
          className="text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-lg shrink-0 transition-opacity hover:opacity-80 bg-[#FAFAFA] dark:bg-[#0A0A0B] transition-colors duration-150 ease-out"
          style={{ fontFamily: fontFamily.mono, color: color }}
        >
          {action}
        </button>
      )}
    </Card>
  )
}
