import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Sparkles,
  Sliders,
  Radio,
  Share2,
  Database,
  RefreshCw,
} from "lucide-react";
import { profileApi, type ProfileOverview, type ConnectionItem, type TimelineItem, type TasteBridge } from "../api/profile";
import { ProfileHeader } from "../components/profile/ProfileHeader";
import { ConnectionsGrid } from "../components/profile/ConnectionsGrid";
import { InsightsTab } from "../components/profile/InsightsTab";
import { ControlsTab } from "../components/profile/ControlsTab";
import { TimelineFeed } from "../components/profile/TimelineFeed";
import { BridgesPanel } from "../components/profile/BridgesPanel";
import { TasteTags } from "../components/profile/TasteTags";
import { Card } from "../components/interchange/Card";

export type ProfileTab =
  | "overview"
  | "insights"
  | "controls"
  | "connections"
  | "share"
  | "data";

interface TabConfig {
  id: ProfileTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const TABS: TabConfig[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "insights", label: "Insights", icon: Sparkles },
  { id: "controls", label: "Controls", icon: Sliders },
  { id: "connections", label: "Connections", icon: Radio },
  { id: "share", label: "Share", icon: Share2 },
  { id: "data", label: "Data", icon: Database },
];

export function ProfilePage() {
  const [activeTab, setActiveTab] = useState<ProfileTab>("overview");
  const [overview, setOverview] = useState<ProfileOverview | null>(null);
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [errorOverview, setErrorOverview] = useState<string | null>(null);
  const [errorConnections, setErrorConnections] = useState<string | null>(null);

  // Phase 5 States
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [bridges, setBridges] = useState<TasteBridge[]>([]);
  const [tasteTags, setTasteTags] = useState<string[]>([]);
  const [loadingPhase5, setLoadingPhase5] = useState(true);

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

  const fetchPhase5Data = async () => {
    setLoadingPhase5(true);
    try {
      const [tl, br, tg] = await Promise.allSettled([
        profileApi.getTimeline(30),
        profileApi.getBridges(),
        profileApi.getTasteTags(),
      ]);
      if (tl.status === "fulfilled") setTimeline(tl.value);
      if (br.status === "fulfilled") setBridges(br.value);
      if (tg.status === "fulfilled") setTasteTags(tg.value);
    } catch {
      // non-fatal
    } finally {
      setLoadingPhase5(false);
    }
  };

  const reloadAll = () => {
    fetchOverviewData();
    fetchConnectionsData();
    fetchPhase5Data();
  };

  useEffect(() => {
    reloadAll();
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-6">
      {/* Top Header Card */}
      <ProfileHeader
        overview={overview}
        loading={loadingOverview}
        error={errorOverview}
      />

      {/* Navigation Tabs Bar */}
      <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 overflow-x-auto">
        <div className="flex gap-1 sm:gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
                  isActive
                    ? "border-emerald-500 text-zinc-900 dark:text-zinc-100 font-semibold"
                    : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <button
          onClick={reloadAll}
          className="p-2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
          title="Refresh profile data"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Active Tab View */}
      <div className="pt-2">
        {activeTab === "overview" && (
          <div className="space-y-6">
            <TasteTags tags={tasteTags} loading={loadingPhase5} />

            <BridgesPanel bridges={bridges} loading={loadingPhase5} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
              <ConnectionsGrid
                connections={connections}
                loading={loadingConnections}
                error={errorConnections}
                onRefresh={fetchConnectionsData}
              />
              <TimelineFeed timeline={timeline} loading={loadingPhase5} />
            </div>
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

        {activeTab === "insights" && <InsightsTab />}

        {activeTab === "controls" && <ControlsTab />}

        {activeTab === "share" && (
          <Card className="p-12 text-center">
            <Share2 className="w-8 h-8 text-pink-500 mx-auto mb-3" />
            <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
              Taste Passport & Sharing
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto mt-1">
              Generate your public Poly_Taste slug, compare compatibility, and download your taste card.
            </p>
          </Card>
        )}

        {activeTab === "data" && (
          <Card className="p-12 text-center">
            <Database className="w-8 h-8 text-amber-500 mx-auto mb-3" />
            <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
              Data Management & Export
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto mt-1">
              Export your profile signals, create Spotify playlists, view sync logs, or manage data.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
