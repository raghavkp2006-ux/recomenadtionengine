import { cn } from "@/lib/utils"
import {
  Home,
  Tv,
  Music,
  Compass,
  ShoppingBag,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Layers,
  Fingerprint,
  Film,
} from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import type { PageId } from "../../types"
import { api } from "../../api"
import { domainColor, domainAlpha, fontFamily } from "../../tokens"
import type { Domain } from "../../tokens"
import { ConnectionBadge } from "../interchange"

interface NavItem {
  id: PageId
  label: string
  icon: React.ElementType
  color: string
}

const navItems: NavItem[] = [
  { id: "home",        label: "Home",        icon: Home,            color: "#A1A1AA" },
  { id: "anime",       label: "Anime",        icon: Tv,              color: "#4F9C8C" },
  { id: "music",       label: "Music",        icon: Music,           color: "#E8553F" },
  { id: "places",      label: "Places",       icon: Compass,         color: "#E3A857" },
  { id: "movies",      label: "Movies",       icon: Film,            color: "#6366F1" },
  { id: "myntra",      label: "Fashion",      icon: ShoppingBag,     color: "#D946EF" },
  { id: "profile",     label: "Profile",      icon: Fingerprint,     color: "#3ED6C4" },
  { id: "settings",    label: "Settings",     icon: Settings,        color: "#A1A1AA" },
]

interface SidebarProps {
  currentPage: PageId
  onNavigate: (page: PageId) => void
  onLogout?: () => void
  collapsed: boolean
  onToggleCollapse: () => void
  connections?: { spotify: boolean; anilist: boolean; location: boolean; myntra: boolean } | null
}

function ConnectionItem({
  label,
  connected,
  domain,
  onClick
}: {
  label: string
  connected: boolean
  domain: Domain
  onClick: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center justify-between p-1.5 rounded-lg text-xs transition-all duration-200",
        !connected && "cursor-pointer hover:bg-black/5 dark:hover:bg-white/5"
      )}
      style={{ fontFamily: fontFamily.body }}
    >
      <div className="flex items-center gap-2">
        <ConnectionBadge connected={connected} domain={domain} size={14} />
        <span
          className={cn(
            connected ? "text-[#18181B] dark:text-[#FAFAFA]" : "text-[#A1A1AA] dark:text-[#71717A]",
            connected ? "font-medium" : "font-normal",
            "transition-colors duration-150 ease-out"
          )}
        >
          {label}
        </span>
      </div>
      <span
        className={cn(
          "text-[9px] uppercase tracking-wider transition-colors duration-150 ease-out",
          connected ? "text-[#2563EB] dark:text-[#3B82F6]" : "text-[#A1A1AA] dark:text-[#71717A]"
        )}
        style={{ fontFamily: fontFamily.mono }}
      >
        {connected ? "Connected" : "Connect"}
      </span>
    </div>
  )
}

export function Sidebar({
  currentPage,
  onNavigate,
  onLogout,
  collapsed,
  onToggleCollapse,
  connections,
}: SidebarProps) {
  return (
    <>
      {/* ── Desktop sidebar ─────────────────────────────────────── */}
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 72 : 240 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className={cn(
          "hidden md:flex flex-col fixed left-0 top-0 h-screen z-40 bg-[#FFFFFF] dark:bg-[#18181B] transition-colors duration-150 ease-out border-r border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out",
          "overflow-hidden"
        )}
      >
        {/* Logo area */}
        <div className="flex items-center h-16 px-4 border-b border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out shrink-0">
          <AnimatePresence mode="wait">
            {!collapsed && (
              <motion.div
                key="logo-full"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="flex items-center gap-2.5 min-w-0"
              >
                <LogoMark size={28} />
                <span
                  className="text-base font-semibold tracking-tight truncate text-[#18181B] dark:text-[#FAFAFA]"
                  style={{ fontFamily: fontFamily.display }}
                >
                  Poly_Taste
                </span>
              </motion.div>
            )}
          </AnimatePresence>
          {collapsed && (
            <div className="mx-auto">
              <LogoMark size={28} />
            </div>
          )}
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-4 space-y-0.5 px-3 overflow-y-auto scrollbar-hide">
          {navItems.map((item) => {
            const isActive = currentPage === item.id
            const Icon = item.icon

            return collapsed ? (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "relative flex items-center justify-center w-full rounded-lg",
                  "h-10 transition-all duration-200",
                  "hover:bg-black/5",
                  isActive && "bg-black/5"
                )}
                title={item.label}
                aria-label={item.label}
              >
                <Icon
                  className={cn(
                    "h-5 w-5 shrink-0 transition-colors",
                    isActive ? "text-[#2563EB] dark:text-[#3B82F6]" : "text-[#A1A1AA] dark:text-[#A1A1AA]"
                  )}
                />
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active-collapsed"
                    className={cn(
                      "absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full",
                      isActive ? "bg-[#2563EB] dark:bg-[#3B82F6]" : "bg-[#A1A1AA] dark:bg-[#A1A1AA]"
                    )}
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
                {isActive && (
                  /* Glow halo behind icon */
                  <div
                    className={cn(
                      "absolute inset-0 rounded-lg opacity-10",
                      isActive ? "bg-[#2563EB] dark:bg-[#3B82F6]" : "bg-[#A1A1AA] dark:bg-[#A1A1AA]"
                    )}
                  />
                )}
              </button>
            ) : (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "relative flex items-center w-full rounded-lg px-3 py-2.5",
                  "text-sm transition-all duration-200",
                  "hover:bg-black/5",
                  isActive ? "bg-black/5 dark:bg-white/5 font-medium text-[#2563EB] dark:text-[#3B82F6]" : "font-normal text-[#A1A1AA] dark:text-[#A1A1AA]"
                )}
                style={{ fontFamily: fontFamily.body }}
              >
                {/* Active left glow bar */}
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full"
                    style={{ backgroundColor: isActive ? "#2563EB" : "#A1A1AA", boxShadow: `0 0 8px ${isActive ? "#2563EB" : "#A1A1AA"}80` }}
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
                {/* Active bg glow */}
                {isActive && (
                  <div
                    className="absolute inset-0 rounded-lg opacity-5"
                    style={{ backgroundColor: isActive ? "#2563EB" : "#A1A1AA" }}
                  />
                )}

                <Icon
                  className={cn(
                    "h-5 w-5 shrink-0 relative z-10",
                    isActive ? "text-[#2563EB] dark:text-[#3B82F6]" : "text-[#A1A1AA] dark:text-[#A1A1AA]"
                  )}
                />
                <AnimatePresence mode="wait">
                  {!collapsed && (
                    <motion.span
                      key={`label-${item.id}`}
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      className={cn("ml-3 truncate relative z-10", isActive ? "text-[#18181B] dark:text-[#FAFAFA]" : "text-[#A1A1AA] dark:text-[#A1A1AA]")}
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            )
          })}
        </nav>

        {/* Connection status indicators */}
        {connections && (
          !collapsed ? (
            <div className="px-4 py-3 border-t border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out space-y-2 shrink-0">
              <div 
                className="text-[10px] font-semibold uppercase tracking-wider text-[#A1A1AA] dark:text-[#A1A1AA]"
                style={{ fontFamily: fontFamily.display }}
              >
                Connections
              </div>
              <div className="flex flex-col gap-1">
                <ConnectionItem
                  label="Spotify"
                  connected={connections.spotify}
                  domain="music"
                  onClick={() => {
                    if (!connections.spotify) window.location.href = api.auth.loginUrl
                  }}
                />
                <ConnectionItem
                  label="AniList"
                  connected={connections.anilist}
                  domain="anime"
                  onClick={() => {
                    if (!connections.anilist) window.location.href = api.anilist.loginUrl
                  }}
                />
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-3 border-t border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out shrink-0">
              <div
                className="cursor-pointer"
                onClick={() => {
                  if (!connections.spotify) window.location.href = api.auth.loginUrl
                }}
                title={`Spotify: ${connections.spotify ? "Connected" : "Not connected (Click to connect)"}`}
              >
                <ConnectionBadge connected={connections.spotify} domain="music" size={24} letter="S" />
              </div>
              <div
                className="cursor-pointer"
                onClick={() => {
                  if (!connections.anilist) window.location.href = api.anilist.loginUrl
                }}
                title={`AniList: ${connections.anilist ? "Connected" : "Not connected (Click to connect)"}`}
              >
                <ConnectionBadge connected={connections.anilist} domain="anime" size={24} letter="A" />
              </div>
            </div>
          )
        )}

        {/* Bottom controls */}
        <div className="p-3 border-t border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out space-y-1 shrink-0">
          {/* Collapse toggle */}
          <button
            onClick={onToggleCollapse}
            className={cn(
              "flex items-center w-full rounded-lg p-2 text-[#A1A1AA] dark:text-[#A1A1AA]",
              "hover:bg-black/5 dark:hover:bg-white/5 transition-all duration-200",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed ? "justify-center" : ""
            )}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4 mr-2" />
                <span className="text-xs" style={{ fontFamily: fontFamily.body }}>Collapse</span>
              </>
            )}
          </button>

          {/* Logout */}
          {onLogout && (
            <button
              onClick={onLogout}
              className={cn(
                "flex items-center w-full rounded-lg p-2 text-[#A1A1AA] dark:text-[#A1A1AA]",
                "hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-500",
                "transition-all duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                collapsed ? "justify-center" : ""
              )}
              aria-label="Logout"
            >
              {collapsed ? (
                <LogOut className="h-4 w-4" />
              ) : (
                <>
                  <LogOut className="h-4 w-4 mr-2" />
                  <span className="text-xs" style={{ fontFamily: fontFamily.body }}>Logout</span>
                </>
              )}
            </button>
          )}
        </div>
      </motion.aside>

      <nav
        className={cn(
          "md:hidden fixed bottom-0 left-0 right-0 z-40",
          "flex items-center justify-around h-16",
          "border-t border-[#E4E4E7] dark:border-[#27272A] transition-colors duration-150 ease-out"
        )}
      >
        {navItems.map((item) => {
          const isActive = currentPage === item.id
          const Icon = item.icon
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={cn(
                "relative flex flex-col items-center gap-0.5 py-2 px-3 rounded-lg",
                "transition-all duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive ? "text-[#2563EB] dark:text-[#3B82F6]" : "text-[#A1A1AA] dark:text-[#A1A1AA]"
              )}
              aria-label={item.label}
            >
              <Icon className="h-5 w-5" />
              <span className={cn("text-[10px] font-medium", isActive ? "text-[#18181B] dark:text-[#FAFAFA]" : "text-[#A1A1AA] dark:text-[#A1A1AA]")} style={{ fontFamily: fontFamily.body }}>{item.label}</span>
              {isActive && (
                <motion.div
                  layoutId="mobile-active"
                  className="absolute -bottom-1 h-[2px] w-5 rounded-full"
                  style={{
                    backgroundColor: isActive ? "#2563EB" : "#A1A1AA",
                    boxShadow: `0 0 6px ${isActive ? "#2563EB" : "#A1A1AA"}`,
                  }}
                  transition={{ type: "spring", stiffness: 350, damping: 30 }}
                />
              )}
            </button>
          )
        })}
      </nav>
    </>
  )
}

// ── Logo mark component ─────────────────────────────────────────────

function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: `linear-gradient(135deg, ${domainColor.music} 0%, #3ED6C4 100%)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        boxShadow: `0 0 12px ${domainAlpha("music", 0.4)}`,
      }}
    >
      <Layers
        style={{
          width: size * 0.52,
          height: size * 0.52,
          color: "#FFFFFF",
          strokeWidth: 2.5,
        }}
      />
    </div>
  )
}
