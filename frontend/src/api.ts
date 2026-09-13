const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000"

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    credentials: "include",
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Unauthorized")
    }
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `API error: ${response.status}`)
  }

  return response.json()
}

export const api = {
  auth: {
    me: () => fetchApi<{ user_id: string }>("/auth/me"),
    login: (req: any) => fetchApi<{ message: string, user_id: string }>("/auth/login", { 
      method: "POST", 
      body: JSON.stringify(req) 
    }),
    logout: () => fetchApi<{ message: string }>("/auth/logout", { method: "POST" }),
    loginUrl: `${API_BASE}/spotify/login`,
    googleLoginUrl: `${API_BASE}/auth/google/login`,
    googleCallback: (id_token: string) =>
      fetchApi<{ message: string, user_id: string }>("/auth/google/callback", {
        method: "POST",
        body: JSON.stringify({ id_token }),
      }),
  },
  taste: {
    getProfile: () => fetchApi<any>("/taste-profile"),
  },
  anime: {
    getTop: () => fetchApi<any[]>("/anime/top"),
    search: async (q: string) => {
      const res = await fetchApi<{ results: any[] }>(`/anime/search?q=${encodeURIComponent(q)}`);
      return res.results || [];
    },
    getUpcoming: () => fetchApi<any[]>("/anime/upcoming"),
    getDetail: (mal_id: number) => fetchApi<any>(`/anime/${mal_id}`),
    getReviews: (mal_id: number) => fetchApi<any[]>(`/anime/${mal_id}/reviews`),
    getVideos: (mal_id: number) => fetchApi<any[]>(`/anime/${mal_id}/videos`),
    getNews: (mal_id: number) => fetchApi<any[]>(`/anime/${mal_id}/news`),
    recommend: (mal_id: number, personalize: boolean = false) => 
      fetchApi<{ recommendations: any[], personalized: boolean }>(`/anime/${mal_id}/recommend?personalize=${personalize}`),
    getDashboardRecommendations: async () => {
      try {
        const profile = await fetchApi<any>("/taste-profile");
        const animeLikes = Object.keys(profile.breakdown?.anime || {});
        const anilistWatched = (profile.anilist_watched || []).map((x: any) => String(x.mal_id));
        const combinedIds = Array.from(new Set([...animeLikes, ...anilistWatched]));
        
        if (combinedIds.length === 0) {
          return [];
        }
        
        const res = await fetchApi<{ recommendations: any[] }>("/anime/recommendations?limit=25", {
          method: "POST",
          body: JSON.stringify({ liked_ids: combinedIds })
        });
        return res.recommendations.map(r => ({
          ...r,
          id: String(r.id),
          score: Math.round(r.score * 100),
          category: "anime"
        })) as import("./types").Recommendation[];
      } catch (e) {
        throw new Error("Couldn't load your recommendations, try refreshing");
      }
    },
    like: (mal_id: number) => fetchApi("/anime/" + mal_id + "/like", { method: "POST" }),
    unlike: (mal_id: number) => fetchApi("/anime/" + mal_id + "/like", { method: "DELETE" }),
  },
  recommendations: {
    getByCategory: async (category: string): Promise<import("./types").Recommendation[]> => {
      if (category === "music") {
        try {
          const res = await fetchApi<{ recommendations: any[] }>("/spotify/recommendations");
          return (res.recommendations || []).map(r => ({
            id: String(r.id),
            title: r.name || r.title || "Unknown Track",
            reason: r.artists ? r.artists.join(", ") : (r.reason || "Recommended Track"),
            imageUrl: r.image_url || r.imageUrl || "",
            score: typeof r.score === "number" ? (r.score <= 1 ? Math.round(r.score * 100) : r.score) : 0,
            category: "music" as const,
          }));
        } catch (e) {
          console.error("Music recs error", e);
          return [];
        }
      }
      if (category === "anime") {
        return api.anime.getDashboardRecommendations();
      }
      if (category === "places") {
        return api.touristSpots.getRecommendations();
      }
      if (category === "movie") {
        try {
          const res = await fetchApi<{ recommendations: any[] }>("/movie/recommendations", {
            method: "POST",
            body: JSON.stringify({}),
          });
          return (res.recommendations || []).map(r => ({
            id: String(r.id),
            title: r.title || "Unknown Movie",
            reason: r.reason || "Recommended for you",
            imageUrl: r.imageUrl || "",
            score: typeof r.score === "number" ? (r.score <= 1 ? Math.round(r.score * 100) : r.score) : 0,
            category: "movie" as const,
          }));
        } catch (e) {
          console.error("Movie recs error", e);
          return [];
        }
      }
      return [];
    },
    getRecent: () =>
      fetchApi<import("./types").RecentItem[]>("/api/recent"),
    getActivity: () =>
      fetchApi<import("./types").ActivityItem[]>("/api/activity"),
  },
  anilist: {
    loginUrl: `${API_BASE}/anilist/login`,
    getStatus: () =>
      fetchApi<{ connected: boolean; anilist_username: string | null }>("/anilist/status"),
  },
  connections: {
    getStatus: () =>
      fetchApi<{ spotify: boolean; anilist: boolean; location: boolean; myntra: boolean }>("/connections/status"),
  },
  myntra: {
    getConnection: () =>
      fetchApi<{
        enabled: boolean
        collect_product_views: boolean
        collect_search: boolean
        collect_wishlist: boolean
        collect_cart: boolean
        collect_orders: boolean
      }>("/myntra/connection"),
    updateConnection: (
      payload: Partial<{
        enabled: boolean
        collect_product_views: boolean
        collect_search: boolean
        collect_wishlist: boolean
        collect_cart: boolean
        collect_orders: boolean
      }>
    ) =>
      fetchApi<{
        enabled: boolean
        collect_product_views: boolean
        collect_search: boolean
        collect_wishlist: boolean
        collect_cart: boolean
        collect_orders: boolean
      }>("/myntra/connection", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getProfile: () => fetchApi<any>("/myntra/profile"),
    getRecommendations: (params?: {
      limit?: number
      category?: string
      min_price?: number
      max_price?: number
      brand?: string
    }) => {
      const searchParams = new URLSearchParams()
      if (params?.limit !== undefined) searchParams.append("limit", String(params.limit))
      if (params?.category) searchParams.append("category", params.category)
      if (params?.min_price !== undefined) searchParams.append("min_price", String(params.min_price))
      if (params?.max_price !== undefined) searchParams.append("max_price", String(params.max_price))
      if (params?.brand) searchParams.append("brand", params.brand)
      const qs = searchParams.toString() ? `?${searchParams.toString()}` : ""
      return fetchApi<{ recommendations: any[] }>(`/myntra/recommendations${qs}`)
    },
    getHistory: (params?: {
      limit?: number
      offset?: number
      event_type?: string
      product_id?: string
      brand?: string
      category?: string
    }) => {
      const searchParams = new URLSearchParams()
      if (params?.limit !== undefined) searchParams.append("limit", String(params.limit))
      if (params?.offset !== undefined) searchParams.append("offset", String(params.offset))
      if (params?.event_type) searchParams.append("event_type", params.event_type)
      if (params?.product_id) searchParams.append("product_id", params.product_id)
      if (params?.brand) searchParams.append("brand", params.brand)
      if (params?.category) searchParams.append("category", params.category)
      const qs = searchParams.toString() ? `?${searchParams.toString()}` : ""
      return fetchApi<{ total: number; limit: number; offset: number; events: any[] }>(`/myntra/history${qs}`)
    },
    submitFeedback: (product_id: string, feedback: string) =>
      fetchApi<{ product_id: string; feedback: string }>("/myntra/feedback", {
        method: "POST",
        body: JSON.stringify({ product_id, feedback }),
      }),
    exportCsvUrl: `${API_BASE}/myntra/export.csv`,
    getRecentlyViewed: (limit = 15) =>
      fetchApi<{ total_events: number; products: any[] }>(`/myntra/history/products?limit=${limit}`),
  },
  touristSpots: {
    getAll: (category?: string, price_tier?: string) => {
      const params = new URLSearchParams()
      if (category && category !== "all") params.append("category", category)
      if (price_tier) params.append("price_tier", price_tier)
      const qs = params.toString() ? `?${params.toString()}` : ""
      return fetchApi<import("./types").TouristSpot[]>(`/tourist-spots${qs}`)
    },
    getRecommendations: async (limit = 20): Promise<import("./types").Recommendation[]> => {
      try {
        const spots = await fetchApi<import("./types").TouristSpot[]>(`/tourist-spots/recommendations?limit=${limit}`);
        return (spots || []).map((s, idx) => ({
          id: s.place_id,
          title: s.name,
          reason: s.description || `${s.category?.replace(/_/g, " ")} • ${s.city}`,
          imageUrl: "",
          score: Math.max(95 - idx * 2, 70),
          category: "places" as const,
        }));
      } catch (e) {
        console.error("Tourist spots recommendations error", e);
        return [];
      }
    },
    getById: (place_id: string) =>
      fetchApi<import("./types").TouristSpot>(`/tourist-spots/${place_id}`),
    feedback: (place_id: string, rating: number, tag?: string) =>
      fetchApi<import("./types").SpotFeedbackResponse>(`/tourist-spots/${place_id}/feedback`, {
        method: "POST",
        body: JSON.stringify({ rating, ...(tag ? { tag } : {}) }),
      }),
  },
  spotify: {
    loginUrl: `${API_BASE}/spotify/login`,
    disconnect: () =>
      fetchApi<{ status: string; message: string }>("/spotify/disconnect", { method: "POST" }),
    getMusicFeed: (limit = 50) =>
      fetchApi<{ items: MusicTrack[]; count: number }>(`/spotify/music-feed?limit=${limit}`),
    getSyncStatus: () =>
      fetchApi<{ sync_enabled: boolean; last_synced_at: string | null }>("/spotify/sync/status"),
    triggerSync: () =>
      fetchApi<Record<string, unknown>>("/spotify/sync/trigger", { method: "POST" }),
  },
}

export interface MusicTrack {
  track_id: string
  track_name: string
  artist_names: string[]
  album_name: string | null
  album_image_url: string | null
  played_at: string | null
  duration_ms: number | null
}

