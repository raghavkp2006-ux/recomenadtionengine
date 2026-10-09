import React, { useState, useEffect } from "react";
import { Users, ArrowRight } from "lucide-react";
import { profileApi, type PublicProfileData } from "../../api/profile";
import { ShareCard } from "./ShareCard";
import { Card } from "../interchange/Card";

export const ShareTab: React.FC = () => {
  const [data, setData] = useState<PublicProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [compareSlug, setCompareSlug] = useState("");
  const [compatResult, setCompatResult] = useState<any>(null);
  const [compatLoading, setCompatLoading] = useState(false);
  const [compatError, setCompatError] = useState<string | null>(null);

  const fetchVisibility = async () => {
    setLoading(true);
    try {
      const res = await profileApi.getVisibility();
      setData(res);
    } catch (err) {
      console.error("Failed to load visibility:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVisibility();
  }, []);

  const handleTogglePublic = async (isPublic: boolean) => {
    if (!data) return;
    setSaving(true);
    try {
      const updated = await profileApi.updateVisibility({
        is_public: isPublic,
        visibility: data.visibility,
      });
      setData(updated);
    } catch (err) {
      console.error("Failed to update public toggle:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleVisibility = async (key: string, val: boolean) => {
    if (!data) return;
    setSaving(true);
    try {
      const newVis = { ...data.visibility, [key]: val };
      const updated = await profileApi.updateVisibility({
        is_public: data.is_public,
        visibility: newVis,
      });
      setData(updated);
    } catch (err) {
      console.error("Failed to update visibility toggle:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleCheckCompatibility = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!compareSlug.trim()) return;
    setCompatLoading(true);
    setCompatError(null);
    setCompatResult(null);
    try {
      const clean = compareSlug.trim().replace(/^.*\/u\//, "");
      const res = await profileApi.getCompatibility(clean);
      setCompatResult(res);
    } catch (err: any) {
      setCompatError(err.message || "Failed to compare compatibility");
    } finally {
      setCompatLoading(false);
    }
  };

  if (loading || !data) {
    return (
      <Card className="p-8 animate-pulse bg-zinc-900/40 border-zinc-800">
        <div className="h-4 w-40 bg-zinc-800 rounded mb-4" />
        <div className="h-64 bg-zinc-800/60 rounded" />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <ShareCard
        data={data}
        onToggleVisibility={handleToggleVisibility}
        onTogglePublic={handleTogglePublic}
        saving={saving}
      />

      {/* Compare Compatibility Box */}
      <Card className="p-5 bg-zinc-900/60 border-zinc-800">
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-zinc-100">Compare Taste Compatibility</h3>
        </div>
        <p className="text-xs text-zinc-400 mb-4">
          Enter another user's public taste slug or URL to calculate your cosine taste resonance score.
        </p>

        <form onSubmit={handleCheckCompatibility} className="flex gap-2 max-w-md">
          <input
            type="text"
            placeholder="e.g. 9f4a1b8c2d or /u/9f4a1b8c2d"
            value={compareSlug}
            onChange={(e) => setCompareSlug(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
          />
          <button
            type="submit"
            disabled={compatLoading || !compareSlug.trim()}
            className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-50"
          >
            <span>{compatLoading ? "Comparing..." : "Compare"}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </form>

        {compatError && (
          <div className="mt-3 p-3 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            {compatError}
          </div>
        )}

        {compatResult && (
          <div className="mt-4 p-4 rounded-lg bg-zinc-950/60 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-zinc-400">Compatibility Score</span>
              <span className="text-lg font-bold font-mono text-cyan-400">
                {compatResult.score_pct}%
              </span>
            </div>
            <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
              <div
                className="bg-cyan-400 h-full rounded-full transition-all duration-700"
                style={{ width: `${compatResult.score_pct}%` }}
              />
            </div>
            <p className="text-xs text-zinc-300">{compatResult.message}</p>
            {compatResult.shared_genres && compatResult.shared_genres.length > 0 && (
              <div className="pt-2">
                <span className="text-[11px] text-zinc-400">Shared Genres: </span>
                <span className="text-xs text-zinc-200">
                  {compatResult.shared_genres.join(", ")}
                </span>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
};
