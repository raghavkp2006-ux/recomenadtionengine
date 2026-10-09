import { User, Film, MapPin, Tv, ShoppingBag, Music2, Calendar } from "lucide-react";
import type { ProfileOverview } from "../../api/profile";
import { Card } from "../interchange/Card";

interface ProfileHeaderProps {
  overview: ProfileOverview | null;
  loading: boolean;
  error?: string | null;
}

export function ProfileHeader({ overview, loading, error }: ProfileHeaderProps) {
  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row items-center sm:items-start gap-5 animate-pulse">
          <div className="w-20 h-20 rounded-full bg-zinc-200 dark:bg-zinc-800" />
          <div className="flex-1 space-y-3 w-full text-center sm:text-left">
            <div className="h-6 bg-zinc-200 dark:bg-zinc-800 rounded w-1/3 mx-auto sm:mx-0" />
            <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-1/4 mx-auto sm:mx-0" />
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-16 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
              ))}
            </div>
          </div>
        </div>
      </Card>
    );
  }

  if (error || !overview) {
    return (
      <Card className="p-6 border-red-200 dark:border-red-900/50 bg-red-50/20 dark:bg-red-950/20">
        <p className="text-sm text-red-600 dark:text-red-400">
          {error || "Failed to load profile summary."}
        </p>
      </Card>
    );
  }

  const memberSinceFormatted = overview.member_since
    ? new Date(overview.member_since).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
      })
    : "Recently";

  const statBlocks = [
    {
      label: "Movies Rated",
      value: overview.counts.movies_rated,
      icon: Film,
      color: "#6366F1",
    },
    {
      label: "Places Rated",
      value: overview.counts.places_rated,
      icon: MapPin,
      color: "#E3A857",
    },
    {
      label: "Anime Logged",
      value: overview.counts.anime_logged,
      icon: Tv,
      color: "#FF7A59",
    },
    {
      label: "Products Captured",
      value: overview.counts.products_viewed,
      icon: ShoppingBag,
      color: "#D946EF",
    },
    {
      label: "Tracks Liked",
      value: overview.counts.tracks_liked,
      icon: Music2,
      color: "#10B981",
    },
  ];

  return (
    <Card className="p-6">
      <div className="flex flex-col md:flex-row items-center md:items-start gap-6">
        {/* Avatar */}
        <div className="relative flex-shrink-0">
          {overview.avatar_url ? (
            <img
              src={overview.avatar_url}
              alt={overview.name || "User Avatar"}
              className="w-20 h-20 rounded-full object-cover border-2 border-emerald-500/40 shadow-sm"
            />
          ) : (
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-sm">
              <User className="w-9 h-9" />
            </div>
          )}
          {overview.spotify && (
            <span
              title={`Spotify linked as ${overview.spotify.display_name}`}
              className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-[#1DB954] text-white flex items-center justify-center text-xs shadow-md border-2 border-white dark:border-zinc-900 font-bold"
            >
              ♪
            </span>
          )}
        </div>

        {/* Identity & Metadata */}
        <div className="flex-1 min-w-0 text-center md:text-left">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
            <div>
              <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 truncate">
                {overview.name || "Explorer"}
              </h2>
              {overview.email && (
                <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate">
                  {overview.email}
                </p>
              )}
            </div>
            <div className="flex items-center justify-center md:justify-end gap-2 text-xs text-zinc-500 dark:text-zinc-400">
              <Calendar className="w-3.5 h-3.5" />
              <span>Member since {memberSinceFormatted}</span>
            </div>
          </div>

          {/* Activity counters */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-5">
            {statBlocks.map((s) => {
              const Icon = s.icon;
              return (
                <div
                  key={s.label}
                  className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200/70 dark:border-zinc-800 flex items-center gap-3 transition-colors"
                >
                  <div
                    className="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: `${s.color}15`, color: s.color }}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-lg font-bold font-mono text-zinc-900 dark:text-zinc-100 leading-none">
                      {s.value}
                    </p>
                    <p className="text-[11px] text-zinc-500 dark:text-zinc-400 truncate mt-1">
                      {s.label}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Card>
  );
}
