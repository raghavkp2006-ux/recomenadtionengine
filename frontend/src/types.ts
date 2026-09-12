// ── Recommendation types ────────────────────────────────────────────

export type Category = "anime" | "music" | "places" | "movie"

export interface Recommendation {
  id: string
  title: string
  imageUrl: string
  reason: string
  /** Match score 0–100 */
  score: number
  category: Category
}

// ── Tourist Spot types ──────────────────────────────────────────────

export interface TouristSpot {
  place_id: string
  name: string
  category: string
  description?: string | null
  price_tier: "free" | "paid" | "premium" | string
  lat: number
  lng: number
  city: string
}

export interface SpotFeedbackResponse {
  status: string
  user_id: string
  place_id: string
  rating: number
  tag?: string | null
}

// ── Recently viewed ─────────────────────────────────────────────────

export interface RecentItem {
  id: string
  title: string
  imageUrl: string
  category: Category
  /** ISO timestamp of last view */
  viewedAt: string
}

// ── Activity feed ───────────────────────────────────────────────────

export type ActivityAction = "rated" | "liked" | "viewed" | "added"

export interface ActivityItem {
  id: string
  action: ActivityAction
  itemTitle: string
  /** e.g. "4" for a 4-star rating */
  detail?: string
  category: Category
  /** ISO timestamp */
  timestamp: string
}

// ── Navigation ──────────────────────────────────────────────────────

export type PageId = "home" | "anime" | "music" | "places" | "profile" | "settings" | "myntra" | "movies"
