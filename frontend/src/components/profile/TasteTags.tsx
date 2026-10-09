import React from "react";
import { Sparkles } from "lucide-react";
import { Card } from "../interchange/Card";

interface TasteTagsProps {
  tags: string[];
  loading?: boolean;
}

export const TasteTags: React.FC<TasteTagsProps> = ({ tags, loading }) => {
  if (loading) {
    return (
      <Card className="p-5 animate-pulse bg-zinc-900/40 border-zinc-800">
        <div className="h-4 w-32 bg-zinc-800 rounded mb-4" />
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-7 w-24 bg-zinc-800/60 rounded-full" />
          ))}
        </div>
      </Card>
    );
  }

  if (!tags || tags.length === 0) return null;

  return (
    <Card className="p-5 bg-zinc-900/60 border-zinc-800">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-emerald-400" />
        <h3 className="text-sm font-semibold text-zinc-100">Cross-Domain Persona Tags</h3>
      </div>
      <p className="text-xs text-zinc-400 mb-4">
        Unified persona markers synthesized from your listening, viewing, and lifestyle tastes.
      </p>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag, idx) => (
          <span
            key={idx}
            className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
          >
            #{tag}
          </span>
        ))}
      </div>
    </Card>
  );
};
