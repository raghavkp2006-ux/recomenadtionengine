/**
 * API client helpers for the Profile section.
 */

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Unauthorized");
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${response.status}`);
  }

  return response.json();
}

export interface ProfileOverview {
  name: string | null;
  email: string | null;
  avatar_url: string | null;
  member_since: string | null;
  spotify: {
    display_name: string;
    avatar: string | null;
  } | null;
  counts: {
    movies_rated: number;
    places_rated: number;
    anime_logged: number;
    products_viewed: number;
    tracks_liked: number;
  };
}

export interface ConnectionItem {
  domain: "spotify" | "anilist" | "myntra" | "movies" | "places" | "dining";
  connected: boolean;
  last_synced_at: string | null;
  status: "ok" | "error" | "needs_reconnect" | "never";
  items_count: number;
  error_message: string | null;
  token_expires_at?: number | null;
  products_captured?: number;
  last_event_at?: string | null;
}

export interface ResyncResponse {
  domain: string;
  status: string;
  items_count: number;
  new_items?: number;
  synced_at: string;
  error_message?: string | null;
}

export interface TasteControlsData {
  user_id?: string;
  domain_weights: {
    music: number;
    anime: number;
    movies: number;
    fashion: number;
  };
  sliders: {
    energy: number;
    obscurity: number;
    novelty: number;
  };
  pinned: {
    artists: string[];
    genres: string[];
  };
  hidden: {
    artists: string[];
    genres: string[];
  };
  updated_at?: string | null;
}

export interface FeedbackHistoryItem {
  id: number;
  domain: string;
  item_id: string;
  title?: string;
  action: string;
  created_at: string;
}

export interface TimelineItem {
  domain: "spotify" | "anilist" | "movies" | "places" | "dining" | "myntra";
  title: string;
  subtitle?: string;
  image?: string | null;
  at: string;
}

export interface TasteBridge {
  from: { domain: string; label: string };
  to: { domain: string; label: string };
  strength: number;
  reason: string;
}

export interface PublicProfileVisibility {
  genres: boolean;
  top_artists: boolean;
  stats: boolean;
  connections: boolean;
  personality: boolean;
}

export interface PublicProfileData {
  user_id?: string;
  slug: string | null;
  is_public: boolean;
  visibility: PublicProfileVisibility;
  updated_at?: string | null;
}

export const profileApi = {
  getOverview: () => fetchApi<ProfileOverview>("/profile/overview"),
  getConnections: () => fetchApi<ConnectionItem[]>("/profile/connections"),
  resyncConnection: (domain: string) =>
    fetchApi<ResyncResponse>(`/profile/connections/${domain}/resync`, { method: "POST" }),
  disconnectConnection: (domain: string) =>
    fetchApi<{ ok: boolean; domain: string; message: string }>(
      `/profile/connections/${domain}?confirm=true`,
      { method: "DELETE" }
    ),
  getControls: () => fetchApi<TasteControlsData>("/profile/controls"),
  updateControls: (data: Partial<TasteControlsData>) =>
    fetchApi<TasteControlsData>("/profile/controls", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  getFeedbackHistory: (domain: string = "", limit: number = 50, offset: number = 0) =>
    fetchApi<FeedbackHistoryItem[]>(
      `/profile/feedback-history?limit=${limit}&offset=${offset}${domain ? `&domain=${domain}` : ""}`
    ),
  resetFeedbackHistory: (domain: string = "") =>
    fetchApi<{ ok: boolean; deleted: number }>(
      `/profile/feedback-history?confirm=true${domain ? `&domain=${domain}` : ""}`,
      { method: "DELETE" }
    ),
  getTimeline: (limit: number = 50) =>
    fetchApi<TimelineItem[]>(`/profile/timeline?limit=${limit}`),
  getBridges: () => fetchApi<TasteBridge[]>("/profile/bridges"),
  getTasteTags: () => fetchApi<string[]>("/profile/taste-tags"),
  getVisibility: () => fetchApi<PublicProfileData>("/profile/visibility"),
  updateVisibility: (data: { is_public: boolean; visibility: Partial<PublicProfileVisibility> }) =>
    fetchApi<PublicProfileData>("/profile/visibility", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  getPublicProfile: (slug: string) =>
    fetchApi<any>(`/public/profile/${slug}`),
  getCompatibility: (slug: string) =>
    fetchApi<{ score_pct: number; shared_genres: string[]; shared_artists: string[] }>(
      `/profile/compatibility/${slug}`
    ),
  exportDataUrl: `${API_BASE}/profile/export`,
  deleteUserData: () =>
    fetchApi<{ ok: boolean; message: string }>("/profile/data?confirm=DELETE", {
      method: "DELETE",
    }),
  createPlaylist: (name: string, range: "short" | "medium" | "long" = "medium") =>
    fetchApi<{ ok: boolean; playlist_url: string; tracks_count: number }>(
      "/profile/playlist",
      {
        method: "POST",
        body: JSON.stringify({ name, range }),
      }
    ),
};
