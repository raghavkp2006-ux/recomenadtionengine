import { useState, useEffect, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  ShoppingBag,
  ThumbsUp,
  ThumbsDown,
  Loader2,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  X,
  ExternalLink,
} from "lucide-react"
import { api } from "../api"
import { fontFamily } from "../tokens"
import { Card } from "../components/interchange"
import { Button, Input } from "../components/ui"
import { cn } from "@/lib/utils"

const FASHION_ACCENT = "#D946EF"
const fashionAlpha = (a: number) => `rgba(217, 70, 239, ${a})`

export interface MyntraProductItem {
  product_id: string
  product_url?: string | null
  brand?: string | null
  title?: string | null
  category?: string | null
  price?: number | null
  currency?: string | null
  image_url?: string | null
  score?: number
}

export function MyntraPage() {
  const [connectionEnabled, setConnectionEnabled] = useState<boolean | null>(null)
  const [products, setProducts] = useState<MyntraProductItem[]>([])
  const [recentlyViewed, setRecentlyViewed] = useState<MyntraProductItem[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState<string>("")
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Feedback states per product_id: { rating: "like" | "dislike", submitted?: boolean }
  const [feedbackMap, setFeedbackMap] = useState<
    Record<string, { rating: "like" | "dislike"; submitted?: boolean }>
  >({})
  const [submittingProductId, setSubmittingProductId] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

  // Fetch connection status and recommendations on mount
  useEffect(() => {
    let isMounted = true
    setLoading(true)
    setError(null)

    api.myntra
      .getConnection()
      .then((conn) => {
        if (!isMounted) return null
        setConnectionEnabled(conn.enabled)
        if (conn.enabled) {
          return api.myntra.getRecommendations()
        }
        return null
      })
      .then((recRes) => {
        if (!isMounted) return
        if (recRes && Array.isArray(recRes.recommendations)) {
          setProducts(recRes.recommendations)
        }
        setLoading(false)
      })
      .catch((err) => {
        if (!isMounted) return
        setError(err.message || "Failed to load Myntra connection.")
        setLoading(false)
      })

    // Supplementary: fetch recently viewed products (don't block the page)
    api.myntra.getRecentlyViewed(15)
      .then((res) => { if (isMounted && res?.products) setRecentlyViewed(res.products) })
      .catch(() => { /* supplementary — don't block the page on this */ })

    return () => {
      isMounted = false
    }
  }, [])

  // Dynamic list of categories from returned products
  const categories = useMemo(() => {
    const set = new Set<string>()
    products.forEach((p) => {
      if (p.category) set.add(p.category)
    })
    return [
      { id: "all", label: "All Items" },
      ...Array.from(set).map((cat) => ({
        id: cat,
        label: cat.charAt(0).toUpperCase() + cat.slice(1).replace(/_/g, " "),
      })),
    ]
  }, [products])

  // In-memory client-side filter
  const filteredProducts = useMemo(() => {
    let list = products
    if (selectedCategory !== "all") {
      list = list.filter(
        (p) => p.category?.toLowerCase() === selectedCategory.toLowerCase()
      )
    }
    if (!searchQuery.trim()) return list
    const q = searchQuery.toLowerCase().trim()
    return list.filter(
      (p) =>
        (p.title && p.title.toLowerCase().includes(q)) ||
        (p.brand && p.brand.toLowerCase().includes(q)) ||
        (p.category && p.category.toLowerCase().includes(q))
    )
  }, [products, selectedCategory, searchQuery])

  // Handle feedback submit
  const handleFeedback = async (productId: string, feedback: "like" | "dislike") => {
    setSubmittingProductId(productId)
    setAuthError(null)
    try {
      await api.myntra.submitFeedback(productId, feedback)
      setFeedbackMap((prev) => ({
        ...prev,
        [productId]: { rating: feedback, submitted: true },
      }))
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

  return (
    <div className="space-y-8 max-w-7xl mx-auto w-full">
      {/* Header & Hero Card */}
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
                Myntra Fashion Signals
              </span>
            </div>
            <h1
              className="text-2xl md:text-3xl font-bold tracking-tight text-foreground"
              style={{ fontFamily: fontFamily.display }}
            >
              Fashion & Wardrobe Discovery
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Explore curated fashion recommendations synced with your Myntra browsing and wardrobe tastes.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="px-4 py-2.5 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-fuchsia-500" />
              <div className="text-xs">
                <span className="font-bold text-foreground font-mono">{products.length}</span>
                <span className="text-muted-foreground ml-1">items curated</span>
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

      {/* Loading state */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2
            className="animate-spin w-8 h-8"
            style={{ color: FASHION_ACCENT }}
          />
          <p className="text-sm font-mono text-muted-foreground">
            Loading fashion recommendations…
          </p>
        </div>
      ) : error ? (
        <Card className="p-8 text-center space-y-4">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
          <p className="text-sm text-foreground">{error}</p>
          <Button
            onClick={() => {
              setLoading(true)
              setError(null)
              api.myntra
                .getConnection()
                .then((conn) => {
                  setConnectionEnabled(conn.enabled)
                  if (conn.enabled) return api.myntra.getRecommendations()
                  return null
                })
                .then((recRes) => {
                  if (recRes && Array.isArray(recRes.recommendations)) {
                    setProducts(recRes.recommendations)
                  }
                  setLoading(false)
                })
                .catch((err) => {
                  setError(err.message || "Failed to load Myntra connection.")
                  setLoading(false)
                })
            }}
            variant="outline"
            size="sm"
          >
            Retry
          </Button>
        </Card>
      ) : connectionEnabled === false ? (
        /* Empty / Not Connected State */
        <Card className="p-12 text-center space-y-4 rounded-2xl border-dashed border-2 border-black/10 dark:border-white/10 max-w-2xl mx-auto">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center mx-auto"
            style={{ backgroundColor: fashionAlpha(0.1) }}
          >
            <ShoppingBag className="w-7 h-7" style={{ color: FASHION_ACCENT }} />
          </div>
          <div className="space-y-2">
            <h3
              className="text-lg font-semibold text-foreground"
              style={{ fontFamily: fontFamily.display }}
            >
              Myntra Connection Inactive
            </h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              Connect your Myntra account via the companion browser extension to sync your shopping signals and receive personalized fashion recommendations.
            </p>
          </div>
          <Button
            onClick={() => {
              // TODO: Link to Settings or extension pairing flow once settings hook is available
              alert("Please enable the Myntra extension in Settings to sync your activity.")
            }}
            className="mt-2 text-xs font-semibold px-5 py-2.5 rounded-xl shadow-sm text-white"
            style={{ backgroundColor: FASHION_ACCENT }}
          >
            Connect in Settings
          </Button>
        </Card>
      ) : (
        /* Connected state with Recommendations */
        <div className="space-y-6">
          {/* Recently Viewed Section */}
          {recentlyViewed.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Recently Viewed
              </h3>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {recentlyViewed.map((product) => (
                  <Card key={product.product_id} className="min-w-[160px] p-3 flex-shrink-0 rounded-xl border border-[#E4E4E7] dark:border-[#27272A]">
                    {product.image_url && (
                      <div className="w-full h-24 rounded-lg overflow-hidden mb-2 bg-black/5 dark:bg-white/5">
                        <img
                          src={product.image_url}
                          alt={product.title || "Product"}
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => { (e.target as HTMLElement).style.display = "none" }}
                        />
                      </div>
                    )}
                    <div className="text-sm font-medium truncate">{product.title || "Untitled product"}</div>
                    <div className="text-xs text-muted-foreground truncate">{product.brand || ""}</div>
                    {product.price != null && (
                      <div className="text-xs mt-1 font-mono" style={{ color: FASHION_ACCENT }}>₹{product.price.toLocaleString()}</div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}
          {/* Search & Category Filter Section */}
          <div className="space-y-4">
            {/* Search Bar */}
            <div className="relative max-w-xl">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search by product, brand, or category…"
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
            {categories.length > 1 && (
              <div className="flex items-center gap-2 overflow-x-auto pb-2 pt-1 scrollbar-hide">
                {categories.map((cat) => {
                  const isSelected = selectedCategory === cat.id
                  return (
                    <button
                      key={cat.id}
                      onClick={() => setSelectedCategory(cat.id)}
                      className={cn(
                        "px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-200 shrink-0",
                        isSelected
                          ? "bg-[#D946EF] text-white font-semibold shadow-[0_0_12px_rgba(217,70,239,0.35)]"
                          : "bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-foreground hover:bg-black/10 dark:hover:bg-white/10 border border-transparent hover:border-black/10 dark:hover:border-white/10"
                      )}
                      style={{ fontFamily: fontFamily.body }}
                    >
                      {cat.label}
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          {/* Items Count & Filter Indicator */}
          <div className="flex items-center justify-between text-xs text-muted-foreground font-mono">
            <span>
              Showing {filteredProducts.length} {filteredProducts.length === 1 ? "item" : "items"}
              {selectedCategory !== "all" && ` in ${categories.find((c) => c.id === selectedCategory)?.label}`}
              {searchQuery && ` matching "${searchQuery}"`}
            </span>
          </div>

          {/* Product Grid / Empty Search State */}
          {filteredProducts.length === 0 ? (
            <Card className="p-12 text-center space-y-3 rounded-2xl border-dashed border-2 border-black/10 dark:border-white/10">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center mx-auto"
                style={{ backgroundColor: fashionAlpha(0.1) }}
              >
                <ShoppingBag className="w-6 h-6" style={{ color: FASHION_ACCENT }} />
              </div>
              <h3
                className="text-base font-semibold text-foreground"
                style={{ fontFamily: fontFamily.display }}
              >
                No items found
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                {searchQuery
                  ? `No recommendations matched "${searchQuery}". Try modifying your search or clearing filters.`
                  : "No recommendations available yet. Browse products on Myntra with the extension enabled to build your signal."}
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
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.product_id}
                  product={product}
                  feedback={feedbackMap[product.product_id]}
                  isSubmitting={submittingProductId === product.product_id}
                  onFeedback={(type) => handleFeedback(product.product_id, type)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface ProductCardProps {
  product: MyntraProductItem
  feedback?: { rating: "like" | "dislike"; submitted?: boolean }
  isSubmitting: boolean
  onFeedback: (rating: "like" | "dislike") => void
}

function ProductCard({
  product,
  feedback,
  isSubmitting,
  onFeedback,
}: ProductCardProps) {
  const isLiked = feedback?.rating === "like"
  const isDisliked = feedback?.rating === "dislike"

  return (
    <Card className="flex flex-col justify-between overflow-hidden rounded-2xl border border-[#E4E4E7] dark:border-[#27272A] bg-white dark:bg-[#18181B] shadow-sm hover:shadow-md transition-all duration-200">
      {/* Product Image */}
      {product.image_url ? (
        <div className="relative w-full h-48 bg-black/5 dark:bg-white/5 overflow-hidden border-b border-[#E4E4E7] dark:border-[#27272A]">
          <img
            src={product.image_url}
            alt={product.title || "Product Image"}
            className="w-full h-full object-cover object-top hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={(e) => {
              ;(e.target as HTMLElement).style.display = "none"
            }}
          />
        </div>
      ) : null}

      {/* Product Details */}
      <div className="p-5 pb-3 flex-1 flex flex-col justify-between">
        <div className="space-y-3">
          {/* Category & Brand Badges */}
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span
              className="px-2.5 py-0.5 rounded-full text-[11px] font-medium uppercase tracking-wider"
              style={{
                backgroundColor: fashionAlpha(0.12),
                color: FASHION_ACCENT,
                border: `1px solid ${fashionAlpha(0.25)}`,
                fontFamily: fontFamily.mono,
              }}
            >
              {product.category || "Fashion"}
            </span>

            {product.brand && (
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {product.brand}
              </span>
            )}
          </div>

          {/* Product Title */}
          <div>
            <h3
              className="text-base font-bold text-foreground leading-snug line-clamp-2"
              style={{ fontFamily: fontFamily.display }}
              title={product.title || "Product"}
            >
              {product.title || "Fashion Item"}
            </h3>

            {/* Price Row */}
            {product.price !== undefined && product.price !== null && (
              <div className="mt-2 flex items-baseline gap-1.5">
                <span
                  className="text-lg font-bold text-foreground"
                  style={{ fontFamily: fontFamily.mono }}
                >
                  {product.currency === "INR" || !product.currency ? "₹" : `${product.currency} `}
                  {product.price.toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Card Footer with Feedback and Links */}
      <div className="px-5 py-3 border-t border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.01] dark:bg-white/[0.01] flex items-center justify-between gap-2">
        {/* Rating buttons */}
        <div className="flex items-center gap-2">
          {/* Like Button */}
          <button
            onClick={() => onFeedback("like")}
            disabled={isSubmitting}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150",
              isLiked
                ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/40 shadow-sm"
                : "bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-foreground hover:bg-black/10 dark:hover:bg-white/10"
            )}
            title="Like this item"
          >
            <ThumbsUp className="w-3.5 h-3.5" />
            <span>Like</span>
          </button>

          {/* Dislike Button */}
          <button
            onClick={() => onFeedback("dislike")}
            disabled={isSubmitting}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150",
              isDisliked
                ? "bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/40 shadow-sm"
                : "bg-black/5 dark:bg-white/5 text-muted-foreground hover:text-foreground hover:bg-black/10 dark:hover:bg-white/10"
            )}
            title="Not interested"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
            <span>Pass</span>
          </button>

          {/* Feedback Confirmed Pill */}
          {feedback?.submitted && (
            <div className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-mono ml-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Saved</span>
            </div>
          )}
        </div>

        {/* External Link to Myntra Product */}
        {product.product_url && (
          <a
            href={product.product_url}
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
