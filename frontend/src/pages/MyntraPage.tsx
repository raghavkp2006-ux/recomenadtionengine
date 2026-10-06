import { useState, useEffect, useMemo, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  ShoppingBag,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  X,
  ExternalLink,
  Music,
  Tv,
  Film,
  Radio,
  Clock,
  ShieldCheck,
  Info,
} from "lucide-react"
import { api } from "../api"
import { fontFamily } from "../tokens"
import { Card } from "../components/interchange"
import { Button, Input } from "../components/ui"
import { cn } from "@/lib/utils"

const FASHION_ACCENT = "#D946EF"
const fashionAlpha = (a: number) => `rgba(217, 70, 239, ${a})`

export interface MyntraVerdictReason {
  domain: string
  text: string
  evidence: Record<string, any>
}

export interface MyntraVerdictItem {
  product_id: string
  product_url: string
  brand: string
  title: string
  category: string
  price: number
  currency: string
  image_url: string
  verdict: "BUY" | "CONSIDER" | "SKIP"
  fit: number
  components: {
    direct: number
    crosswalk: number
    price: number
    redundancy: number
  }
  reasons: MyntraVerdictReason[]
  price_note: string
}

export interface MyntraVerdictsSummary {
  events: number
  last_event_at: string | null
  signals: {
    myntra: boolean
    spotify: boolean
    anilist: boolean
    movies: boolean
  }
  confidence: "low" | "medium" | "high"
  price_range: {
    min: number | null
    median: number | null
    max: number | null
  }
  top_colours: string[]
  top_categories: string[]
  gender_filter: string
}

export interface MyntraRecentlyViewedItem {
  product_id: string
  product_url?: string | null
  brand?: string | null
  title?: string | null
  price?: number | null
  image_url?: string | null
}

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return "never"
  try {
    const d = new Date(isoString)
    const diffSec = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000))
    if (diffSec < 60) return "just now"
    const diffMin = Math.round(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHour = Math.round(diffMin / 60)
    if (diffHour < 24) return `${diffHour}h ago`
    const diffDay = Math.round(diffHour / 24)
    return `${diffDay}d ago`
  } catch {
    return "recently"
  }
}

export function MyntraPage() {
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

  // Verdict state
  const [summary, setSummary] = useState<MyntraVerdictsSummary | null>(null)
  const [counts, setCounts] = useState<{ buy: number; consider: number; skip: number }>({
    buy: 0,
    consider: 0,
    skip: 0,
  })
  const [items, setItems] = useState<MyntraVerdictItem[]>([])
  const [recentlyViewed, setRecentlyViewed] = useState<MyntraRecentlyViewedItem[]>([])

  // Controls
  const [activeTab, setActiveTab] = useState<"BUY" | "CONSIDER" | "SKIP">("BUY")
  const [genderFilter, setGenderFilter] = useState<"all" | "men" | "women">("all")
  const [searchQuery, setSearchQuery] = useState<string>("")
  const [submittingProductId, setSubmittingProductId] = useState<string | null>(null)

  // Fetch verdict feed
  const loadVerdicts = useCallback(async (gender: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.myntra.getVerdicts({
        gender: gender === "all" ? undefined : gender,
        limit: 100,
      })
      setSummary(res.summary)
      setCounts(res.counts)
      setItems(res.items || [])

      // Automatically pick the first populated tab if current is empty
      if (res.counts.buy > 0) {
        setActiveTab("BUY")
      } else if (res.counts.consider > 0) {
        setActiveTab("CONSIDER")
      } else if (res.counts.skip > 0) {
        setActiveTab("SKIP")
      }
    } catch (err: any) {
      setError(err.message || "Failed to load fashion verdicts.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadVerdicts(genderFilter)

    // Supplementary: recently viewed products (non-blocking)
    api.myntra
      .getRecentlyViewed(15)
      .then((res) => {
        if (res?.products && Array.isArray(res.products)) {
          setRecentlyViewed(res.products)
        }
      })
      .catch(() => {
        /* non-critical */
      })
  }, [genderFilter, loadVerdicts])

  // Handle feedback and optimistic card removal
  const handleFeedback = async (productId: string, feedbackType: "like" | "dislike") => {
    setSubmittingProductId(productId)
    setAuthError(null)
    try {
      await api.myntra.submitFeedback(productId, feedbackType)

      // Optimistically remove card from the feed
      setItems((prev) => prev.filter((it) => it.product_id !== productId))

      // Decrement current count
      setCounts((prev) => {
        const key = activeTab.toLowerCase() as "buy" | "consider" | "skip"
        return {
          ...prev,
          [key]: Math.max(0, prev[key] - 1),
        }
      })
    } catch (err: any) {
      if (
        err.message === "Unauthorized" ||
        err.message?.includes("401") ||
        err.message?.includes("authenticated")
      ) {
        setAuthError("Please log in to submit feedback.")
      } else {
        setAuthError(err.message || "Failed to record feedback.")
      }
    } finally {
      setSubmittingProductId(null)
    }
  }

  // Client-side search within the active tab
  const tabItems = useMemo(() => {
    return items.filter((it) => it.verdict === activeTab)
  }, [items, activeTab])

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return tabItems
    const q = searchQuery.toLowerCase().trim()
    return tabItems.filter(
      (p) =>
        (p.title && p.title.toLowerCase().includes(q)) ||
        (p.brand && p.brand.toLowerCase().includes(q)) ||
        (p.category && p.category.toLowerCase().includes(q))
    )
  }, [tabItems, searchQuery])

  // Determine signals status
  const hasMyntraEvents = (summary?.events ?? 0) > 0
  const hasMediaSignals = Boolean(
    summary?.signals.spotify || summary?.signals.anilist || summary?.signals.movies
  )
  const isColdStart = !hasMyntraEvents && !hasMediaSignals

  return (
    <div className="space-y-8 max-w-7xl mx-auto w-full">
      {/* Header & Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-[#E4E4E7] dark:border-[#27272A] bg-gradient-to-br from-fuchsia-500/10 via-transparent to-transparent p-6 md:p-8 backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center shadow-sm"
                style={{
                  backgroundColor: fashionAlpha(0.15),
                  color: FASHION_ACCENT,
                  border: `1px solid ${fashionAlpha(0.3)}`,
                }}
              >
                <ShoppingBag className="w-4 h-4" />
              </div>
              <span
                className="text-xs font-semibold uppercase tracking-wider"
                style={{ color: FASHION_ACCENT, fontFamily: fontFamily.mono }}
              >
                Verdict-First Fashion Engine
              </span>
            </div>
            <h1
              className="text-2xl md:text-3xl font-bold tracking-tight text-foreground"
              style={{ fontFamily: fontFamily.display }}
            >
              Should I Buy This?
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Curated Buy / Consider / Skip verdicts computed from your Myntra browsing history,
              spend profile, and media crosswalk taste signals.
            </p>
          </div>
        </div>

        {/* Activity & Signals Strip */}
        {summary && (
          <div className="mt-6 pt-5 border-t border-black/5 dark:border-white/5 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
            {/* Events count & Last sync time */}
            <div className="flex items-center gap-2 text-foreground/80">
              <Clock className="w-3.5 h-3.5 text-muted-foreground" />
              <span>
                <strong>{summary.events}</strong> Myntra events · last synced{" "}
                <strong className="text-foreground">{formatRelativeTime(summary.last_event_at)}</strong>
              </span>
            </div>

            {/* Cross-domain Signal Chips */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-muted-foreground mr-1">Signals:</span>

              {/* Myntra Chip */}
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px]",
                  summary.signals.myntra
                    ? "bg-fuchsia-500/10 border-fuchsia-500/30 text-fuchsia-600 dark:text-fuchsia-400 font-semibold"
                    : "bg-black/5 dark:bg-white/5 border-transparent text-muted-foreground"
                )}
              >
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    summary.signals.myntra ? "bg-fuchsia-500" : "bg-zinc-400"
                  )}
                />
                <Radio className="w-3 h-3" />
                <span>Myntra</span>
              </div>

              {/* Spotify Chip */}
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px]",
                  summary.signals.spotify
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400 font-semibold"
                    : "bg-black/5 dark:bg-white/5 border-transparent text-muted-foreground"
                )}
              >
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    summary.signals.spotify ? "bg-emerald-500" : "bg-zinc-400"
                  )}
                />
                <Music className="w-3 h-3" />
                <span>Spotify</span>
              </div>

              {/* AniList Chip */}
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px]",
                  summary.signals.anilist
                    ? "bg-sky-500/10 border-sky-500/30 text-sky-600 dark:text-sky-400 font-semibold"
                    : "bg-black/5 dark:bg-white/5 border-transparent text-muted-foreground"
                )}
              >
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    summary.signals.anilist ? "bg-sky-500" : "bg-zinc-400"
                  )}
                />
                <Tv className="w-3 h-3" />
                <span>AniList</span>
              </div>

              {/* Movies Chip */}
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px]",
                  summary.signals.movies
                    ? "bg-purple-500/10 border-purple-500/30 text-purple-600 dark:text-purple-400 font-semibold"
                    : "bg-black/5 dark:bg-white/5 border-transparent text-muted-foreground"
                )}
              >
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    summary.signals.movies ? "bg-purple-500" : "bg-zinc-400"
                  )}
                />
                <Film className="w-3 h-3" />
                <span>Movies</span>
              </div>
            </div>

            {/* Confidence note */}
            <div className="flex items-center gap-1.5 text-xs">
              <ShieldCheck className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">
                {summary.confidence === "low" && "Low confidence — browse more on Myntra to sharpen this"}
                {summary.confidence === "medium" && "Medium confidence — signals calibrated"}
                {summary.confidence === "high" && "High confidence — deep taste profile active"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Taste Summary Strip */}
      {summary && (summary.top_colours.length > 0 || summary.top_categories.length > 0 || summary.price_range.median !== null) && (
        <div className="p-4 rounded-xl border border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
          <div className="flex items-center gap-4 flex-wrap">
            {summary.price_range.median !== null && (
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground">Spend Band:</span>
                <span className="font-semibold text-foreground">
                  ₹{summary.price_range.min ?? 0} – ₹{summary.price_range.median} (median) – ₹{summary.price_range.max ?? 0}
                </span>
              </div>
            )}

            {summary.top_colours.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground">Top Colours:</span>
                <span className="text-foreground capitalize">{summary.top_colours.join(", ")}</span>
              </div>
            )}

            {summary.top_categories.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground">Top Categories:</span>
                <span className="text-foreground capitalize">{summary.top_categories.join(", ")}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Auth Error Notification Banner */}
      <AnimatePresence>
        {authError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="p-4 rounded-xl bg-fuchsia-500/10 border border-fuchsia-500/30 flex items-center justify-between gap-4 text-sm"
          >
            <div className="flex items-center gap-2.5 text-fuchsia-600 dark:text-fuchsia-400">
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

      {/* Main Content Area */}
      {loading ? (
        /* Loading Skeleton (No layout shift) */
        <div className="space-y-6">
          <div className="h-10 w-80 bg-black/5 dark:bg-white/5 rounded-xl animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3, 4, 5, 6].map((idx) => (
              <Card key={idx} className="p-4 space-y-4 rounded-2xl animate-pulse">
                <div className="w-full h-48 bg-black/5 dark:bg-white/5 rounded-xl" />
                <div className="h-4 bg-black/5 dark:bg-white/5 rounded w-3/4" />
                <div className="h-3 bg-black/5 dark:bg-white/5 rounded w-1/2" />
                <div className="h-6 bg-black/5 dark:bg-white/5 rounded w-1/3" />
              </Card>
            ))}
          </div>
        </div>
      ) : error ? (
        /* Empty State 4: Request Error */
        <Card className="p-10 text-center space-y-4 rounded-2xl border-red-500/20 max-w-lg mx-auto">
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto" />
          <h3 className="text-base font-semibold text-foreground" style={{ fontFamily: fontFamily.display }}>
            Unable to Load Verdicts
          </h3>
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button onClick={() => loadVerdicts(genderFilter)} variant="outline" size="sm">
            Retry Request
          </Button>
        </Card>
      ) : isColdStart ? (
        /* Empty State 1: Extension not connected & no media signals */
        <Card className="p-12 text-center space-y-4 rounded-2xl border-dashed border-2 border-black/10 dark:border-white/10 max-w-2xl mx-auto">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center mx-auto"
            style={{ backgroundColor: fashionAlpha(0.1) }}
          >
            <ShoppingBag className="w-7 h-7" style={{ color: FASHION_ACCENT }} />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-foreground" style={{ fontFamily: fontFamily.display }}>
              Connect Signals to Generate Verdicts
            </h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              No Myntra activity or media signals detected. Install and enable the PolyTaste browser extension on
              Myntra or connect Spotify / AniList in Settings to generate personalized Buy / Consider / Skip verdicts.
            </p>
          </div>
          <p className="text-xs font-mono text-muted-foreground">
            No synthetic catalog data is shown. Real signals are required.
          </p>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Empty State 2 Banner: Media-only signals (no direct Myntra events yet) */}
          {!hasMyntraEvents && hasMediaSignals && (
            <div className="p-4 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center gap-3 text-xs font-mono text-sky-600 dark:text-sky-400">
              <Info className="w-4 h-4 shrink-0" />
              <span>
                Based on music / anime / movies crosswalk only. Browse products on Myntra with the extension enabled to calibrate direct fit and spend preferences.
              </span>
            </div>
          )}

          {/* Controls Bar: Tabs, Gender Filter, Search Box */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            {/* Verdict Tabs: Buy (n), Consider (n), Skip (n) */}
            <div className="flex items-center gap-2 p-1 bg-black/5 dark:bg-white/5 rounded-xl self-start">
              <button
                onClick={() => setActiveTab("BUY")}
                className={cn(
                  "px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center gap-2",
                  activeTab === "BUY"
                    ? "bg-white dark:bg-[#18181B] text-emerald-600 dark:text-emerald-400 shadow-sm border border-black/5 dark:border-white/10"
                    : "text-muted-foreground hover:text-foreground"
                )}
                style={{ fontFamily: fontFamily.body }}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span>Buy</span>
                <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-emerald-500/10">
                  {counts.buy}
                </span>
              </button>

              <button
                onClick={() => setActiveTab("CONSIDER")}
                className={cn(
                  "px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center gap-2",
                  activeTab === "CONSIDER"
                    ? "bg-white dark:bg-[#18181B] text-amber-600 dark:text-amber-400 shadow-sm border border-black/5 dark:border-white/10"
                    : "text-muted-foreground hover:text-foreground"
                )}
                style={{ fontFamily: fontFamily.body }}
              >
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                <span>Consider</span>
                <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-amber-500/10">
                  {counts.consider}
                </span>
              </button>

              <button
                onClick={() => setActiveTab("SKIP")}
                className={cn(
                  "px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center gap-2",
                  activeTab === "SKIP"
                    ? "bg-white dark:bg-[#18181B] text-zinc-600 dark:text-zinc-400 shadow-sm border border-black/5 dark:border-white/10"
                    : "text-muted-foreground hover:text-foreground"
                )}
                style={{ fontFamily: fontFamily.body }}
              >
                <span className="w-2 h-2 rounded-full bg-zinc-400" />
                <span>Skip</span>
                <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-zinc-500/10">
                  {counts.skip}
                </span>
              </button>
            </div>

            {/* Right: Gender Filter + Search Box */}
            <div className="flex items-center gap-3 flex-wrap">
              {/* Gender Segmented Control */}
              <div className="flex items-center gap-1 p-1 bg-black/5 dark:bg-white/5 rounded-xl text-xs font-mono">
                {(["all", "men", "women"] as const).map((g) => (
                  <button
                    key={g}
                    onClick={() => setGenderFilter(g)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg font-medium transition-all duration-150 capitalize",
                      genderFilter === g
                        ? "bg-white dark:bg-[#18181B] text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {g}
                  </button>
                ))}
              </div>

              {/* Search Box */}
              <div className="relative min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter items..."
                  className="pl-9 h-9 text-xs bg-black/5 dark:bg-white/5 border-transparent focus:border-black/20 dark:focus:border-white/20 rounded-xl"
                  style={{ fontFamily: fontFamily.body }}
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Verdict Items Grid / Empty State 3 (Tab has no items) */}
          {filteredItems.length === 0 ? (
            <Card className="p-12 text-center space-y-3 rounded-2xl border-dashed border-2 border-black/10 dark:border-white/10">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center mx-auto"
                style={{ backgroundColor: fashionAlpha(0.1) }}
              >
                <ShoppingBag className="w-6 h-6" style={{ color: FASHION_ACCENT }} />
              </div>
              <h3 className="text-base font-semibold text-foreground" style={{ fontFamily: fontFamily.display }}>
                No items in {activeTab} tab
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                {searchQuery
                  ? `No ${activeTab.toLowerCase()} items matched "${searchQuery}".`
                  : `Currently no catalog items classified as ${activeTab}. Explore other tabs or adjust gender filter.`}
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredItems.map((item) => (
                <VerdictProductCard
                  key={item.product_id}
                  item={item}
                  isSubmitting={submittingProductId === item.product_id}
                  onFeedback={(type) => handleFeedback(item.product_id, type)}
                />
              ))}
            </div>
          )}

          {/* Recently Viewed Section (Preserved) */}
          {recentlyViewed.length > 0 && (
            <div className="pt-8 space-y-3 border-t border-black/5 dark:border-white/5">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
                  Recently Viewed on Myntra
                </h3>
                <span className="text-xs text-muted-foreground font-mono">
                  {recentlyViewed.length} items
                </span>
              </div>
              <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
                {recentlyViewed.map((prod) => (
                  <Card
                    key={prod.product_id}
                    className="min-w-[170px] max-w-[170px] p-3 flex-shrink-0 rounded-xl border border-[#E4E4E7] dark:border-[#27272A]"
                  >
                    {prod.image_url && (
                      <div className="w-full h-28 rounded-lg overflow-hidden mb-2 bg-black/5 dark:bg-white/5">
                        <img
                          src={prod.image_url}
                          alt={prod.title || "Product"}
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            ;(e.target as HTMLElement).style.display = "none"
                          }}
                        />
                      </div>
                    )}
                    <div className="text-xs font-medium truncate" title={prod.title || ""}>
                      {prod.title || "Untitled product"}
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">{prod.brand || ""}</div>
                    {prod.price != null && (
                      <div className="text-xs mt-1 font-mono font-semibold" style={{ color: FASHION_ACCENT }}>
                        ₹{prod.price.toLocaleString()}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function VerdictProductCard({
  item,
  isSubmitting,
  onFeedback,
}: {
  item: MyntraVerdictItem
  isSubmitting: boolean
  onFeedback: (type: "like" | "dislike") => void
}) {
  const verdictBadgeStyles = {
    BUY: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
    CONSIDER: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30",
    SKIP: "bg-zinc-500/15 text-zinc-600 dark:text-zinc-400 border-zinc-500/30",
  }

  const fitPercentage = Math.round((item.fit ?? 0) * 100)

  return (
    <Card className="flex flex-col justify-between overflow-hidden rounded-2xl border border-[#E4E4E7] dark:border-[#27272A] bg-card hover:border-black/20 dark:hover:border-white/20 transition-all duration-200">
      <div>
        {/* Product Image and Overlay Badges */}
        <div className="relative aspect-[4/3] w-full overflow-hidden bg-black/5 dark:bg-white/5">
          {item.image_url ? (
            <img
              src={item.image_url}
              alt={item.title || "Fashion Item"}
              className="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
              loading="lazy"
              onError={(e) => {
                ;(e.target as HTMLElement).style.display = "none"
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-muted-foreground">
              <ShoppingBag className="w-10 h-10 opacity-30" />
            </div>
          )}

          {/* Top Left: Verdict Badge */}
          <div className="absolute top-3 left-3 flex items-center gap-1.5">
            <span
              className={cn(
                "px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider border shadow-sm backdrop-blur-md",
                verdictBadgeStyles[item.verdict]
              )}
              style={{ fontFamily: fontFamily.mono }}
            >
              {item.verdict}
            </span>
          </div>

          {/* Top Right: Fit percentage badge */}
          <div className="absolute top-3 right-3">
            <span
              className="px-2.5 py-1 rounded-full text-xs font-mono font-semibold bg-black/60 text-white backdrop-blur-md border border-white/20 shadow-sm"
            >
              {fitPercentage}% fit
            </span>
          </div>
        </div>

        {/* Content body */}
        <div className="p-5 space-y-3">
          {/* Brand & Category */}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-semibold uppercase tracking-wider">{item.brand || "Fashion"}</span>
            <span className="font-mono">{item.category}</span>
          </div>

          {/* Title */}
          <h3
            className="text-sm font-semibold text-foreground line-clamp-2 leading-snug"
            title={item.title}
            style={{ fontFamily: fontFamily.display }}
          >
            {item.title}
          </h3>

          {/* Price & Price Note */}
          <div className="space-y-1">
            <div className="flex items-baseline gap-2">
              <span className="text-lg font-bold font-mono text-foreground">
                {item.currency === "INR" || !item.currency ? "₹" : `${item.currency} `}
                {item.price.toLocaleString()}
              </span>
            </div>
            {item.price_note && (
              <p className="text-[11px] font-mono text-muted-foreground">{item.price_note}</p>
            )}
          </div>

          {/* Reasons (Max 3, prefixed with domain, rendered via React text nodes) */}
          {item.reasons && item.reasons.length > 0 && (
            <div className="pt-2 space-y-1.5 border-t border-black/5 dark:border-white/5">
              {item.reasons.slice(0, 3).map((r, i) => (
                <div
                  key={i}
                  className="text-xs text-foreground/90 bg-black/[0.03] dark:bg-white/[0.03] px-2.5 py-1 rounded-lg flex items-center gap-1.5"
                >
                  <span
                    className={cn(
                      "text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded",
                      r.domain === "myntra" && "bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-400",
                      r.domain === "spotify" && "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
                      r.domain === "anilist" && "bg-sky-500/15 text-sky-600 dark:text-sky-400",
                      r.domain === "movies" && "bg-purple-500/15 text-purple-600 dark:text-purple-400"
                    )}
                    style={{ fontFamily: fontFamily.mono }}
                  >
                    {r.domain}
                  </span>
                  <span className="truncate">{r.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer Actions: Like / Pass / External Link */}
      <div className="px-5 py-3 border-t border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.01] dark:bg-white/[0.01] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Like */}
          <button
            onClick={() => onFeedback("like")}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
            title="Like this item"
          >
            <ThumbsUp className="w-3.5 h-3.5" />
            <span>Like</span>
          </button>

          {/* Pass */}
          <button
            onClick={() => onFeedback("dislike")}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 transition-colors"
            title="Pass / Not interested"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
            <span>Pass</span>
          </button>
        </div>

        {/* View on Myntra */}
        {item.product_url && (
          <a
            href={item.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-black/5 dark:hover:bg-white/5 rounded-lg transition-colors"
            title="View on Myntra"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>
    </Card>
  )
}
