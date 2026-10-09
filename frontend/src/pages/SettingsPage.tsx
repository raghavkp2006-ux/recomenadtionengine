import { useState, useEffect } from "react";
import {
  Palette,
  LayoutDashboard,
  Radio,
  Sliders,
  Share2,
  Database,
  Sun,
  Moon,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "../components/ui/ThemeProvider";
import { Card } from "../components/interchange/Card";
import { profileApi, type ProfileOverview, type ConnectionItem } from "../api/profile";
import { ProfileHeader } from "../components/profile/ProfileHeader";
import { ConnectionsGrid } from "../components/profile/ConnectionsGrid";
import { ControlsTab } from "../components/profile/ControlsTab";
import { ShareTab } from "../components/profile/ShareTab";
import { DataTab } from "../components/profile/DataTab";

export type SettingsTab =
  | "appearance"
  | "overview"
  | "connections"
  | "controls"
  | "share"
  | "data";

interface TabConfig {
  id: SettingsTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const TABS: TabConfig[] = [
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "overview", label: "Account Overview", icon: LayoutDashboard },
  { id: "connections", label: "Connected Services", icon: Radio },
  { id: "controls", label: "Recommendation Controls", icon: Sliders },
  { id: "share", label: "Passport & Sharing", icon: Share2 },
  { id: "data", label: "Data & Privacy", icon: Database },
];

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("appearance");
  const { theme, setTheme } = useTheme();

  // Overview and connections states for profile-level settings
  const [overview, setOverview] = useState<ProfileOverview | null>(null);
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [errorOverview, setErrorOverview] = useState<string | null>(null);
  const [errorConnections, setErrorConnections] = useState<string | null>(null);

  const fetchOverviewData = async () => {
    setLoadingOverview(true);
    setErrorOverview(null);
    try {
      const data = await profileApi.getOverview();
      setOverview(data);
    } catch (err: any) {
      setErrorOverview(err.message || "Failed to load overview");
    } finally {
      setLoadingOverview(false);
    }
  };

  const fetchConnectionsData = async () => {
    setLoadingConnections(true);
    setErrorConnections(null);
    try {
      const list = await profileApi.getConnections();
      setConnections(list);
    } catch (err: any) {
      setErrorConnections(err.message || "Failed to load connections");
    } finally {
      setLoadingConnections(false);
    }
  };

  const reloadAll = () => {
    fetchOverviewData();
    fetchConnectionsData();
  };

  useEffect(() => {
    reloadAll();
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-6">
      {/* Top Header Card */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#E4E4E7] dark:border-[#27272A]">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">
            Settings & Account Controls
          </h1>
          <p className="text-sm font-sans text-muted-foreground mt-1">
            Configure appearance, connected services, recommendation weights, and taste privacy.
          </p>
        </div>
        <button
          onClick={reloadAll}
          className="self-start md:self-auto flex items-center gap-2 px-3 py-1.5 text-xs font-mono rounded-lg border border-[#E4E4E7] dark:border-[#27272A] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
          title="Refresh settings state"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Sync Settings</span>
        </button>
      </div>

      {/* Navigation Tabs Bar */}
      <div className="flex items-center gap-1 sm:gap-2 border-b border-[#E4E4E7] dark:border-[#27272A] overflow-x-auto pb-px">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-3.5 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-all whitespace-nowrap cursor-pointer",
                isActive
                  ? "border-emerald-500 text-foreground font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      <div className="mt-4">
        {activeTab === "appearance" && (
          <div className="max-w-2xl space-y-6">
            <Card className="relative overflow-hidden">
              <div className="px-6 py-4 border-b border-[#E4E4E7] dark:border-[#27272A]">
                <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground">
                  Interface Theme
                </h3>
                <p className="text-xs font-sans text-muted-foreground mt-0.5">
                  Choose how PolyTaste looks on this screen and linked devices.
                </p>
              </div>

              <div className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <button
                    type="button"
                    onClick={() => setTheme("light")}
                    className={cn(
                      "flex flex-col items-center justify-center gap-3 p-4 rounded-xl border text-sm font-medium transition-all duration-150 cursor-pointer",
                      theme === "light"
                        ? "border-[#2563EB] bg-[#2563EB]/10 text-[#2563EB] shadow-sm ring-1 ring-[#2563EB]"
                        : "border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <Sun className="w-6 h-6" />
                    <span>Light Mode</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setTheme("dark")}
                    className={cn(
                      "flex flex-col items-center justify-center gap-3 p-4 rounded-xl border text-sm font-medium transition-all duration-150 cursor-pointer",
                      theme === "dark"
                        ? "border-[#2563EB] bg-[#2563EB]/10 text-[#2563EB] shadow-sm ring-1 ring-[#2563EB]"
                        : "border-[#E4E4E7] dark:border-[#27272A] bg-black/[0.02] dark:bg-white/[0.02] text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <Moon className="w-6 h-6" />
                    <span>Dark Mode</span>
                  </button>
                </div>

                <div className="flex items-center gap-2 pt-2 text-xs font-mono text-muted-foreground">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span>Theme preference is saved across sessions</span>
                </div>
              </div>
            </Card>
          </div>
        )}

        {activeTab === "overview" && (
          <div className="space-y-6">
            <ProfileHeader
              overview={overview}
              loading={loadingOverview}
              error={errorOverview}
            />
            <Card className="p-6">
              <h3 className="text-sm font-display font-semibold uppercase tracking-wide text-foreground mb-2">
                Account Summary
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Your PolyTaste identity consolidates signals from Spotify, AniList, fashion interactions,
                and ratings into a single cross-domain vector.
              </p>
            </Card>
          </div>
        )}

        {activeTab === "connections" && (
          <ConnectionsGrid
            connections={connections}
            loading={loadingConnections}
            error={errorConnections}
            onRefresh={fetchConnectionsData}
          />
        )}

        {activeTab === "controls" && <ControlsTab />}

        {activeTab === "share" && <ShareTab />}

        {activeTab === "data" && <DataTab />}
      </div>
    </div>
  );
}
