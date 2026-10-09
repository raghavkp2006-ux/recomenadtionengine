import { useState, useEffect } from "react";
import { ArrowLeft, ShieldAlert, Sparkles, Layers } from "lucide-react";
import { profileApi } from "../api/profile";
import { Card } from "../components/interchange/Card";

export function PublicProfilePage({ slug: propSlug }: { slug?: string }) {
  // Extract slug from prop or from window.location.pathname (/u/:slug)
  const [slug] = useState<string>(() => {
    if (propSlug) return propSlug;
    const match = window.location.pathname.match(/\/u\/([^\/\?#]+)/);
    return match ? match[1] : "";
  });
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    profileApi
      .getPublicProfile(slug)
      .then((data) => {
        setProfile(data);
      })
      .catch((err) => {
        setError(err.message || "Profile is private or does not exist.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [slug]);

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-6 space-y-4">
        <div className="h-6 w-32 bg-zinc-800 rounded animate-pulse" />
        <Card className="p-8 animate-pulse bg-zinc-900/40 border-zinc-800 space-y-4">
          <div className="h-12 w-12 bg-zinc-800 rounded-full" />
          <div className="h-4 w-48 bg-zinc-800 rounded" />
          <div className="h-20 bg-zinc-800/60 rounded" />
        </Card>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="max-w-md mx-auto p-6 text-center space-y-4 pt-16">
        <div className="p-4 rounded-full bg-zinc-800/80 w-fit mx-auto text-zinc-400">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h2 className="text-base font-bold text-zinc-100">Profile Not Found</h2>
        <p className="text-xs text-zinc-400">
          This taste passport is private, was removed, or does not exist.
        </p>
        <a
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-zinc-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </a>
      </div>
    );
  }

  const { visibility } = profile;

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-6 space-y-6">
      {/* Top Navigation */}
      <a
        href="/"
        className="inline-flex items-center gap-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Poly_Taste Home
      </a>

      {/* Main Passport Card */}
      <Card className="p-6 md:p-8 bg-zinc-900/80 border-zinc-800 space-y-6">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-pink-500 to-emerald-400 flex items-center justify-center font-bold text-black text-sm">
              PT
            </div>
            <div>
              <h1 className="text-lg font-bold text-zinc-100">{profile.display_name}</h1>
              <p className="text-xs text-zinc-400 font-mono">Taste Passport #{profile.slug}</p>
            </div>
          </div>
          <div className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Public
          </div>
        </div>

        {/* Archetype / Personality Section */}
        {visibility.personality && profile.personality && (
          <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-1">
            <div className="flex items-center gap-2 text-pink-400 text-xs font-semibold">
              <Sparkles className="w-4 h-4" />
              <span>Archetype</span>
            </div>
            <h3 className="text-sm font-bold text-zinc-100">{profile.personality.label}</h3>
            <p className="text-xs text-zinc-400">{profile.personality.reason}</p>
          </div>
        )}

        {/* Genres Section */}
        {visibility.genres && profile.top_genres && (
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Top Soundscapes & Genres
            </h3>
            <div className="flex flex-wrap gap-2">
              {profile.top_genres.map((g: any, i: number) => (
                <span
                  key={i}
                  className="px-3 py-1 rounded-lg text-xs font-medium bg-zinc-800/80 text-zinc-200 border border-zinc-700/60"
                >
                  {g.genre}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Stats Section */}
        {visibility.stats && (
          <div className="grid grid-cols-3 gap-3 pt-2">
            <div className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800 text-center">
              <div className="text-[10px] text-zinc-500 uppercase">Diversity</div>
              <div className="text-base font-bold text-emerald-400 font-mono">
                {Math.round((profile.diversity || 0) * 100)}%
              </div>
            </div>
            <div className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800 text-center">
              <div className="text-[10px] text-zinc-500 uppercase">Mainstream</div>
              <div className="text-base font-bold text-amber-400 font-mono">
                {Math.round(profile.mainstream_score || 0)}%
              </div>
            </div>
            <div className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800 text-center">
              <div className="text-[10px] text-zinc-500 uppercase">Obscurity</div>
              <div className="text-base font-bold text-cyan-400 font-mono">
                {Math.round(profile.obscurity_score || 0)}%
              </div>
            </div>
          </div>
        )}

        {/* Connections Section */}
        {visibility.connections && profile.active_connections && (
          <div className="space-y-2 pt-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5" />
              Connected Mediums
            </h3>
            <div className="flex gap-2">
              {profile.active_connections.map((c: string, idx: number) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded text-xs font-medium bg-zinc-800 text-zinc-300"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
