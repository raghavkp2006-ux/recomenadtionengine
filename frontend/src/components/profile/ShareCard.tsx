import React, { useRef, useState } from "react";
import { Download, Share2, Sparkles, Music, Copy, Check, Eye, EyeOff } from "lucide-react";
import { toPng } from "html-to-image";
import { Card } from "../interchange/Card";
import type { PublicProfileData } from "../../api/profile";

interface ShareCardProps {
  data: PublicProfileData;
  onToggleVisibility: (key: string, val: boolean) => void;
  onTogglePublic: (isPublic: boolean) => void;
  saving?: boolean;
}

export const ShareCard: React.FC<ShareCardProps> = ({
  data,
  onToggleVisibility,
  onTogglePublic,
  saving,
}) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState(false);

  const publicUrl = data.slug
    ? `${window.location.origin}/u/${data.slug}`
    : "";

  const handleCopy = () => {
    if (!publicUrl) return;
    navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = async () => {
    if (!cardRef.current) return;
    setDownloading(true);
    try {
      const dataUrl = await toPng(cardRef.current, {
        cacheBust: true,
        pixelRatio: 2,
      });
      const link = document.createElement("a");
      link.download = `polytaste-${data.slug || "card"}.png`;
      link.href = dataUrl;
      link.click();
    } catch (err) {
      console.error("Failed to export image:", err);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Visibility Toggles Card */}
      <Card className="p-5 bg-zinc-900/60 border-zinc-800">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-zinc-800">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <Share2 className="w-4 h-4 text-pink-400" />
              Public Passport Visibility
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Control whether your taste passport is discoverable and choose which components to leak.
            </p>
          </div>

          <button
            onClick={() => onTogglePublic(!data.is_public)}
            disabled={saving}
            className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
              data.is_public
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20"
                : "bg-zinc-800 text-zinc-400 border border-zinc-700 hover:text-zinc-200"
            }`}
          >
            {data.is_public ? (
              <>
                <Eye className="w-3.5 h-3.5" />
                Public (Live)
              </>
            ) : (
              <>
                <EyeOff className="w-3.5 h-3.5" />
                Private (Off)
              </>
            )}
          </button>
        </div>

        {data.is_public && (
          <div className="mt-4 space-y-4">
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-zinc-950/80 border border-zinc-800">
              <span className="text-xs text-zinc-400 truncate flex-1 font-mono">
                {publicUrl}
              </span>
              <button
                onClick={handleCopy}
                className="px-3 py-1 rounded bg-zinc-800 text-xs font-medium text-zinc-200 hover:bg-zinc-700 flex items-center gap-1.5 transition-colors"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                {copied ? "Copied" : "Copy Link"}
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 pt-2">
              {(
                [
                  { key: "genres", label: "Top Genres" },
                  { key: "top_artists", label: "Rarest Taste" },
                  { key: "stats", label: "Diversity & Stats" },
                  { key: "connections", label: "Active Services" },
                  { key: "personality", label: "Archetype" },
                ] as const
              ).map((item) => {
                const isEnabled = data.visibility[item.key as keyof typeof data.visibility];
                return (
                  <button
                    key={item.key}
                    onClick={() => onToggleVisibility(item.key, !isEnabled)}
                    disabled={saving}
                    className={`p-2.5 rounded-lg border text-left transition-all text-xs ${
                      isEnabled
                        ? "bg-pink-500/10 border-pink-500/30 text-pink-300"
                        : "bg-zinc-950/40 border-zinc-800 text-zinc-500 hover:text-zinc-400"
                    }`}
                  >
                    <div className="font-medium">{item.label}</div>
                    <div className="text-[10px] opacity-75 mt-0.5">
                      {isEnabled ? "Shown" : "Hidden"}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </Card>

      {/* Share Card Canvas Preview (1080x1350 Instagram / Passport format aspect ratio 4:5) */}
      <div className="flex flex-col items-center gap-4">
        <div className="flex items-center justify-between w-full max-w-[420px]">
          <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            Taste Passport Card (Shareable Image)
          </span>
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="px-3 py-1.5 rounded-lg bg-pink-600 hover:bg-pink-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            {downloading ? "Exporting..." : "Download Card"}
          </button>
        </div>

        <div
          ref={cardRef}
          className="w-full max-w-[420px] aspect-[4/5] p-6 rounded-2xl bg-gradient-to-br from-zinc-900 via-zinc-950 to-black border border-zinc-800 shadow-2xl flex flex-col justify-between text-zinc-100 relative overflow-hidden"
        >
          {/* Subtle background glow aesthetic */}
          <div className="absolute top-0 right-0 w-48 h-48 bg-pink-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

          {/* Card Header */}
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-pink-500 to-emerald-400 flex items-center justify-center font-bold text-xs text-black">
                PT
              </div>
              <div>
                <h4 className="text-sm font-bold tracking-tight">Poly_Taste</h4>
                <p className="text-[10px] text-zinc-400">Taste Passport</p>
              </div>
            </div>
            <div className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
              #{data.slug || "taste"}
            </div>
          </div>

          {/* Central Persona Badge */}
          <div className="relative z-10 my-auto text-center space-y-3">
            <div className="inline-flex items-center justify-center p-3 rounded-full bg-zinc-800/80 border border-zinc-700">
              <Music className="w-6 h-6 text-pink-400" />
            </div>
            <h2 className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-pink-400 via-emerald-300 to-cyan-400 bg-clip-text text-transparent">
              {data.visibility.personality ? "Curated Sonic Wanderer" : "Taste Explorer"}
            </h2>
            <p className="text-xs text-zinc-400 max-w-[280px] mx-auto line-clamp-2">
              Cross-domain aesthetic profile spanning music, cinema, anime, and lifestyle choices.
            </p>
          </div>

          {/* Card Footer Toggles / Watermark */}
          <div className="relative z-10 pt-4 border-t border-zinc-800/60 flex items-center justify-between text-[10px] text-zinc-500">
            <span>polytaste.app/u/{data.slug || "passport"}</span>
            <span className="font-mono">VERIFIED TASTE</span>
          </div>
        </div>
      </div>
    </div>
  );
};
