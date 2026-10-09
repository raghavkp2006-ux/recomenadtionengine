import { useState } from "react";
import {
  RefreshCw,
  Trash2,
  AlertTriangle,
  HelpCircle,
  Music,
  Tv,
  ShoppingBag,
  Film,
  MapPin,
  Utensils,
  ExternalLink,
} from "lucide-react";
import { Card } from "../interchange/Card";
import { profileApi, type ConnectionItem } from "../../api/profile";

interface ConnectionsGridProps {
  connections: ConnectionItem[];
  loading: boolean;
  error?: string | null;
  onRefresh: () => void;
}

const DOMAIN_INFO: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string; desc: string; connectUrl?: string }
> = {
  spotify: {
    label: "Spotify",
    icon: Music,
    color: "#1DB954",
    desc: "Syncs recently played tracks, top artists, and streaming habits.",
    connectUrl: `${import.meta.env.VITE_API_BASE || "http://localhost:8000"}/spotify/login`,
  },
  anilist: {
    label: "AniList",
    icon: Tv,
    color: "#4A90E2",
    desc: "Syncs completed and watching anime lists and scores.",
    connectUrl: `${import.meta.env.VITE_API_BASE || "http://localhost:8000"}/anilist/login`,
  },
  myntra: {
    label: "Myntra Fashion",
    icon: ShoppingBag,
    color: "#D946EF",
    desc: "Ingests product views, styles, and wishlists via browser extension.",
  },
  movies: {
    label: "Movies",
    icon: Film,
    color: "#6366F1",
    desc: "Ratings and feedback across TMDB and IMDb cinema catalog.",
  },
  places: {
    label: "Tourist Spots",
    icon: MapPin,
    color: "#E3A857",
    desc: "Exploration ratings and bookmarks for local spots and adventures.",
  },
  dining: {
    label: "Dining & Cafes",
    icon: Utensils,
    color: "#EC4899",
    desc: "Culinary likes, cafe visits, and food spot preferences.",
  },
};

export function ConnectionsGrid({
  connections,
  loading,
  error,
  onRefresh,
}: ConnectionsGridProps) {
  const [syncingDomain, setSyncingDomain] = useState<string | null>(null);
  const [disconnectingDomain, setDisconnectingDomain] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<{ domain: string; msg: string; isErr?: boolean } | null>(null);

  const handleResync = async (domain: string) => {
    setSyncingDomain(domain);
    setFeedbackMsg(null);
    try {
      const res = await profileApi.resyncConnection(domain);
      setFeedbackMsg({
        domain,
        msg: res.status === "ok" ? `Synced ${res.items_count} items` : `Status: ${res.status}`,
        isErr: res.status === "error" || res.status === "needs_reconnect",
      });
      onRefresh();
    } catch (err: any) {
      setFeedbackMsg({
        domain,
        msg: err.message || "Resync failed",
        isErr: true,
      });
    } finally {
      setSyncingDomain(null);
    }
  };

  const handleDisconnect = async (domain: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to disconnect ${DOMAIN_INFO[domain]?.label || domain}? This will remove stored signals and tokens for this domain. Your account will NOT be deleted.`
    );
    if (!confirmed) return;

    setDisconnectingDomain(domain);
    setFeedbackMsg(null);
    try {
      await profileApi.disconnectConnection(domain);
      setFeedbackMsg({
        domain,
        msg: "Disconnected and cleared signals",
      });
      onRefresh();
    } catch (err: any) {
      setFeedbackMsg({
        domain,
        msg: err.message || "Failed to disconnect",
        isErr: true,
      });
    } finally {
      setDisconnectingDomain(null);
    }
  };

  const formatRelativeTime = (isoString?: string | null) => {
    if (!isoString) return "Never synced";
    try {
      const date = new Date(isoString.endsWith("Z") ? isoString : `${isoString}Z`);
      return date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  const getStatusBadge = (status: ConnectionItem["status"]) => {
    switch (status) {
      case "ok":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Connected
          </span>
        );
      case "needs_reconnect":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Needs Reconnect
          </span>
        );
      case "error":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            Error
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-500/10 text-zinc-500 dark:text-zinc-400 border border-zinc-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 dark:bg-zinc-600" />
            Not Active
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => (
          <Card key={i} className="p-5 animate-pulse">
            <div className="h-6 bg-zinc-200 dark:bg-zinc-800 rounded w-1/2 mb-3" />
            <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-3/4 mb-6" />
            <div className="h-8 bg-zinc-200 dark:bg-zinc-800 rounded w-full" />
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6 border-red-200 dark:border-red-900/50 bg-red-50/20 dark:bg-red-950/20">
        <div className="flex items-center gap-3 text-red-600 dark:text-red-400 text-sm">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <p>{error}</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Domain Connections
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Manage live signals powering your unified Poly_Taste recommendations.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {connections.map((item) => {
          const info = DOMAIN_INFO[item.domain] || {
            label: item.domain,
            icon: HelpCircle,
            color: "#71717A",
            desc: "Custom domain connection",
          };
          const Icon = info.icon;
          const isSyncing = syncingDomain === item.domain;
          const isDisconnecting = disconnectingDomain === item.domain;
          const msg = feedbackMsg?.domain === item.domain ? feedbackMsg : null;

          return (
            <Card key={item.domain} className="p-5 flex flex-col justify-between relative group">
              <div>
                {/* Header row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 shadow-sm"
                      style={{ backgroundColor: `${info.color}15`, color: info.color }}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                        {info.label}
                      </h4>
                      <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                        {item.items_count} items logged
                      </p>
                    </div>
                  </div>
                  {getStatusBadge(item.status)}
                </div>

                {/* Description */}
                <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-3 line-clamp-2">
                  {info.desc}
                </p>

                {/* Specific Myntra details */}
                {item.domain === "myntra" && (
                  <div className="mt-3 p-2 rounded-md bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200/60 dark:border-zinc-800 text-[11px] text-zinc-500 dark:text-zinc-400 space-y-1">
                    <div className="flex justify-between">
                      <span>Products Captured:</span>
                      <span className="font-mono font-medium text-zinc-700 dark:text-zinc-300">
                        {item.products_captured ?? 0}
                      </span>
                    </div>
                    {item.last_event_at && (
                      <div className="flex justify-between">
                        <span>Last Event:</span>
                        <span>{formatRelativeTime(item.last_event_at)}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Error message callout if present */}
                {item.error_message && (
                  <div className="mt-3 p-2 rounded bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/40 text-[11px] text-red-600 dark:text-red-400 flex items-start gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    <span className="truncate">{item.error_message}</span>
                  </div>
                )}

                {/* Action feedback message */}
                {msg && (
                  <p
                    className={`mt-2 text-xs font-medium ${
                      msg.isErr ? "text-red-500" : "text-emerald-500"
                    }`}
                  >
                    {msg.msg}
                  </p>
                )}
              </div>

              {/* Footer info & action buttons */}
              <div className="mt-5 pt-3 border-t border-zinc-200/70 dark:border-zinc-800 flex items-center justify-between text-xs">
                <span className="text-[11px] text-zinc-400 dark:text-zinc-500 truncate max-w-[130px]">
                  {formatRelativeTime(item.last_synced_at)}
                </span>

                <div className="flex items-center gap-2">
                  {/* Connect link for OAuth domains if disconnected or needs reconnect */}
                  {info.connectUrl && (item.status === "never" || item.status === "needs_reconnect") && (
                    <a
                      href={info.connectUrl}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-white dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors"
                    >
                      Connect
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}

                  {/* Resync button */}
                  {item.connected && (
                    <button
                      onClick={() => handleResync(item.domain)}
                      disabled={isSyncing || isDisconnecting}
                      className="p-1.5 rounded text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50"
                      title="Trigger sync"
                    >
                      <RefreshCw
                        className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin text-emerald-500" : ""}`}
                      />
                    </button>
                  )}

                  {/* Disconnect button */}
                  {item.connected && (
                    <button
                      onClick={() => handleDisconnect(item.domain)}
                      disabled={isSyncing || isDisconnecting}
                      className="p-1.5 rounded text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors disabled:opacity-50"
                      title="Disconnect domain"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
