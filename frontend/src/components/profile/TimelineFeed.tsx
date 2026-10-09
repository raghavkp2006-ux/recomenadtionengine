import React from "react";
import { Clock, Music, Film, Tv, MapPin, Utensils, ShoppingBag } from "lucide-react";
import { Card } from "../interchange/Card";
import type { TimelineItem } from "../../api/profile";

interface TimelineFeedProps {
  timeline: TimelineItem[];
  loading?: boolean;
}

export const TimelineFeed: React.FC<TimelineFeedProps> = ({ timeline, loading }) => {
  if (loading) {
    return (
      <Card className="p-5 animate-pulse bg-zinc-900/40 border-zinc-800">
        <div className="h-4 w-32 bg-zinc-800 rounded mb-4" />
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-zinc-800/60 rounded" />
          ))}
        </div>
      </Card>
    );
  }

  const getDomainIcon = (domain: string) => {
    switch (domain) {
      case "spotify":
        return <Music className="w-4 h-4 text-emerald-400" />;
      case "anilist":
        return <Tv className="w-4 h-4 text-purple-400" />;
      case "movies":
      case "movie":
        return <Film className="w-4 h-4 text-amber-400" />;
      case "places":
      case "spots":
        return <MapPin className="w-4 h-4 text-rose-400" />;
      case "dining":
      case "cafes":
        return <Utensils className="w-4 h-4 text-orange-400" />;
      case "myntra":
      case "fashion":
        return <ShoppingBag className="w-4 h-4 text-pink-400" />;
      default:
        return <Clock className="w-4 h-4 text-zinc-400" />;
    }
  };

  const formatDomainName = (domain: string) => {
    switch (domain) {
      case "spotify":
        return "Spotify";
      case "anilist":
        return "AniList";
      case "movies":
      case "movie":
        return "Movies";
      case "places":
      case "spots":
        return "Places";
      case "dining":
        return "Dining";
      case "myntra":
        return "Fashion";
      default:
        return domain;
    }
  };

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <Card className="p-5 bg-zinc-900/60 border-zinc-800">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-zinc-300" />
        <h3 className="text-sm font-semibold text-zinc-100">Activity Timeline</h3>
      </div>
      <p className="text-xs text-zinc-400 mb-4">
        Unified interaction history flowing across music, anime, cinema, dining, spots, and apparel.
      </p>

      {timeline.length === 0 ? (
        <div className="py-8 text-center text-xs text-zinc-500">
          No interactions logged yet. Connect services or start exploring recommendations to build your timeline!
        </div>
      ) : (
        <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-[2px] before:bg-zinc-800">
          {timeline.map((item, idx) => (
            <div key={idx} className="relative group">
              {/* Timeline marker node */}
              <div className="absolute -left-[27px] top-1 p-1 rounded-full bg-zinc-900 border border-zinc-700">
                {getDomainIcon(item.domain)}
              </div>

              <div className="p-3 rounded-lg bg-zinc-950/40 border border-zinc-800/60 hover:border-zinc-700/80 transition-colors">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                      {formatDomainName(item.domain)}
                    </span>
                    <span className="text-xs font-medium text-zinc-200 line-clamp-1">{item.title}</span>
                  </div>
                  <span className="text-[11px] font-mono text-zinc-500 shrink-0">
                    {formatDate(item.at)}
                  </span>
                </div>
                {item.subtitle && (
                  <p className="text-xs text-zinc-400 pl-1">{item.subtitle}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
