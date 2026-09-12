import { getHighResImageUrl } from "@/lib/utils"
import { ChromaGrid, type ChromaItem } from "../ui/ChromaGrid"

export function AnimeGrid({
  animes,
  onSelect,
}: {
  animes: any[]
  onSelect: (anime: any) => void
}) {
  if (!animes || animes.length === 0) {
    return (
      <div
        className="text-center py-10 rounded-xl bg-white dark:bg-[#18181B] border border-[#E4E4E7] dark:border-[#27272A] text-[#71717A] dark:text-[#A1A1AA] transition-colors duration-150 ease-out"
      >
        No anime found.
      </div>
    )
  }

  const chromaItems: ChromaItem[] = animes.map((anime) => {
    const imgSrc = getHighResImageUrl(
      anime.images?.jpg?.image_url ||
      anime.coverImage?.large ||
      anime.cover_image ||
      anime.imageUrl
    )

    let genres: string[] = []
    if (Array.isArray(anime.genres)) {
      genres = anime.genres
    } else if (typeof anime.genres === "string") {
      genres = [anime.genres]
    } else if (Array.isArray(anime.genres_raw)) {
      genres = anime.genres_raw
    } else if (typeof anime.genres_raw === "string") {
      genres = [anime.genres_raw]
    }

    const score = anime.score ? Number(anime.score) : undefined
    const scoreText = score ? `★ ${score}` : undefined
    const genreText = genres.slice(0, 2).join(" · ")

    // Score or anime-themed dynamic gradient
    const accent = score && score >= 8
      ? "#FF7A59"
      : score && score >= 7
      ? "#F59E0B"
      : "#7C6CF0"

    return {
      image: imgSrc,
      title: anime.title || "Untitled Anime",
      subtitle: genreText || "Anime",
      handle: scoreText,
      location: anime.year ? `${anime.year}` : anime.type || undefined,
      borderColor: accent,
      gradient: `linear-gradient(155deg, ${accent}33 0%, rgba(15, 23, 42, 0.95) 70%, #060910 100%)`,
      data: anime,
    }
  })

  return (
    <div className="relative w-full overflow-hidden rounded-2xl">
      <ChromaGrid
        items={chromaItems}
        radius={280}
        damping={0.4}
        fadeOut={0.5}
        columns={4}
        onItemClick={(item) => onSelect(item.data)}
      />
    </div>
  )
}
