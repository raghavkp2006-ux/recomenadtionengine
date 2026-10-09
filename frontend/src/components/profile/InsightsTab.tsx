import { useState, useEffect } from "react";
import {
  Sparkles,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  Disc3,
  Clock,
  Compass,
  Radio,
} from "lucide-react";
import { profileApi, type ProfileInsightsData } from "../../api/profile";
import { Card } from "../interchange/Card";
import { GenreRadar } from "./charts/GenreRadar";
import { BarList } from "./charts/BarList";
import { DecadeBars } from "./charts/DecadeBars";
import { EvolutionDelta } from "./charts/EvolutionDelta";
import { ScoreGauge } from "./charts/ScoreGauge";

export function InsightsTab() {
  const [range, setRange] = useState<"short" | "medium" | "long">("medium");
  const [insights, setInsights] = useState<ProfileInsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInsights = async (forceRefresh = false) => {
    if (forceRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const data = await profileApi.getInsights(range, forceRefresh);
      setInsights(data);
    } catch (err: any) {
      setError(err.message || "Failed to load taste insights");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchInsights(false);
  }, [range]);

  const ranges: { id: "short" | "medium" | "long"; label: string; desc: string }[] = [
    { id: "short", label: "Short Term", desc: "Past 4 weeks" },
    { id: "medium", label: "Medium Term", desc: "Past 6 months" },
    { id: "long", label: "Long Term", desc: "All-time" },
  ];

  if (loading && !insights) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 bg-zinc-200 dark:bg-zinc-800 rounded-lg w-1/3" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
          ))}
        </div>
        <div className="h-80 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
      </div>
    );
  }

  const connectUrl = `${import.meta.env.VITE_API_BASE || "http://localhost:8000"}/spotify/login`;

  return (
    <div className="space-y-6">
      {/* Top Controls: Range Toggle + Refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
            Taste Profile Insights
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Analytical breakdown of your musical footprint and sonic diversity.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Range segmented buttons */}
          <div className="p-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 flex items-center">
            {ranges.map((r) => (
              <button
                key={r.id}
                onClick={() => setRange(r.id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  range === r.id
                    ? "bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-sm"
                    : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                }`}
                title={r.desc}
              >
                {r.label}
              </button>
            ))}
          </div>

          <button
            onClick={() => fetchInsights(true)}
            disabled={refreshing}
            className="p-2 rounded-lg border border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            title="Force refresh"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-indigo-500" : ""}`} />
          </button>
        </div>
      </div>

      {/* Needs Reconnect Prompt if Spotify not connected */}
      {insights?.status === "needs_reconnect" && (
        <Card className="p-6 border-amber-300 dark:border-amber-800/60 bg-amber-50/40 dark:bg-amber-950/20">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-6 h-6 text-amber-600 dark:text-amber-400 flex-shrink-0" />
              <div>
                <h4 className="text-sm font-bold text-amber-900 dark:text-amber-100">
                  Spotify Account Not Synced
                </h4>
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  Connect Spotify to generate top genres, Shannon entropy diversity, era histograms, and discover rare artists.
                </p>
              </div>
            </div>
            <a
              href={connectUrl}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#1DB954] hover:bg-[#1ed760] text-white text-xs font-semibold shadow transition-colors"
            >
              <span>Connect Spotify</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </Card>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 text-xs text-red-600">
          {error}
        </div>
      )}

      {/* Hero row: Personality badge */}
      {insights?.personality && (
        <Card className="p-5 bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-pink-500/10 border-indigo-500/20">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 shadow-md">
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase tracking-wider text-indigo-600 dark:text-indigo-400 font-bold">
                  Listener Archetype
                </span>
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-indigo-600 text-white">
                  {insights.personality.label}
                </span>
              </div>
              <p className="text-sm text-zinc-700 dark:text-zinc-200 mt-1 font-medium">
                {insights.personality.reason}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Metric Gauges Row */}
      {insights && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <ScoreGauge
            label="Genre Diversity"
            value={insights.diversity}
            isPercentage={true}
            color="#8B5CF6"
            description="Shannon entropy normalized across genre breadths"
          />
          <ScoreGauge
            label="Mainstream Appeal"
            value={insights.mainstream_score}
            isPercentage={false}
            color="#3B82F6"
            description="Average artist and track popularity index"
          />
          <ScoreGauge
            label="Discovery Freshness"
            value={insights.discovery_rate}
            isPercentage={true}
            color="#10B981"
            description="Share of recent artists absent from long-term history"
          />
        </div>
      )}

      {/* Genre Radar & Bar List Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-indigo-500" />
              <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                Genre Radar
              </h4>
            </div>
            <span className="text-[11px] text-zinc-400">Top 6 genres</span>
          </div>
          <GenreRadar genres={insights?.top_genres || []} size={320} />
        </Card>

        <Card className="p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-indigo-500" />
                <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                  Genre Distribution
                </h4>
              </div>
              <span className="text-[11px] text-zinc-400">Rank-weighted</span>
            </div>
            <BarList items={insights?.top_genres || []} color="#7C6CF0" />
          </div>

          <div className="mt-6 pt-4 border-t border-zinc-200/70 dark:border-zinc-800 flex justify-between text-xs text-zinc-500">
            <span>Obscurity Score:</span>
            <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200">
              {insights?.obscurity_score ?? 50}/100
            </span>
          </div>
        </Card>
      </div>

      {/* Decades Histogram & Evolution Delta */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-500" />
              <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                Era Spectrum
              </h4>
            </div>
            <span className="text-[11px] text-zinc-400">Release decades</span>
          </div>
          <DecadeBars decades={insights?.decades || []} />
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-500" />
              <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                Taste Evolution
              </h4>
            </div>
            <span className="text-[11px] text-zinc-400">Short vs Long term</span>
          </div>
          <EvolutionDelta
            rising={insights?.evolution.rising || []}
            fading={insights?.evolution.fading || []}
          />
        </Card>
      </div>

      {/* Rarest Artist and Track Callouts */}
      {insights?.rarest && (insights.rarest.artist || insights.rarest.track) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {insights.rarest.artist && (
            <Card className="p-4 flex items-center gap-4">
              {insights.rarest.artist.image ? (
                <img
                  src={insights.rarest.artist.image}
                  alt={insights.rarest.artist.name}
                  className="w-14 h-14 rounded-lg object-cover flex-shrink-0"
                />
              ) : (
                <div className="w-14 h-14 rounded-lg bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center text-zinc-400">
                  <Disc3 className="w-6 h-6" />
                </div>
              )}
              <div className="min-w-0">
                <span className="text-[10px] font-mono uppercase tracking-wider text-purple-600 dark:text-purple-400 font-bold">
                  Deep Cut Artist
                </span>
                <h5 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate">
                  {insights.rarest.artist.name}
                </h5>
                <p className="text-xs text-zinc-500">
                  Popularity: {insights.rarest.artist.popularity}/100
                </p>
              </div>
            </Card>
          )}

          {insights.rarest.track && (
            <Card className="p-4 flex items-center gap-4">
              {insights.rarest.track.image ? (
                <img
                  src={insights.rarest.track.image}
                  alt={insights.rarest.track.name}
                  className="w-14 h-14 rounded-lg object-cover flex-shrink-0"
                />
              ) : (
                <div className="w-14 h-14 rounded-lg bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center text-zinc-400">
                  <Disc3 className="w-6 h-6" />
                </div>
              )}
              <div className="min-w-0">
                <span className="text-[10px] font-mono uppercase tracking-wider text-pink-600 dark:text-pink-400 font-bold">
                  Deep Cut Track
                </span>
                <h5 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate">
                  {insights.rarest.track.name}
                </h5>
                <p className="text-xs text-zinc-500 truncate">
                  {insights.rarest.track.artist} · Popularity: {insights.rarest.track.popularity}/100
                </p>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Recently Played List */}
      {insights?.recently_played && insights.recently_played.length > 0 && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
              Recently Played
            </h4>
            <span className="text-xs text-zinc-400">Last 20 tracks</span>
          </div>

          <div className="divide-y divide-zinc-200/60 dark:divide-zinc-800">
            {insights.recently_played.map((t, idx) => (
              <div key={idx} className="py-2.5 flex items-center justify-between text-xs">
                <div className="min-w-0 flex items-center gap-3">
                  <span className="w-5 font-mono text-[11px] text-zinc-400 text-right">
                    {idx + 1}
                  </span>
                  <div className="truncate">
                    <p className="font-medium text-zinc-800 dark:text-zinc-200 truncate">
                      {t.track}
                    </p>
                    <p className="text-[11px] text-zinc-500 truncate">{t.artist}</p>
                  </div>
                </div>
                {t.played_at && (
                  <span className="text-[11px] text-zinc-400 font-mono flex-shrink-0">
                    {new Date(t.played_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
