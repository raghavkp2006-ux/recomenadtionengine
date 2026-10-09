import React, { useState } from "react";
import { Download, Music, Trash2, AlertTriangle, Check, RefreshCw } from "lucide-react";
import { profileApi } from "../../api/profile";
import { Card } from "../interchange/Card";

export const DataTab: React.FC = () => {
  const [playlistName, setPlaylistName] = useState("Poly_Taste Soundscape");
  const [playlistRange, setPlaylistRange] = useState<"short" | "medium" | "long">("medium");
  const [creatingPlaylist, setCreatingPlaylist] = useState(false);
  const [playlistResult, setPlaylistResult] = useState<any>(null);
  const [playlistError, setPlaylistError] = useState<string | null>(null);

  const [wipeConfirmText, setWipeConfirmText] = useState("");
  const [wiping, setWiping] = useState(false);
  const [wipeResult, setWipeResult] = useState<string | null>(null);
  const [wipeError, setWipeError] = useState<string | null>(null);

  const handleExport = () => {
    window.location.href = profileApi.exportDataUrl;
  };

  const handleCreatePlaylist = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingPlaylist(true);
    setPlaylistError(null);
    setPlaylistResult(null);
    try {
      const res = await profileApi.createPlaylist(playlistName, playlistRange);
      setPlaylistResult(res);
    } catch (err: any) {
      setPlaylistError(err.message || "Failed to create Spotify playlist.");
    } finally {
      setCreatingPlaylist(false);
    }
  };

  const handleWipeAccount = async () => {
    if (wipeConfirmText !== "DELETE") return;
    setWiping(true);
    setWipeError(null);
    setWipeResult(null);
    try {
      const res = await profileApi.deleteUserData();
      setWipeResult(res.message);
      setWipeConfirmText("");
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err: any) {
      setWipeError(err.message || "Failed to wipe user data.");
    } finally {
      setWiping(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Export Section */}
      <Card className="p-5 bg-zinc-900/60 border-zinc-800">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Download className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-semibold text-zinc-100">Export Taste Profile</h3>
            </div>
            <p className="text-xs text-zinc-400">
              Download your complete interaction history, taste controls, and category weights as JSON.
            </p>
          </div>
          <button
            onClick={handleExport}
            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            Download JSON
          </button>
        </div>
      </Card>

      {/* Spotify Playlist Generator */}
      <Card className="p-5 bg-zinc-900/60 border-zinc-800 space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Music className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-zinc-100">Save as Spotify Playlist</h3>
          </div>
          <p className="text-xs text-zinc-400">
            Export a snapshot of your discovered soundscape directly into your Spotify library as a private playlist.
          </p>
        </div>

        <form onSubmit={handleCreatePlaylist} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input
            type="text"
            value={playlistName}
            onChange={(e) => setPlaylistName(e.target.value)}
            placeholder="Playlist Title"
            className="px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 focus:outline-none focus:border-emerald-500"
          />

          <select
            value={playlistRange}
            onChange={(e) => setPlaylistRange(e.target.value as any)}
            className="px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-300 focus:outline-none focus:border-emerald-500"
          >
            <option value="short">Last 4 Weeks (Short Term)</option>
            <option value="medium">Last 6 Months (Medium Term)</option>
            <option value="long">All Time (Long Term)</option>
          </select>

          <button
            type="submit"
            disabled={creatingPlaylist}
            className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 border border-zinc-700"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${creatingPlaylist ? "animate-spin" : ""}`} />
            {creatingPlaylist ? "Generating..." : "Generate Playlist"}
          </button>
        </form>

        {playlistError && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            {playlistError}
          </div>
        )}

        {playlistResult && (
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center justify-between">
            <span>
              {playlistResult.message} ({playlistResult.tracks_count} tracks)
            </span>
            {playlistResult.playlist_url && (
              <a
                href={playlistResult.playlist_url}
                target="_blank"
                rel="noreferrer"
                className="underline font-semibold ml-2 hover:text-emerald-300"
              >
                Open in Spotify
              </a>
            )}
          </div>
        )}
      </Card>

      {/* Danger Zone: GDPR Wipe */}
      <Card className="p-5 bg-rose-950/20 border-rose-900/40 space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-1 text-rose-400">
            <AlertTriangle className="w-4 h-4" />
            <h3 className="text-sm font-semibold">Danger Zone: Permanent Account Wipe</h3>
          </div>
          <p className="text-xs text-zinc-400">
            Permanently delete all connected credentials, interaction events, ratings, and recommendations. This action cannot be reversed.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
          <input
            type="text"
            value={wipeConfirmText}
            onChange={(e) => setWipeConfirmText(e.target.value)}
            placeholder='Type "DELETE" to confirm'
            className="px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-rose-200 placeholder-zinc-600 focus:outline-none focus:border-rose-500"
          />

          <button
            onClick={handleWipeAccount}
            disabled={wiping || wipeConfirmText !== "DELETE"}
            className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-40"
          >
            <Trash2 className="w-3.5 h-3.5" />
            {wiping ? "Wiping Data..." : "Permanently Delete Everything"}
          </button>
        </div>

        {wipeError && (
          <div className="p-3 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-300 text-xs">
            {wipeError}
          </div>
        )}

        {wipeResult && (
          <div className="p-3 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2">
            <Check className="w-4 h-4" />
            {wipeResult}
          </div>
        )}
      </Card>
    </div>
  );
};
