import { useEffect, useState } from "react"
import { api } from "./api"
import { AmbientBackground } from "./components/ui/AmbientBackground"
import { Component as LoginPage } from "./components/ui/animated-characters-login-page"
import { Sidebar } from "./components/dashboard/Sidebar"
import { DashboardHome } from "./components/dashboard/DashboardHome"
import { AnimeGrid } from "./components/anime/AnimeGrid"
import { AnimeDetail } from "./components/anime/AnimeDetail"
import { ConvergenceHalo } from "./components/dashboard/ConvergenceHalo"
import { OnboardingWizard } from "./components/onboarding/OnboardingWizard"
import { cn } from "@/lib/utils"
import { Button, Input } from "./components/ui"
import { Search, Loader2 } from "lucide-react"
import { colors } from "./tokens"
import { Card, LineRail } from "./components/interchange"
import { ThemeProvider } from "./components/ui/ThemeProvider"
import { ThemeToggleButton } from "./components/ui/ThemeToggleButton"
import { TouristSpotsPage } from "./pages/TouristSpotsPage"
import { MyntraPage } from "./pages/MyntraPage"
import { SignalCard, DOMAIN } from "./components/dashboard/RecommendationRow"
import type { PageId, Recommendation } from "./types"

// ── Domain accent constants ──────────────────────────────────────────
const MUSIC_ACCENT = colors.music

// ── Derive wizard resume step from OAuth redirect params ────────────
function detectResumeStep(): number {
  const params = new URLSearchParams(window.location.search)
  const spotifyDone = params.get("spotify") === "connected"
  const anilistDone = params.get("anilist") === "connected"

  // Clean params from URL without triggering a reload
  if (spotifyDone || anilistDone) {
    const clean = window.location.pathname + window.location.hash
    window.history.replaceState(null, "", clean)
  }

  if (spotifyDone && anilistDone) return 3 // Done step
  if (anilistDone)                return 3 // Done step
  if (spotifyDone)                return 2 // AniList step
  return 0
}

export default function App() {
  const [user,           setUser]           = useState<{ user_id: string; name?: string | null } | null>(null)
  const [loading,        setLoading]        = useState(true)
  const [showOnboarding, setShowOnboarding] = useState(false)
  // Computed once on mount so it's stable across re-renders
  const [wizardStep]                        = useState(() => detectResumeStep())

  useEffect(() => {
    const hash  = window.location.hash
    const match = hash.match(/id_token=([^&]+)/)

    if (match) {
      const idToken = match[1]
      window.location.hash = ""
      api.auth.googleCallback(idToken)
        .then(() => window.location.reload())
        .catch(() => {
          window.location.hash = hash
          checkSession()
        })
      return
    }

    checkSession()

    function checkSession() {
      api.auth.me()
        .then((u) => {
          setUser(u)
          // ── Onboarding gate ──────────────────────────────────────
          const doneKey = `onboarding_done_${u.user_id}`
          if (localStorage.getItem(doneKey)) {
            // Already completed onboarding
            setShowOnboarding(false)
            return
          }
          // Check connection status; if endpoint is absent or all
          // connected, skip wizard; otherwise show it.
          api.connections.getStatus()
            .then((status) => {
              const fullyConnected = status.spotify && status.anilist
              if (fullyConnected) {
                localStorage.setItem(doneKey, "true")
                setShowOnboarding(false)
              } else {
                setShowOnboarding(true)
              }
            })
            .catch(() => {
              // /connections/status not yet live — show wizard so user
              // can still connect services opportunistically.
              setShowOnboarding(true)
            })
        })
        .catch(() => setUser(null))
        .finally(() => setLoading(false))
    }
  }, [])

  return (
    <ThemeProvider>
      <AmbientBackground />
      {loading ? (
        <div className="flex h-screen items-center justify-center bg-transparent">
          <div className="flex flex-col items-center gap-4">
            {/* Convergence ring spinner */}
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                background: "linear-gradient(135deg, #7C6CF0 0%, #3ED6C4 100%)",
                padding: 2,
                animation: "spin 1.2s linear infinite",
              }}
            >
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  borderRadius: "50%",
                  background: "#0A0E14",
                }}
              />
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            <p className="font-mono text-xs tracking-widest uppercase text-muted-foreground">
              Initializing…
            </p>
          </div>
        </div>
      ) : !user ? (
        <LoginPage />
      ) : showOnboarding ? (
        <OnboardingWizard
          userId={user.user_id}
          initialStep={wizardStep}
          onComplete={() => {
            localStorage.setItem(`onboarding_done_${user.user_id}`, "true")
            setShowOnboarding(false)
          }}
        />
      ) : (
        <DashboardLayout
          userId={user.user_id}
          userName={user.name || user.user_id}
          onLogout={() => {
            api.auth.logout().then(() => setUser(null))
          }}
        />
      )}
    </ThemeProvider>
  )
}

// ── Dashboard shell ──────────────────────────────────────────────────

function DashboardLayout({
  userId,
  userName,
  onLogout,
}: {
  userId: string
  userName?: string
  onLogout: () => void
}) {
  const [currentPage,    setCurrentPage]    = useState<PageId>("home")
  const [selectedAnime,  setSelectedAnime]  = useState<any | null>(null)
  const [collapsed,      setCollapsed]      = useState(false)
  const [connections,    setConnections]    = useState<{ spotify: boolean; anilist: boolean; location: boolean; myntra: boolean } | null>(null)

  useEffect(() => {
    api.connections.getStatus()
      .then(setConnections)
      .catch((err) => {
        console.error("Failed to fetch connection status:", err)
        setConnections({ spotify: false, anilist: false, location: false, myntra: false })
      })
  }, [])

  const handleNavigate = (page: PageId, item?: any) => {
    if (page === "anime") {
      if (item) {
        setSelectedAnime({
          mal_id:       item.id,
          title:        item.title,
          cover_image:  item.imageUrl,
          score:        item.score,
          synopsis:     item.reason,
        })
      } else {
        setSelectedAnime(null)
      }
    }
    setCurrentPage(page)
  }

  return (
    <div className="flex min-h-screen w-full overflow-x-hidden bg-transparent">
      <Sidebar
        currentPage={currentPage}
        onNavigate={handleNavigate}
        onLogout={onLogout}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        connections={connections}
      />

      <div
        className={cn(
          "flex-1 min-w-0 transition-all duration-300",
          collapsed ? "md:ml-[72px]" : "md:ml-[240px]"
        )}
      >
        {currentPage === "home" && (
          <DashboardHome
            userName={userName || userId}
            onLogout={onLogout}
            onNavigate={handleNavigate}
            connections={connections}
          />
        )}
        {currentPage === "anime" && (
          <PageWrapper title="Anime">
            <AnimeModule
              externalSelectedAnime={selectedAnime}
              onExternalSelectAnime={setSelectedAnime}
            />
          </PageWrapper>
        )}
        {currentPage === "music" && (
          <PageWrapper title="Music Recommendations">
            <MusicRecommendationsPage isConnected={connections?.spotify ?? false} />
          </PageWrapper>
        )}
        {currentPage === "places" && (
          <PageWrapper title="Places">
            <TouristSpotsPage />
          </PageWrapper>
        )}
        {currentPage === "myntra" && (
          <PageWrapper title="Fashion">
            <MyntraPage />
          </PageWrapper>
        )}
        {currentPage === "movies" && (
          <PageWrapper title="Movies">
            <MoviesRecommendationsPage />
          </PageWrapper>
        )}
        {currentPage === "profile" && (
          <PageWrapper title="Taste Profile">
            <TasteProfileModule />
          </PageWrapper>
        )}
        {currentPage === "settings" && (
          <PageWrapper title="Settings">
            <SettingsSection />
          </PageWrapper>
        )}
      </div>
    </div>
  )
}

// ── Page wrapper ─────────────────────────────────────────────────────

function PageWrapper({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col min-h-screen bg-[#FAFAFA] dark:bg-[#0A0A0B] transition-colors duration-150 ease-out">
      {/* Sticky page top bar with theme toggle */}
      <div className="sticky top-0 z-30 flex items-center justify-between gap-4 px-4 md:px-6 py-3 bg-[#FFFFFF] dark:bg-[#18181B] border-b border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out">
        <h1 className="text-sm font-semibold text-[#18181B] dark:text-[#FAFAFA] transition-colors duration-150 ease-out">
          {title ?? ""}
        </h1>
        <ThemeToggleButton />
      </div>
      <div className="flex-1 p-4 md:p-6 lg:p-8 pb-24 md:pb-8">
        {children}
      </div>
    </div>
  )
}

// ── Settings section ─────────────────────────────────────────────────

function SettingsSection() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-display font-bold text-foreground">Preferences</h2>
      <Card className="relative overflow-hidden">
        <div className="p-6">
          <p className="text-sm font-sans text-muted-foreground">
            More settings coming soon. Your taste signals are already being tuned automatically.
          </p>
        </div>
      </Card>
    </div>
  )
}

function MusicRecommendationsPage({ isConnected }: { isConnected: boolean }) {
  const [recommendations, setRecommendations] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.recommendations.getByCategory("music")
      .then((recs) => setRecommendations(recs))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="flex justify-center p-12"><Loader2 className="animate-spin text-muted-foreground" size={24} /></div>
  }

  if (recommendations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
        {!isConnected ? (
          <>
            <p className="text-sm text-muted-foreground max-w-sm">
              Connect Spotify to get personalized music recommendations based on your listening history.
            </p>
            <div className="flex gap-3 mt-2">
              <Button
                onClick={() => window.location.href = api.spotify.loginUrl}
                style={{ backgroundColor: "#1DB954", color: "#fff" }}
              >
                Connect Spotify
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground max-w-sm">
              Your Spotify is connected, but we don't have enough signals yet. Make sure you've synced your recently played history in the Taste Profile page!
            </p>
            <div className="flex gap-3 mt-2">
              <Button
                variant="outline"
                className="text-xs"
                onClick={() => {
                  if (confirm("Disconnect Spotify and unlink account?")) {
                    api.spotify.disconnect().then(() => window.location.reload())
                  }
                }}
              >
                Disconnect Spotify
              </Button>
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-wrap gap-4 p-4">
      {recommendations.map((r, i) => (
        <SignalCard 
          key={r.id} 
          item={r} 
          index={i} 
          category="music"
          meta={DOMAIN.music}
          onNavigate={() => {}}
        />
      ))}
    </div>
  )
}

function MoviesRecommendationsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    api.recommendations.getByCategory("movie")
      .then((recs) => { setRecommendations(recs); setError(null) })
      .catch((err) => setError(err.message || "Failed to load movie recommendations."))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading movie recommendations…</div>
  }
  if (error) {
    return <div className="p-6 text-sm text-red-500">{error}</div>
  }
  if (recommendations.length === 0) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        No movie recommendations yet — rate or like some movies to build your taste profile.
      </div>
    )
  }

  return (
    <div className="flex flex-wrap gap-4 p-4">
      {recommendations.map((r, i) => (
        <SignalCard
          key={r.id}
          item={r}
          index={i}
          category="movie"
          meta={DOMAIN.movie}
          onNavigate={() => {}}
        />
      ))}
    </div>
  )
}

// ── Music section ────────────────────────────────────────────────────

function MusicSection({ isConnected }: { isConnected?: boolean }) {
  type Track = import("./api").MusicTrack
  const [tracks, setTracks] = useState<Track[]>([])
  const [syncStatus, setSyncStatus] = useState<{ sync_enabled: boolean; last_synced_at: string | null } | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!isConnected) return
    setLoading(true)
    Promise.all([
      api.spotify.getMusicFeed(50).catch(() => ({ items: [], count: 0 })),
      api.spotify.getSyncStatus().catch(() => null),
    ]).then(([feed, status]) => {
      setTracks(feed.items)
      setSyncStatus(status)
    }).finally(() => setLoading(false))
  }, [isConnected])

  function handleDisconnect() {
    if (!confirm("Are you sure you want to disconnect Spotify?")) return
    setDisconnecting(true)
    api.spotify.disconnect()
      .then(() => window.location.reload())
      .catch((e: any) => alert(e.message || "Failed to disconnect Spotify"))
      .finally(() => setDisconnecting(false))
  }

  function handleSync() {
    setSyncing(true)
    setSyncMsg(null)
    api.spotify.triggerSync()
      .then((res: any) => {
        const statusMsgMap: Record<string, string> = {
          ok: `Synced ${res.new_tracks ?? 0} new tracks ✓`,
          already_up_to_date: "Already up to date",
          no_new_plays: "Already up to date",
          sync_disabled: "Sync not enabled — reconnect Spotify",
          token_invalid: "Spotify token expired — reconnect Spotify",
        }
        if (res.status === "error") {
          setSyncMsg(res.error || res.detail || "Sync failed — please try again")
        } else {
          setSyncMsg(statusMsgMap[res.status] ?? res.status ?? "Done")
        }
        return api.spotify.getMusicFeed(50)
      })
      .then(feed => setTracks(feed.items))
      .catch((e: any) => setSyncMsg(e.message ?? "Sync failed"))
      .finally(() => setSyncing(false))
  }

  function fmtTime(iso: string | null) {
    if (!iso) return ""
    try {
      return new Date(iso + "Z").toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    } catch { return iso }
  }

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-6">
        <div
          className="w-16 h-16 flex items-center justify-center rounded-full"
          style={{
            background: `linear-gradient(135deg, ${MUSIC_ACCENT}30, transparent)`,
            border: `1px solid ${MUSIC_ACCENT}40`,
            boxShadow: `0 0 32px ${MUSIC_ACCENT}30`,
          }}
        >
          <span style={{ fontSize: 28, color: MUSIC_ACCENT }}>♪</span>
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-display font-bold text-foreground">No music signals yet</h2>
          <p className="text-sm font-sans max-w-sm text-muted-foreground">
            Connect Spotify to activate your music signal — we'll learn your vibe from every listen.
          </p>
        </div>
        <a
          href={api.spotify.loginUrl}
          className="inline-flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-sans font-semibold transition-all duration-200 hover:scale-[1.02] active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7C6CF0] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0E14]"
          style={{
            backgroundColor: `${MUSIC_ACCENT}20`,
            color:            MUSIC_ACCENT,
            border:           `1px solid ${MUSIC_ACCENT}40`,
            boxShadow:        `0 0 20px ${MUSIC_ACCENT}20`,
          }}
        >
          Connect Spotify
        </a>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 py-4">
      {/* Header row */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 20, color: MUSIC_ACCENT }}>♪</span>
          <span className="text-sm font-display font-semibold text-foreground">
            Recently Played
            {tracks.length > 0 && <span className="ml-1 text-muted-foreground font-normal">({tracks.length})</span>}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {syncStatus?.last_synced_at && (
            <span className="text-xs text-muted-foreground hidden sm:block">
              Last sync {fmtTime(syncStatus.last_synced_at)}
            </span>
          )}
          <button
            onClick={handleSync}
            disabled={syncing}
            className="text-xs rounded-lg px-3 py-1.5 font-sans font-medium transition-all duration-150 hover:scale-[1.02] active:scale-[0.97] disabled:opacity-50"
            style={{
              backgroundColor: `${MUSIC_ACCENT}15`,
              color: MUSIC_ACCENT,
              border: `1px solid ${MUSIC_ACCENT}30`,
            }}
          >
            {syncing ? "Syncing…" : "↻ Sync now"}
          </button>
          <button
            onClick={handleDisconnect}
            disabled={disconnecting}
            className="text-xs rounded-lg px-2.5 py-1.5 font-sans text-red-500 hover:text-red-600 dark:text-red-400 border border-red-500/20 hover:bg-red-500/10 transition-all disabled:opacity-50"
          >
            {disconnecting ? "Disconnecting…" : "Disconnect"}
          </button>
        </div>
      </div>

      {syncMsg && (
        <p className="text-xs text-center" style={{ color: MUSIC_ACCENT }}>{syncMsg}</p>
      )}

      {/* Track list */}
      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="animate-spin text-muted-foreground" size={22} />
        </div>
      ) : tracks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
          <p className="text-sm text-muted-foreground max-w-xs">
            {syncStatus?.last_synced_at
              ? "We synced your Spotify, but didn't find any recently finished tracks. Play some music and check back! (Note: Spotify only syncs tracks after they finish playing)"
              : "Your Spotify is connected but no play history is synced yet. Hit Sync now to pull in your recent listens."}
          </p>
          <a
            href={api.spotify.loginUrl}
            className="text-xs underline underline-offset-2"
            style={{ color: MUSIC_ACCENT }}
          >
            Reconnect Spotify
          </a>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {tracks.map((t, i) => (
            <div
              key={`${t.track_id}-${i}`}
              className="flex items-center gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-white/5"
            >
              {/* Album art */}
              {t.album_image_url ? (
                <img
                  src={t.album_image_url}
                  alt={t.album_name ?? ""}
                  className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
                  style={{ boxShadow: `0 2px 8px ${MUSIC_ACCENT}20` }}
                />
              ) : (
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: `${MUSIC_ACCENT}20`, border: `1px solid ${MUSIC_ACCENT}30` }}
                >
                  <span style={{ fontSize: 16, color: MUSIC_ACCENT }}>♪</span>
                </div>
              )}

              {/* Track info */}
              <div className="flex flex-col min-w-0 flex-1">
                <span className="text-sm font-sans font-medium text-foreground truncate">{t.track_name}</span>
                <span className="text-xs text-muted-foreground truncate">{t.artist_names.join(", ")}</span>
              </div>

              {/* Played time */}
              <span className="text-xs text-muted-foreground flex-shrink-0 hidden sm:block">
                {fmtTime(t.played_at)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Reconnect link (only when tracks exist, since empty state already has reconnect prompt) */}
      {tracks.length > 0 && (
        <div className="pt-2 text-center">
          <a
            href={api.spotify.loginUrl}
            className="text-xs underline underline-offset-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            Reconnect Spotify
          </a>
        </div>
      )}
    </div>
  )
}


// ── Anime sub-module ─────────────────────────────────────────────────

function AnimeModule({
  externalSelectedAnime,
  onExternalSelectAnime,
}: {
  externalSelectedAnime?: any
  onExternalSelectAnime?: (anime: any) => void
}) {
  const [query,          setQuery]          = useState("")
  const [results,        setResults]        = useState<any[]>([])
  const [upcoming,       setUpcoming]       = useState<any[]>([])
  const [recommendations, setRecommendations] = useState<any[]>([])
  const [loading,        setLoading]        = useState(false)
  const [loadingUpcoming, setLoadingUpcoming] = useState(true)
  const [loadingRecs,    setLoadingRecs]    = useState(true)
  const [localSelected,  setLocalSelected]  = useState<any | null>(null)

  const selectedAnime  = externalSelectedAnime !== undefined ? externalSelectedAnime : localSelected
  const setSelectedAnime = onExternalSelectAnime || setLocalSelected

  useEffect(() => {
    api.anime.getUpcoming()
      .then((res) => setUpcoming((res as { upcoming?: any[] }).upcoming || []))
      .catch(console.error)
      .finally(() => setLoadingUpcoming(false))

    api.anime.getDashboardRecommendations()
      .then((res) => setRecommendations(res || []))
      .catch(console.error)
      .finally(() => setLoadingRecs(false))
  }, [])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query) { setResults([]); return }
    setLoading(true)
    try {
      setResults(await api.anime.search(query))
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  if (selectedAnime) {
    return (
      <AnimeDetail
        anime={selectedAnime}
        onBack={() => setSelectedAnime(null)}
        onSelect={setSelectedAnime}
      />
    )
  }

  const showResults = query && results.length > 0

  return (
    <div className="space-y-8">
      {/* Search bar */}
      <Card className="p-4 rounded-xl relative overflow-hidden">
        <form onSubmit={handleSearch} className="flex gap-2 w-full max-w-lg">
          <Input
            placeholder="Search anime by title…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search anime"
          />
          <Button type="submit" id="btn-anime-search" style={{ backgroundColor: "#FF7A59", color: "#fff" }}>
            <Search className="h-4 w-4 mr-2" />
            Search
          </Button>
        </form>
      </Card>

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="animate-spin w-8 h-8" style={{ color: "#FF7A59" }} />
        </div>
      ) : showResults ? (
        <section>
          <SectionHeader title="Search Results" color="#FF7A59" />
          <AnimeGrid animes={results} onSelect={setSelectedAnime} />
        </section>
      ) : (
        <div className="space-y-10">
          <section>
            <SectionHeader title="Recommended for You" color="#FF7A59" />
            {loadingRecs ? (
              <div className="flex justify-center p-12">
                <Loader2 className="animate-spin w-8 h-8" style={{ color: "#FF7A59" }} />
              </div>
            ) : recommendations.length === 0 ? (
              <p className="text-sm text-muted-foreground">Add anime to your Taste Profile to get recommendations.</p>
            ) : (
              <AnimeGrid animes={recommendations} onSelect={setSelectedAnime} />
            )}
          </section>

          <section>
            <SectionHeader title="Upcoming Anime" color="#FF7A59" />
            {loadingUpcoming ? (
              <div className="flex justify-center p-12">
                <Loader2 className="animate-spin w-8 h-8" style={{ color: "#FF7A59" }} />
              </div>
            ) : (
              <AnimeGrid animes={upcoming} onSelect={setSelectedAnime} />
            )}
          </section>
        </div>
      )}
    </div>
  )
}

// ── TasteProfileModule (unchanged structure, updated styles) ─────────

export function TasteProfileModule() {
  const [profile, setProfile] = useState<any>(null)
  const [convergence, setConvergence] = useState<{ score: number; segments: any[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.taste.getProfile()
      .then(setProfile)
      .catch(console.error)
      .finally(() => setLoading(false))

    api.taste.getConvergence()
      .then(setConvergence)
      .catch(console.error)
  }, [])

  if (loading) return (
    <div className="flex h-64 items-center justify-center">
      <Loader2 className="animate-spin w-8 h-8" style={{ color: "#7C6CF0" }} />
    </div>
  )

  if (!profile) return (
    <div className="flex h-64 items-center justify-center">
      <p className="text-center text-muted-foreground font-sans">
        Failed to load taste profile.
      </p>
    </div>
  )

  // Convert profile object to sorted array for display
  const topGenres = Object.entries(profile.profile || {})
    .sort(([, a]: any, [, b]: any) => b - a)
    .slice(0, 5)

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header & Halo */}
      <div className="flex flex-col items-center justify-center py-8">
        <ConvergenceHalo score={convergence?.score} data={convergence?.segments} />
        <div className="text-center mt-6 space-y-2">
          <h2 className="text-2xl font-display font-bold text-foreground">
            Your Taste Profile
          </h2>
          <p className="text-sm font-sans text-muted-foreground max-w-md mx-auto">
            This is the unified model of your preferences across all domains.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ProfileCard title="Top Unified Signals">
          {topGenres.length > 0 ? (
            topGenres.map(([genre, score]: any) => (
              <li key={genre} className="flex justify-between font-sans text-sm capitalize text-foreground py-1">
                <span>{genre}</span>
                <span className="font-mono text-xs text-muted-foreground">
                  {Math.round(score)} pts
                </span>
              </li>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No signals detected yet.</p>
          )}
        </ProfileCard>

        <div className="space-y-6">
          <Card className="relative overflow-hidden">
            <div className="px-5 py-4 border-b border-[#E4E4E7] dark:border-[#27272A]">
              <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                Domain Activity
              </h3>
            </div>
            <div className="p-5 flex flex-wrap gap-6 md:gap-8">
              <StatBlock label="Anime Liked"            value={Object.keys(profile.breakdown?.anime || {}).length}              color="#FF7A59" />
              <StatBlock label="AniList Genres"         value={Object.keys(profile.breakdown?.anilist || {}).length}            color="#4A90E2" />
              <StatBlock label="Places Rated"           value={profile.places_rated_count ?? 0}                                 color="#E3A857" />
              <StatBlock label="Movies Rated"           value={Object.keys(profile.breakdown?.movie || {}).length}              color="#6366F1" />
              <StatBlock label="Fashion Interactions"   value={Object.keys(profile.breakdown?.myntra?.styles || {}).length}     color="#D946EF" />
            </div>
          </Card>
          
          <Card className="p-5 relative overflow-hidden">
             <LineRail domain="music" />
             <div className="flex items-center gap-3 pl-3">
               <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                 Spotify Connection
               </h3>
             </div>
             <p className="text-sm font-sans text-muted-foreground mt-2">
               {profile.spotify_connected 
                 ? "Your music taste is actively influencing your recommendations across anime."
                 : "Connect Spotify to unlock full cross-domain convergence."}
             </p>
             {!profile.spotify_connected && (
               <Button
                 className="mt-4"
                 style={{ backgroundColor: "#7C6CF0", color: "#fff" }}
                 onClick={() => window.location.href = api.spotify.loginUrl}
               >
                 Connect Spotify
               </Button>
             )}
             
             {profile.spotify_connected && (
               <div className="mt-6 border-t border-[#E4E4E7] dark:border-[#27272A] pt-4">
                 <MusicSection isConnected={true} />
               </div>
             )}
          </Card>

          <Card className="p-5 relative overflow-hidden">
             <LineRail domain="anime" />
             <div className="flex items-center gap-3 pl-3">
               <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                 AniList Connection
               </h3>
             </div>
             <p className="text-sm font-sans text-muted-foreground mt-2">
               {profile.anilist_connected 
                 ? "Your AniList profile is connected and actively influencing your recommendation signals."
                 : "Connect AniList to unlock full cross-domain convergence."}
             </p>
             {!profile.anilist_connected && (
               <Button
                 className="mt-4"
                 style={{ backgroundColor: "#4A90E2", color: "#fff" }}
                 onClick={() => window.location.href = api.anilist.loginUrl}
               >
                 Connect AniList
               </Button>
             )}
          </Card>
        </div>
      </div>

      {profile.anilist_watched && profile.anilist_watched.length > 0 && (
        <Card className="p-5 relative overflow-hidden">
          <LineRail domain="anime" />
          <div className="flex items-center gap-3 mb-4 pl-3">
            <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
              Watched on AniList
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {profile.anilist_watched.map((item: any) => (
              <div 
                key={item.mal_id} 
                className="p-3 rounded-lg bg-black/[0.02] dark:bg-white/[0.02] border border-[#E4E4E7] dark:border-[#27272A] flex flex-col justify-between"
              >
                <span className="text-sm font-sans font-medium text-foreground line-clamp-1">{item.title}</span>
                <div className="flex items-center justify-between mt-2 text-xs font-mono">
                  <span className="text-muted-foreground uppercase">{item.status.toLowerCase()}</span>
                  {item.score > 0 ? (
                    <span style={{ color: "#FF7A59" }}>{item.score} / 10</span>
                  ) : (
                    <span className="text-muted-foreground">Unscored</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string; color?: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <LineRail domain="anime" />
      <h2 className="text-base font-display font-semibold tracking-wide uppercase text-foreground pl-3">
        {title}
      </h2>
    </div>
  )
}

function ProfileCard({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <Card className="overflow-hidden relative">
      <div className="px-5 py-4 border-b border-[#E4E4E7] dark:border-[#27272A] pl-6">
        <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
          {title}
        </h3>
      </div>
      <div className="p-5 pl-6">
        <ul className="space-y-2">{children}</ul>
      </div>
    </Card>
  )
}

function StatBlock({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  return (
    <div>
      <p
        className="text-2xl font-display font-bold"
        style={{ color }}
      >
        {value}
      </p>
      <p className="text-xs font-sans text-muted-foreground mt-0.5">{label}</p>
    </div>
  )
}
