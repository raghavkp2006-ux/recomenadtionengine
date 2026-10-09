import { useState, useEffect } from "react";
import {
  Sparkles,
  Loader2,
  Tv,
  Music,
  Compass,
  Film,
  ShoppingBag,
  RefreshCw,
  TrendingUp,
  CheckCircle2,
  Sliders,
  ArrowRight,
} from "lucide-react";
import { api } from "../api";
import { Card } from "../components/interchange/Card";
import { LineRail } from "../components/interchange/LineRail";
import { Button } from "../components/ui/button";
import { ConvergenceHalo } from "../components/dashboard/ConvergenceHalo";
import { GenreRadar } from "../components/profile/charts/GenreRadar";
import { BridgesPanel } from "../components/profile/BridgesPanel";
import { profileApi, type TasteBridge } from "../api/profile";
import type { PageId } from "../types";
import { cn } from "@/lib/utils";

interface TasteProfilePageProps {
  onNavigate?: (page: PageId) => void;
}

export function TasteProfilePage({ onNavigate }: TasteProfilePageProps) {
  const [profile, setProfile] = useState<any>(null);
  const [convergence, setConvergence] = useState<{ score: number; segments: any[] } | null>(null);
  const [bridges, setBridges] = useState<TasteBridge[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [syncingSpotify, setSyncingSpotify] = useState(false);

  const loadData = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const [profData, convData, bridgeData] = await Promise.allSettled([
        api.taste.getProfile(),
        api.taste.getConvergence(),
        profileApi.getBridges(),
      ]);

      if (profData.status === "fulfilled") setProfile(profData.value);
      if (convData.status === "fulfilled") setConvergence(convData.value);
      if (bridgeData.status === "fulfilled") setBridges(bridgeData.value);
    } catch (err) {
      console.error("[TasteProfilePage] load error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSpotifySync = async () => {
    setSyncingSpotify(true);
    setSyncMsg(null);
    try {
      const res: any = await api.spotify.triggerSync();
      setSyncMsg(res.status === "ok" ? `Synced ${res.new_tracks ?? 0} tracks!` : "Up to date");
      await loadData(true);
    } catch {
      setSyncMsg("Sync failed");
    } finally {
      setSyncingSpotify(false);
      setTimeout(() => setSyncMsg(null), 4000);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-4">
        <Loader2 className="w-8 h-8 animate-spin text-[#7C6CF0]" />
        <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          Synthesizing taste model…
        </p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="max-w-xl mx-auto p-8 text-center space-y-4">
        <p className="text-muted-foreground font-sans">
          Failed to load taste profile signals.
        </p>
        <Button onClick={() => loadData(true)} variant="outline" size="sm">
          Try Again
        </Button>
      </div>
    );
  }

  // Sorted top genres from profile
  const sortedSignals = Object.entries(profile.profile || {})
    .sort(([, a]: any, [, b]: any) => (b as number) - (a as number));
  const topFive = sortedSignals.slice(0, 5);
  const maxScore = topFive.length > 0 ? (topFive[0][1] as number) : 1;

  // Radar data format
  const radarGenres = sortedSignals.slice(0, 6).map(([g, w]) => ({
    genre: g,
    weight: typeof w === "number" ? w : 1,
  }));

  const convScore = convergence?.score ?? 0;
  let archetype = "Unified Synthesizer";
  if (convScore > 75) archetype = "Cross-Domain Synergist";
  else if (convScore > 50) archetype = "Balanced Eclectic";
  else archetype = "Emerging Explorer";

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-8">
      {/* Top Header Card */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#E4E4E7] dark:border-[#27272A]">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-display font-bold text-foreground">
              Your Taste Profile
            </h1>
            <span className="px-2.5 py-0.5 text-[11px] font-mono uppercase tracking-wide rounded-full bg-[#7C6CF0]/10 text-[#7C6CF0] border border-[#7C6CF0]/20 font-semibold">
              {archetype}
            </span>
          </div>
          <p className="text-sm font-sans text-muted-foreground mt-1">
            Unified mathematical representation of your preferences across music, anime, cinema, fashion, and places.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono rounded-lg border border-[#E4E4E7] dark:border-[#27272A] hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
            title="Recalculate signals"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", refreshing && "animate-spin")} />
            <span>{refreshing ? "Refreshing..." : "Recalculate"}</span>
          </button>
          {onNavigate && (
            <button
              onClick={() => onNavigate("settings")}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg bg-[#2563EB] text-white hover:bg-[#1D4ED8] transition-colors cursor-pointer"
              title="Tune weights in Settings"
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Algorithm Settings</span>
            </button>
          )}
        </div>
      </div>

      {/* Hero Visual Section: Convergence Halo + Genre Radar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Convergence Halo Card */}
        <Card className="lg:col-span-6 p-6 flex flex-col items-center justify-center relative overflow-hidden bg-gradient-to-b from-[#7C6CF0]/5 to-transparent">
          <LineRail domain="music" />
          <ConvergenceHalo score={convergence?.score} data={convergence?.segments} />
          <div className="mt-4 text-center max-w-sm space-y-1">
            <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Convergence Score: <span className="font-bold text-foreground">{Math.round(convScore)}%</span>
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Measures how strongly signals from one media correlate and enrich recommendations across all other domains.
            </p>
          </div>
        </Card>

        {/* Genre Radar Card */}
        <Card className="lg:col-span-6 p-6 flex flex-col justify-between relative overflow-hidden">
          <LineRail domain="anime" />
          <div className="flex items-center justify-between pb-3 border-b border-[#E4E4E7] dark:border-[#27272A] pl-3">
            <div>
              <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                Taste Balance Polygon
              </h3>
              <p className="text-xs text-muted-foreground">
                Relative dispersion across dominant genres
              </p>
            </div>
            <Sparkles className="w-4 h-4 text-[#7C6CF0]" />
          </div>

          <div className="flex items-center justify-center py-2">
            {radarGenres.length >= 3 ? (
              <GenreRadar genres={radarGenres} size={260} />
            ) : (
              <div className="h-56 flex items-center justify-center text-xs text-muted-foreground font-mono">
                Log more ratings to generate radar polygon
              </div>
            )}
          </div>

          <div className="text-center pt-2 border-t border-[#E4E4E7] dark:border-[#27272A]">
            <p className="text-xs text-muted-foreground font-sans">
              Top Anchor: <span className="font-semibold text-foreground capitalize">{topFive[0]?.[0] || "None"}</span> ({(topFive[0]?.[1] as number)?.toFixed(1) || 0} pts)
            </p>
          </div>
        </Card>
      </div>

      {/* Top Unified Signals & Domain Activity Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Top Unified Signals */}
        <Card className="lg:col-span-7 overflow-hidden relative">
          <div className="px-6 py-4 border-b border-[#E4E4E7] dark:border-[#27272A] flex items-center justify-between">
            <div>
              <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                Top Unified Signals
              </h3>
              <p className="text-xs text-muted-foreground">
                Aggregated cross-domain affinity scores
              </p>
            </div>
            <TrendingUp className="w-4 h-4 text-emerald-500" />
          </div>

          <div className="p-6 space-y-4">
            {topFive.length > 0 ? (
              topFive.map(([genre, score]: any, idx) => {
                const percentage = Math.min(100, Math.round(((score as number) / maxScore) * 100));
                return (
                  <div key={genre} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-sans">
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 flex items-center justify-center rounded text-[10px] font-mono font-bold bg-black/5 dark:bg-white/10 text-muted-foreground">
                          #{idx + 1}
                        </span>
                        <span className="font-medium text-foreground capitalize text-sm">{genre}</span>
                      </div>
                      <span className="font-mono text-muted-foreground text-xs">
                        {Math.round(score)} pts ({percentage}%)
                      </span>
                    </div>
                    {/* Visual Meter */}
                    <div className="w-full h-2 rounded-full bg-black/5 dark:bg-white/5 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500 ease-out"
                        style={{
                          width: `${percentage}%`,
                          backgroundColor:
                            idx === 0
                              ? "#7C6CF0"
                              : idx === 1
                              ? "#3ED6C4"
                              : idx === 2
                              ? "#FF7A59"
                              : idx === 3
                              ? "#E3A857"
                              : "#D946EF",
                        }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No signals detected yet. Rate anime, connect Spotify, or explore fashion to seed your taste.
              </p>
            )}
          </div>
        </Card>

        {/* Domain Activity Cards */}
        <Card className="lg:col-span-5 p-6 relative overflow-hidden flex flex-col justify-between">
          <div className="pb-3 border-b border-[#E4E4E7] dark:border-[#27272A]">
            <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
              Cross-Domain Activity
            </h3>
            <p className="text-xs text-muted-foreground">
              Active data streams feeding your model
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4 py-4">
            <div className="p-3.5 rounded-xl border border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] space-y-1">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Tv className="w-3.5 h-3.5 text-[#FF7A59]" />
                <span>Anime Liked</span>
              </div>
              <p className="text-xl font-display font-bold text-foreground">
                {Object.keys(profile.breakdown?.anime || {}).length}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] space-y-1">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Tv className="w-3.5 h-3.5 text-[#4A90E2]" />
                <span>AniList Synced</span>
              </div>
              <p className="text-xl font-display font-bold text-foreground">
                {Object.keys(profile.breakdown?.anilist || {}).length}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] space-y-1">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Compass className="w-3.5 h-3.5 text-[#E3A857]" />
                <span>Places Rated</span>
              </div>
              <p className="text-xl font-display font-bold text-foreground">
                {profile.places_rated_count ?? 0}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] space-y-1">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Film className="w-3.5 h-3.5 text-[#6366F1]" />
                <span>Movies Rated</span>
              </div>
              <p className="text-xl font-display font-bold text-foreground">
                {Object.keys(profile.breakdown?.movie || {}).length}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] space-y-1">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <ShoppingBag className="w-3.5 h-3.5 text-[#D946EF]" />
                <span>Fashion Signals</span>
              </div>
              <p className="text-xl font-display font-bold text-foreground">
                {Object.keys(profile.breakdown?.myntra?.styles || {}).length}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] space-y-1">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Music className="w-3.5 h-3.5 text-[#E8553F]" />
                <span>Spotify Plays</span>
              </div>
              <p className="text-xl font-display font-bold text-foreground">
                {profile.spotify_tracks_count ?? 0}
              </p>
            </div>
          </div>

          <div className="pt-2 text-center text-xs text-muted-foreground">
            {profile.spotify_connected && profile.anilist_connected ? (
              <span className="flex items-center justify-center gap-1.5 text-emerald-500 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" /> High Cross-Domain Fidelity
              </span>
            ) : (
              <span>Connect remaining services in Settings to unlock 100% convergence</span>
            )}
          </div>
        </Card>
      </div>

      {/* Cross-Domain Taste Bridges */}
      {bridges.length > 0 && <BridgesPanel bridges={bridges} />}

      {/* Connected Services Details (Spotify & AniList) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Spotify Connection Preview */}
        <Card className="p-6 relative overflow-hidden flex flex-col justify-between">
          <LineRail domain="music" />
          <div className="pl-3 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                Spotify Music Stream
              </h3>
              <span
                className={cn(
                  "px-2 py-0.5 text-[10px] font-mono rounded-full font-semibold uppercase",
                  profile.spotify_connected
                    ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                )}
              >
                {profile.spotify_connected ? "Connected" : "Disconnected"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {profile.spotify_connected
                ? "Your listening history actively tunes recommendation algorithms across anime and tourism spots."
                : "Connect your Spotify account to unlock audio feature analysis and track-level convergence."}
            </p>
          </div>

          <div className="pl-3 pt-4 mt-4 border-t border-[#E4E4E7] dark:border-[#27272A] flex items-center justify-between">
            {profile.spotify_connected ? (
              <>
                <button
                  onClick={handleSpotifySync}
                  disabled={syncingSpotify}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono rounded-lg border border-[#E4E4E7] dark:border-[#27272A] hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", syncingSpotify && "animate-spin")} />
                  <span>{syncingSpotify ? "Syncing Plays..." : "Sync Plays Now"}</span>
                </button>
                {syncMsg && (
                  <span className="text-xs font-mono text-emerald-500">{syncMsg}</span>
                )}
              </>
            ) : (
              <Button
                size="sm"
                style={{ backgroundColor: "#7C6CF0", color: "#fff" }}
                onClick={() => (window.location.href = api.auth.loginUrl)}
              >
                Connect Spotify
              </Button>
            )}
          </div>
        </Card>

        {/* AniList Connection Preview */}
        <Card className="p-6 relative overflow-hidden flex flex-col justify-between">
          <LineRail domain="anime" />
          <div className="pl-3 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                AniList Profile Stream
              </h3>
              <span
                className={cn(
                  "px-2 py-0.5 text-[10px] font-mono rounded-full font-semibold uppercase",
                  profile.anilist_connected
                    ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                )}
              >
                {profile.anilist_connected ? "Connected" : "Disconnected"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {profile.anilist_connected
                ? "Your logged anime lists and ratings directly inform cross-module theme correlations."
                : "Connect your AniList account to synchronize your completed anime and high-affinity genres."}
            </p>
          </div>

          <div className="pl-3 pt-4 mt-4 border-t border-[#E4E4E7] dark:border-[#27272A] flex items-center justify-between">
            {profile.anilist_connected ? (
              <span className="text-xs font-mono text-muted-foreground">
                Status: Logged In & Synchronized
              </span>
            ) : (
              <Button
                size="sm"
                style={{ backgroundColor: "#4A90E2", color: "#fff" }}
                onClick={() => (window.location.href = `${import.meta.env.VITE_API_BASE || ""}/anilist/login`)}
              >
                Connect AniList
              </Button>
            )}
          </div>
        </Card>
      </div>

      {/* AniList Watched Gallery */}
      {profile.anilist_watched && profile.anilist_watched.length > 0 && (
        <Card className="p-6 relative overflow-hidden">
          <LineRail domain="anime" />
          <div className="flex items-center justify-between mb-4 pl-3">
            <div>
              <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                Watched on AniList
              </h3>
              <p className="text-xs text-muted-foreground">
                Recent series influencing your taste vectors
              </p>
            </div>
            <Tv className="w-4 h-4 text-[#FF7A59]" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pl-3">
            {profile.anilist_watched.map((item: any) => (
              <div
                key={item.mal_id}
                className="p-3.5 rounded-xl bg-black/[0.02] dark:bg-white/[0.02] border border-[#E4E4E7] dark:border-[#27272A] flex flex-col justify-between space-y-2 hover:border-[#FF7A59]/40 transition-colors"
              >
                <span className="text-sm font-sans font-medium text-foreground line-clamp-1">
                  {item.title}
                </span>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-muted-foreground uppercase text-[10px]">
                    {item.status.toLowerCase()}
                  </span>
                  {item.score > 0 ? (
                    <span className="font-semibold text-[#FF7A59]">{item.score} / 10</span>
                  ) : (
                    <span className="text-muted-foreground">Unscored</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Footer Navigation CTA to Settings */}
      {onNavigate && (
        <div className="p-4 rounded-xl border border-dashed border-[#E4E4E7] dark:border-[#27272A] flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <div>
            <p className="text-xs font-sans font-medium text-foreground">
              Looking to adjust algorithm sensitivity, change theme, or export your profile?
            </p>
            <p className="text-[11px] text-muted-foreground">
              Fine-tune serendipity, obscurity filters, and domain weights in the Settings tab.
            </p>
          </div>
          <button
            onClick={() => onNavigate("settings")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-sans font-medium rounded-lg bg-black/5 dark:bg-white/10 hover:bg-black/10 dark:hover:bg-white/15 text-foreground transition-colors cursor-pointer whitespace-nowrap"
          >
            <span>Open Settings</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
