import { useState, useEffect } from "react";
import {
  Sliders,
  Pin,
  EyeOff,
  Save,
  RotateCcw,
  Trash2,
  Plus,
  X,
  History,
} from "lucide-react";
import {
  profileApi,
  type TasteControlsData,
  type FeedbackHistoryItem,
} from "../../api/profile";
import { Card } from "../interchange/Card";

export function ControlsTab() {
  const [controls, setControls] = useState<TasteControlsData | null>(null);
  const [initialControls, setInitialControls] = useState<TasteControlsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; isError?: boolean } | null>(null);

  // New tag inputs
  const [newPinnedArtist, setNewPinnedArtist] = useState("");
  const [newPinnedGenre, setNewPinnedGenre] = useState("");
  const [newHiddenArtist, setNewHiddenArtist] = useState("");
  const [newHiddenGenre, setNewHiddenGenre] = useState("");

  // Feedback history section
  const [feedbackList, setFeedbackList] = useState<FeedbackHistoryItem[]>([]);
  const [feedbackDomain, setFeedbackDomain] = useState<string>("");
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  const [resettingFeedback, setResettingFeedback] = useState(false);

  useEffect(() => {
    loadControls();
    loadFeedbackHistory();
  }, []);

  const loadControls = async () => {
    setLoading(true);
    try {
      const data = await profileApi.getControls();
      setControls(data);
      setInitialControls(JSON.parse(JSON.stringify(data)));
    } catch (err: any) {
      setStatusMsg({ text: err.message || "Failed to load controls", isError: true });
    } finally {
      setLoading(false);
    }
  };

  const loadFeedbackHistory = async (domain = "") => {
    setLoadingFeedback(true);
    try {
      const list = await profileApi.getFeedbackHistory(domain, 25, 0);
      setFeedbackList(list);
    } catch {
      setFeedbackList([]);
    } finally {
      setLoadingFeedback(false);
    }
  };

  const isDirty =
    controls && initialControls
      ? JSON.stringify(controls) !== JSON.stringify(initialControls)
      : false;

  // Normalized weight slider adjustment
  const handleDomainWeightChange = (key: keyof TasteControlsData["domain_weights"], rawVal: number) => {
    if (!controls) return;
    const newVal = Math.max(0, Math.min(100, Math.round(rawVal)));
    const keys: (keyof TasteControlsData["domain_weights"])[] = [
      "music",
      "anime",
      "movies",
      "fashion",
    ];
    const otherKeys = keys.filter((k) => k !== key);
    const otherCurrentSum = otherKeys.reduce((sum, k) => sum + controls.domain_weights[k], 0);

    const targetRemaining = 100 - newVal;
    const newWeights = { ...controls.domain_weights, [key]: newVal };

    if (otherCurrentSum === 0) {
      // Split remaining equally
      const each = Math.floor(targetRemaining / otherKeys.length);
      otherKeys.forEach((k, idx) => {
        newWeights[k] = idx === 0 ? targetRemaining - each * (otherKeys.length - 1) : each;
      });
    } else {
      let accumulated = 0;
      otherKeys.forEach((k, idx) => {
        if (idx === otherKeys.length - 1) {
          newWeights[k] = Math.max(0, targetRemaining - accumulated);
        } else {
          const share = Math.round((controls.domain_weights[k] / otherCurrentSum) * targetRemaining);
          newWeights[k] = Math.max(0, share);
          accumulated += newWeights[k];
        }
      });
    }

    setControls({
      ...controls,
      domain_weights: newWeights,
    });
  };

  const handleSliderChange = (key: keyof TasteControlsData["sliders"], val: number) => {
    if (!controls) return;
    setControls({
      ...controls,
      sliders: {
        ...controls.sliders,
        [key]: Math.max(0, Math.min(100, val)),
      },
    });
  };

  const handleAddChip = (
    type: "pinned" | "hidden",
    category: "artists" | "genres",
    value: string
  ) => {
    if (!controls || !value.trim()) return;
    const clean = value.trim().toLowerCase();
    const currentList = controls[type][category];
    if (currentList.length >= 50 || currentList.includes(clean)) return;

    setControls({
      ...controls,
      [type]: {
        ...controls[type],
        [category]: [...currentList, clean],
      },
    });
  };

  const handleRemoveChip = (
    type: "pinned" | "hidden",
    category: "artists" | "genres",
    index: number
  ) => {
    if (!controls) return;
    const currentList = [...controls[type][category]];
    currentList.splice(index, 1);
    setControls({
      ...controls,
      [type]: {
        ...controls[type],
        [category]: currentList,
      },
    });
  };

  const handleSave = async () => {
    if (!controls) return;
    setSaving(true);
    setStatusMsg(null);
    try {
      const updated = await profileApi.updateControls(controls);
      setControls(updated);
      setInitialControls(JSON.parse(JSON.stringify(updated)));
      setStatusMsg({ text: "Taste controls updated successfully!" });
    } catch (err: any) {
      setStatusMsg({ text: err.message || "Failed to update controls", isError: true });
    } finally {
      setSaving(false);
    }
  };

  const handleResetFeedback = async (domainToReset = "") => {
    const domainLabel = domainToReset || "all domains";
    const confirmed = window.confirm(
      `Are you sure you want to reset recommendation feedback for ${domainLabel}? This will clear your likes, dislikes, and skip records.`
    );
    if (!confirmed) return;

    setResettingFeedback(true);
    try {
      await profileApi.resetFeedbackHistory(domainToReset);
      loadFeedbackHistory(feedbackDomain);
      setStatusMsg({ text: `Feedback reset for ${domainLabel}` });
    } catch (err: any) {
      setStatusMsg({ text: err.message || "Reset failed", isError: true });
    } finally {
      setResettingFeedback(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-40 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
        <div className="h-40 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
      </div>
    );
  }

  if (!controls) return null;

  return (
    <div className="space-y-8">
      {/* Header bar with save button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
            Taste Controls & Weights
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Customize how recommendation signals blend across domains and fine-tune your aesthetic sliders.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {statusMsg && (
            <span
              className={`text-xs font-medium ${
                statusMsg.isError ? "text-red-500" : "text-emerald-500"
              }`}
            >
              {statusMsg.text}
            </span>
          )}

          <button
            onClick={() => setControls(JSON.parse(JSON.stringify(initialControls)))}
            disabled={!isDirty || saving}
            className="p-2 rounded-lg border border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors disabled:opacity-40"
            title="Reset changes"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={handleSave}
            disabled={!isDirty || saving}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-sm transition-all disabled:opacity-40"
          >
            {saving ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            <span>Save Controls</span>
          </button>
        </div>
      </div>

      {/* 1. Domain Weights (Normalized to 100) */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-500" />
            <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
              Domain Blending Weights
            </h4>
          </div>
          <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">
            Total: 100%
          </span>
        </div>
        <p className="text-xs text-zinc-500 mb-6">
          Set how much each domain influences your cross-domain taste passport. Sliders auto-balance to always sum to 100%.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {(["music", "anime", "movies", "fashion"] as const).map((key) => {
            const val = controls.domain_weights[key];
            return (
              <div key={key} className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="capitalize font-semibold text-zinc-800 dark:text-zinc-200">
                    {key}
                  </span>
                  <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                    {val}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={val}
                  onChange={(e) => handleDomainWeightChange(key, Number(e.target.value))}
                  className="w-full h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                />
              </div>
            );
          })}
        </div>
      </Card>

      {/* 2. Taste Aesthetic Sliders */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="w-4 h-4 text-indigo-500" />
          <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
            Aesthetic Sliders
          </h4>
        </div>
        <p className="text-xs text-zinc-500 mb-6">
          Fine-tune the vibe, obscurity threshold, and novelty exploration rate of recommendation candidates.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-zinc-800 dark:text-zinc-200">Energy</span>
              <span className="font-mono text-indigo-500">{controls.sliders.energy}</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={controls.sliders.energy}
              onChange={(e) => handleSliderChange("energy", Number(e.target.value))}
              className="w-full h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
            <div className="flex justify-between text-[10px] text-zinc-400">
              <span>Chill / Ambient</span>
              <span>Intense / Dynamic</span>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-zinc-800 dark:text-zinc-200">Obscurity</span>
              <span className="font-mono text-purple-500">{controls.sliders.obscurity}</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={controls.sliders.obscurity}
              onChange={(e) => handleSliderChange("obscurity", Number(e.target.value))}
              className="w-full h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
            <div className="flex justify-between text-[10px] text-zinc-400">
              <span>Popular / Mainstream</span>
              <span>Underground / Niche</span>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-zinc-800 dark:text-zinc-200">Novelty</span>
              <span className="font-mono text-pink-500">{controls.sliders.novelty}</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={controls.sliders.novelty}
              onChange={(e) => handleSliderChange("novelty", Number(e.target.value))}
              className="w-full h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-pink-500"
            />
            <div className="flex justify-between text-[10px] text-zinc-400">
              <span>Familiar Favorites</span>
              <span>Serendipitous Discovery</span>
            </div>
          </div>
        </div>
      </Card>

      {/* 3. Pinned & Hidden Curation Chips */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Pinned */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Pin className="w-4 h-4 text-emerald-500" />
            <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
              Pinned Items (Always Boost)
            </h4>
          </div>
          <p className="text-xs text-zinc-500">
            Pinned artists and genres receive an intentional priority score boost across candidate pools.
          </p>

          {/* Add Pinned Genre */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
              Pinned Genres
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. shoegaze, cyberpunk"
                value={newPinnedGenre}
                onChange={(e) => setNewPinnedGenre(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleAddChip("pinned", "genres", newPinnedGenre);
                    setNewPinnedGenre("");
                  }
                }}
                className="flex-1 px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs text-zinc-900 dark:text-zinc-100"
              />
              <button
                onClick={() => {
                  handleAddChip("pinned", "genres", newPinnedGenre);
                  setNewPinnedGenre("");
                }}
                className="p-1.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 text-zinc-600 dark:text-zinc-300"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {controls.pinned.genres.map((g, idx) => (
                <span
                  key={g}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                >
                  {g}
                  <button onClick={() => handleRemoveChip("pinned", "genres", idx)}>
                    <X className="w-3 h-3 hover:text-emerald-800" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Add Pinned Artist */}
          <div className="space-y-2 pt-2 border-t border-zinc-200/60 dark:border-zinc-800">
            <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
              Pinned Artists
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. Radiohead, Daft Punk"
                value={newPinnedArtist}
                onChange={(e) => setNewPinnedArtist(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleAddChip("pinned", "artists", newPinnedArtist);
                    setNewPinnedArtist("");
                  }
                }}
                className="flex-1 px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs text-zinc-900 dark:text-zinc-100"
              />
              <button
                onClick={() => {
                  handleAddChip("pinned", "artists", newPinnedArtist);
                  setNewPinnedArtist("");
                }}
                className="p-1.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 text-zinc-600 dark:text-zinc-300"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {controls.pinned.artists.map((a, idx) => (
                <span
                  key={a}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                >
                  {a}
                  <button onClick={() => handleRemoveChip("pinned", "artists", idx)}>
                    <X className="w-3 h-3 hover:text-emerald-800" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        </Card>

        {/* Hidden */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2">
            <EyeOff className="w-4 h-4 text-red-500" />
            <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
              Hidden Items (Always Exclude)
            </h4>
          </div>
          <p className="text-xs text-zinc-500">
            Hidden artists and genres are completely dropped from your recommendation candidates.
          </p>

          {/* Add Hidden Genre */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
              Hidden Genres
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. k-pop, horror"
                value={newHiddenGenre}
                onChange={(e) => setNewHiddenGenre(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleAddChip("hidden", "genres", newHiddenGenre);
                    setNewHiddenGenre("");
                  }
                }}
                className="flex-1 px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs text-zinc-900 dark:text-zinc-100"
              />
              <button
                onClick={() => {
                  handleAddChip("hidden", "genres", newHiddenGenre);
                  setNewHiddenGenre("");
                }}
                className="p-1.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 text-zinc-600 dark:text-zinc-300"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {controls.hidden.genres.map((g, idx) => (
                <span
                  key={g}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20"
                >
                  {g}
                  <button onClick={() => handleRemoveChip("hidden", "genres", idx)}>
                    <X className="w-3 h-3 hover:text-red-800" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Add Hidden Artist */}
          <div className="space-y-2 pt-2 border-t border-zinc-200/60 dark:border-zinc-800">
            <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
              Hidden Artists
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. Artist to block"
                value={newHiddenArtist}
                onChange={(e) => setNewHiddenArtist(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleAddChip("hidden", "artists", newHiddenArtist);
                    setNewHiddenArtist("");
                  }
                }}
                className="flex-1 px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs text-zinc-900 dark:text-zinc-100"
              />
              <button
                onClick={() => {
                  handleAddChip("hidden", "artists", newHiddenArtist);
                  setNewHiddenArtist("");
                }}
                className="p-1.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 text-zinc-600 dark:text-zinc-300"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {controls.hidden.artists.map((a, idx) => (
                <span
                  key={a}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20"
                >
                  {a}
                  <button onClick={() => handleRemoveChip("hidden", "artists", idx)}>
                    <X className="w-3 h-3 hover:text-red-800" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        </Card>
      </div>

      {/* 4. Feedback History & Reset Section */}
      <Card className="p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-zinc-500" />
            <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
              Feedback History & Reset
            </h4>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={feedbackDomain}
              onChange={(e) => {
                setFeedbackDomain(e.target.value);
                loadFeedbackHistory(e.target.value);
              }}
              className="px-2.5 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs text-zinc-700 dark:text-zinc-300"
            >
              <option value="">All Domains</option>
              <option value="movie">Movies</option>
              <option value="music">Music</option>
              <option value="places">Places</option>
              <option value="dining">Dining</option>
              <option value="fashion">Fashion</option>
            </select>

            <button
              onClick={() => handleResetFeedback(feedbackDomain)}
              disabled={resettingFeedback}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-900 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Reset {feedbackDomain ? feedbackDomain : "All"}</span>
            </button>
          </div>
        </div>

        {/* Feedback table list */}
        {loadingFeedback ? (
          <div className="py-8 text-center text-xs text-zinc-400">Loading history...</div>
        ) : feedbackList.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-400">
            No feedback history recorded yet.
          </div>
        ) : (
          <div className="divide-y divide-zinc-200/60 dark:divide-zinc-800 max-h-60 overflow-y-auto">
            {feedbackList.map((f) => (
              <div key={f.id} className="py-2 flex items-center justify-between text-xs">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono capitalize bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                    {f.domain}
                  </span>
                  <span className="font-medium text-zinc-800 dark:text-zinc-200 truncate">
                    {f.title || f.item_id}
                  </span>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="font-mono text-[11px] text-zinc-500">{f.action}</span>
                  {f.created_at && (
                    <span className="text-[10px] text-zinc-400 font-mono">
                      {new Date(f.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
