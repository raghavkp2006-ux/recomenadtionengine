import { useState, useEffect, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  Compass,
  ThumbsUp,
  ThumbsDown,
  Loader2,
  Sparkles,
  MapPin,
  Tag,
  CheckCircle2,
  AlertCircle,
  X,
} from "lucide-react"
import { api } from "../api"
import type { TouristSpot } from "../types"
import { domainColor, domainAlpha, fontFamily } from "../tokens"
import { Card } from "../components/interchange"
import { Button, Input } from "../components/ui"
import { cn } from "@/lib/utils"

const CATEGORIES = [
  { id: "recommended", label: "Recommended for You" },
  { id: "all", label: "All Spots" },
  { id: "adventure_outdoor", label: "Adventure & Outdoor" },
  { id: "cultural_historic", label: "Cultural & Historic" },
  { id: "chill_scenic", label: "Chill & Scenic" },
  { id: "nightlife", label: "Nightlife" },
  { id: "shopping_social", label: "Shopping & Social" },
  { id: "offbeat_indie", label: "Offbeat & Indie" },
]

export function TouristSpotsPage() {
  const [spots, setSpots] = useState<TouristSpot[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>("recommended")
  const [searchQuery, setSearchQuery] = useState<string>("")
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Feedback states per place_id: { rating: 1 | -1, tag?: string, activeTagInput?: boolean, submitted?: boolean }
  const [feedbackMap, setFeedbackMap] = useState<
    Record<string, { rating: number; tag?: string; submitted?: boolean }>
  >({})
  const [tagInputPlaceId, setTagInputPlaceId] = useState<string | null>(null)
  const [tagInputRating, setTagInputRating] = useState<number>(1)
  const [tagInputValue, setTagInputValue] = useState<string>("")
  const [submittingPlaceId, setSubmittingPlaceId] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

  // Fetch spots whenever category changes
  useEffect(() => {
    let isMounted = true
    setLoading(true)
    setError(null)

    if (selectedCategory === "recommended") {
      api.touristSpots
        .getRecommendedSpots(30)
        .then((data) => {
          if (isMounted) {
            setSpots(data && data.length > 0 ? data : [])
            setLoading(false)
          }
        })
        .catch((err) => {
          // Graceful fallback to all spots if not logged in
          api.touristSpots.getAll().then((allData) => {
            if (isMounted) {
              setSpots(allData || [])
              setLoading(false)
            }
          }).catch(() => {
            if (isMounted) {
              setError(err.message || "Failed to load tourist spots.")
              setLoading(false)
            }
          })
        })
    } else {
      const categoryParam = selectedCategory === "all" ? undefined : selectedCategory
      api.touristSpots
        .getAll(categoryParam)
        .then((data) => {
          if (isMounted) {
            setSpots(data || [])
            setLoading(false)
          }
        })
        .catch((err) => {
          if (isMounted) {
            setError(err.message || "Failed to load tourist spots.")
            setLoading(false)
          }
        })
    }

    return () => {
      isMounted = false
    }
  }, [selectedCategory])

  // In-memory client-side search filter
  const filteredSpots = useMemo(() => {
    if (!searchQuery.trim()) return spots
    const q = searchQuery.toLowerCase().trim()
    return spots.filter(
      (spot) =>
        spot.name.toLowerCase().includes(q) ||
        (spot.description && spot.description.toLowerCase().includes(q))
    )
  }, [spots, searchQuery])

  // Handle feedback click
  const handleFeedbackClick = (spot: TouristSpot, rating: number) => {
    setAuthError(null)
    const existing = feedbackMap[spot.place_id]
    // If same rating clicked and no tag prompt is open, open tag input
    if (tagInputPlaceId === spot.place_id && tagInputRating === rating) {
      setTagInputPlaceId(null)
      return
    }
    setTagInputPlaceId(spot.place_id)
    setTagInputRating(rating)
    setTagInputValue(existing?.tag || "")
  }

  // Submit feedback
  const submitFeedback = async (placeId: string, rating: number, tag?: string) => {
    setSubmittingPlaceId(placeId)
    setAuthError(null)
    try {
      await api.touristSpots.feedback(placeId, rating, tag?.trim() || undefined)
      setFeedbackMap((prev) => ({
        ...prev,
        [placeId]: { rating, tag: tag?.trim() || undefined, submitted: true },
      }))
      setTagInputPlaceId(null)
    } catch (err: any) {
      if (err.message === "Unauthorized" || err.message?.includes("401") || err.message?.includes("authenticated")) {
        setAuthError("Please log in to submit your rating.")
      } else {
        setAuthError(err.message || "Failed to record feedback.")
      }
    } finally {
      setSubmittingPlaceId(null)
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto w-full">
      {/* Header & Hero Card */}
      <div className="relative overflow-hidden rounded-2xl border border-[#E4E4E7] dark:border-[#27272A] bg-gradient-to-br from-amber-500/10 via-transparent to-transparent p-6 md:p-8 backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center shadow-sm"
                style={{
                  backgroundColor: domainAlpha("tourism", 0.15),
                  color: domainColor.tourism,
                  border: `1px solid ${domainAlpha("tourism", 0.3)}`,
                }}
              >
                <Compass className="w-4 h-4" />
              </div>
              <span
                className="text-xs font-semibold uppercase tracking-wider"
                style={{ color: domainColor.tourism, fontFamily: fontFamily.mono }}
              >
                Chennai Urban Discovery
              </span>
            </div>
            <h1
              className="text-2xl md:text-3xl font-bold tracking-tight text-foreground"
              style={{ fontFamily: fontFamily.display }}
            >
              Explore Places & Tourist Spots
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Browse curated destinations across Chennai. Rate your favorite spots to tune your
              cross-module taste profile.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="px-4 py-2.5 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <div className="text-xs">
                <span className="font-bold text-foreground font-mono">{spots.length}</span>
                <span className="text-muted-foreground ml-1">spots cataloged</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Auth Error Banner */}
      <AnimatePresence>
        {authError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-4 text-sm"
          >
            <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-400">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{authError}</span>
            </div>
            <button
              onClick={() => setAuthError(null)}
              className="text-muted-foreground hover:text-foreground p-1 rounded-md"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search & Category Filter Section */}
      <div className="space-y-4">
        {/* Search Bar */}
        <div className="relative max-w-xl">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search spots by name or description…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 pr-10 py-2.5 rounded-xl border-black/10 dark:border-white/10 bg-white/70 dark:bg-[#18181B]/70 backdrop-blur-sm"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Category Pills Row */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 pt-1 scrollbar-hide">
          {CATEGORIES.map((cat) => {
            const isSelected = selectedCategory === cat.id
            const isRec = cat.id === "recommended"
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-200 shrink-0 cursor-pointer",
                  isSelected
                    ? isRec
                      ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold shadow-[0_0_14px_rgba(245,158,11,0.4)]"
                      : "bg-[#E3A857] text-[#10141B] font-semibold shadow-[0_0_12px_rgba(227,168,87,0.35)]"
                    : isRec
                    ? "bg-amber-500/10 text-amber-500 border border-amber-500/30 hover:bg-amber-500/20"
                    : "bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-foreground hover:bg-black/10 dark:hover:bg-white/10 border border-transparent hover:border-black/10 dark:hover:border-white/10"
                )}
                style={{ fontFamily: fontFamily.body }}
              >
                {isRec && <Sparkles className="w-3.5 h-3.5" />}
                <span>{cat.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Spots Count & Results Indicator */}
      <div className="flex items-center justify-between text-xs text-muted-foreground font-mono">
        <span>
          Showing {filteredSpots.length} {filteredSpots.length === 1 ? "spot" : "spots"}
          {selectedCategory !== "all" && ` in ${CATEGORIES.find((c) => c.id === selectedCategory)?.label}`}
          {searchQuery && ` matching "${searchQuery}"`}
        </span>
      </div>

      {/* Spots Grid / States */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2
            className="animate-spin w-8 h-8"
            style={{ color: domainColor.tourism }}
          />
          <p className="text-sm font-mono text-muted-foreground">
            Loading tourist spots…
          </p>
        </div>
      ) : error ? (
        <Card className="p-8 text-center space-y-4">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
          <p className="text-sm text-foreground">{error}</p>
          <Button
            onClick={() => setSelectedCategory(selectedCategory)}
            variant="outline"
            size="sm"
          >
            Retry
          </Button>
        </Card>
      ) : filteredSpots.length === 0 ? (
        <Card className="p-12 text-center space-y-3 rounded-2xl border-dashed border-2 border-black/10 dark:border-white/10">
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center mx-auto"
            style={{ backgroundColor: domainAlpha("tourism", 0.1) }}
          >
            <Compass className="w-6 h-6" style={{ color: domainColor.tourism }} />
          </div>
          <h3
            className="text-base font-semibold text-foreground"
            style={{ fontFamily: fontFamily.display }}
          >
            No spots found
          </h3>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto">
            {searchQuery
              ? `No destinations matched "${searchQuery}". Try modifying your search or clearing filters.`
              : "No spots are currently cataloged for this category."}
          </p>
          {(searchQuery || selectedCategory !== "all") && (
            <Button
              onClick={() => {
                setSearchQuery("")
                setSelectedCategory("all")
              }}
              variant="outline"
              size="sm"
              className="mt-2"
            >
              Reset Filters
            </Button>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredSpots.map((spot, index) => (
            <SpotCard
              key={spot.place_id || `spot-${index}`}
              spot={spot}
              feedback={feedbackMap[spot.place_id]}
              isTagInputOpen={tagInputPlaceId === spot.place_id}
              tagRating={tagInputRating}
              tagValue={tagInputValue}
              isSubmitting={submittingPlaceId === spot.place_id}
              onFeedbackClick={(rating) => handleFeedbackClick(spot, rating)}
              onTagChange={setTagInputValue}
              onTagSubmit={(tag) => submitFeedback(spot.place_id, tagInputRating, tag)}
              onTagCancel={() => setTagInputPlaceId(null)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface SpotCardProps {
  spot: TouristSpot
  feedback?: { rating: number; tag?: string; submitted?: boolean }
  isTagInputOpen: boolean
  tagRating: number
  tagValue: string
  isSubmitting: boolean
  onFeedbackClick: (rating: number) => void
  onTagChange: (val: string) => void
  onTagSubmit: (tag?: string) => void
  onTagCancel: () => void
}

function SpotCard({
  spot,
  feedback,
  isTagInputOpen,
  tagRating,
  tagValue,
  isSubmitting,
  onFeedbackClick,
  onTagChange,
  onTagSubmit,
  onTagCancel,
}: SpotCardProps) {
  const categoryLabel =
    CATEGORIES.find((c) => c.id === spot.category)?.label || spot.category || "General"

  // Price tier styling
  const priceTierBadge = () => {
    const tier = (spot.price_tier || "").toLowerCase()
    switch (tier) {
      case "free":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-wider font-semibold border border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
            Free
          </span>
        )
      case "paid":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-wider font-semibold bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30">
            Paid
          </span>
        )
      case "premium":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-wider font-semibold bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/40 shadow-[0_0_8px_rgba(245,158,11,0.2)]">
            Premium
          </span>
        )
      default:
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-wider text-muted-foreground border border-black/10 dark:border-white/10">
            {spot.price_tier || "Standard"}
          </span>
        )
    }
  }

  const isLiked = feedback?.rating === 1
  const isDisliked = feedback?.rating === -1

  return (
    <Card className="flex flex-col justify-between overflow-hidden rounded-2xl border border-[#E4E4E7] dark:border-[#27272A] bg-white dark:bg-[#18181B] shadow-sm hover:shadow-md transition-all duration-200">
      {/* Top Banner / Color Rail */}
      <div className="p-5 pb-3 flex-1 flex flex-col justify-between">
        <div className="space-y-3">
          {/* Badges row */}
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span
              className="px-2.5 py-0.5 rounded-full text-[11px] font-medium"
              style={{
                backgroundColor: domainAlpha("tourism", 0.12),
                color: domainColor.tourism,
                border: `1px solid ${domainAlpha("tourism", 0.25)}`,
                fontFamily: fontFamily.body,
              }}
            >
              {categoryLabel}
            </span>
            <div className="flex items-center gap-1.5">
              {priceTierBadge()}
            </div>
          </div>

          {/* Place Title */}
          <div>
            <h3
              className="text-base font-bold text-foreground leading-snug line-clamp-1"
              style={{ fontFamily: fontFamily.display }}
              title={spot.name}
            >
              {spot.name}
            </h3>
            <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
              <MapPin className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
              <span>{spot.city || "Chennai"}</span>
            </div>
          </div>

          {/* Description */}
          <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
            {spot.description || "No description available for this destination."}
          </p>
        </div>
      </div>

      {/* Card Footer with Feedback Action */}
      <div className="px-5 py-3 border-t border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.01] dark:bg-white/[0.01] flex flex-col gap-2.5">
        {/* Rating buttons and status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Like Button */}
            <button
              onClick={() => onFeedbackClick(1)}
              disabled={isSubmitting}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150",
                isLiked
                  ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/40 shadow-sm"
                  : "bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-foreground hover:bg-black/10 dark:hover:bg-white/10"
              )}
              title="Like this place"
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              <span>Like</span>
            </button>

            {/* Dislike Button */}
            <button
              onClick={() => onFeedbackClick(-1)}
              disabled={isSubmitting}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150",
                isDisliked
                  ? "bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/40 shadow-sm"
                  : "bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-foreground hover:bg-black/10 dark:hover:bg-white/10"
              )}
              title="Dislike this place"
            >
              <ThumbsDown className="w-3.5 h-3.5" />
              <span>Pass</span>
            </button>
          </div>

          {/* Feedback Confirmed Pill */}
          {feedback?.submitted && (
            <div className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-mono">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Saved</span>
            </div>
          )}
        </div>

        {/* Existing feedback tag if already added */}
        {feedback?.tag && !isTagInputOpen && (
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground italic truncate">
            <Tag className="w-3 h-3 shrink-0" />
            <span className="truncate">"{feedback.tag}"</span>
          </div>
        )}

        {/* Inline Tag Input Form */}
        <AnimatePresence>
          {isTagInputOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="pt-2 border-t border-black/5 dark:border-white/5 space-y-2 overflow-hidden"
            >
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>
                  Add a note for {tagRating === 1 ? "Like" : "Pass"} (optional):
                </span>
                <button
                  onClick={onTagCancel}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
              <div className="flex gap-1.5">
                <Input
                  type="text"
                  placeholder="e.g. peaceful mornings, great chai…"
                  value={tagValue}
                  onChange={(e) => onTagChange(e.target.value)}
                  className="text-xs py-1 px-2.5 h-8 rounded-lg"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      onTagSubmit(tagValue)
                    }
                  }}
                />
                <Button
                  size="sm"
                  onClick={() => onTagSubmit(tagValue)}
                  disabled={isSubmitting}
                  className="h-8 px-3 text-xs bg-[#E3A857] text-[#10141B] hover:bg-[#E3A857]/90 font-medium"
                >
                  {isSubmitting ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    "Save"
                  )}
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Card>
  )
}
