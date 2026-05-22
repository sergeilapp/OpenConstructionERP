import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Search,
  Copy,
  Check,
  Database,
  ChevronDown,
  Upload,
  Download,
  Loader2,
  Plus,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Hammer,
  HardHat,
  Package,
  Sparkles,
  Table2,
  FolderOpen,
  X,
  CheckSquare,
  Square,
  House,
  Star,
  Clock,
  Layers,
  TrendingUp,
  Trash2,
} from "lucide-react";
import {
  Button,
  Card,
  Badge,
  EmptyState,
  InfoHint,
  SkeletonTable,
  CountryFlag,
  Breadcrumb,
  ConfirmDialog,
} from "@/shared/ui";
import { useConfirm } from "@/shared/hooks/useConfirm";
import {
  apiGet,
  apiPost,
  apiDelete,
  triggerDownload,
  extractErrorMessageFromBody,
} from "@/shared/lib/api";
import { getIntlLocale } from "@/shared/lib/formatters";
import { useToastStore } from "@/stores/useToastStore";
import { useProjectContextStore } from "@/stores/useProjectContextStore";
import {
  useCostDatabaseStore,
  REGION_MAP,
} from "@/stores/useCostDatabaseStore";
import { useAuthStore } from "@/stores/useAuthStore";
import type { CostItemMetadata } from "./api";
import { CertaintyBadge } from "./CertaintyBadge";
import { EscalationCalculator } from "./EscalationCalculator";
import { RegionalAdjustPanel } from "./RegionalAdjustPanel";
import { CostCategoryTree } from "@/features/boq/CostCategoryTree";
import { fetchCategoryTree, type CategoryTreeNode } from "@/features/boq/api";

/* ── Types ─────────────────────────────────────────────────────────────── */

interface CostComponent {
  name: string;
  code: string;
  unit: string;
  /** Localized mirror of `unit` populated by the backend translation
   *  layer when a known locale is requested.  Render with the
   *  `unit_localized || unit` fallback chain — see `api.ts`. */
  unit_localized?: string;
  quantity: number;
  unit_rate: number;
  cost: number;
  type:
    | "material"
    | "labor"
    | "equipment"
    | "operator"
    | "electricity"
    | "other";
}

interface CostItem {
  id: string;
  code: string;
  description: string;
  unit: string;
  rate: number;
  region: string | null;
  classification: Record<string, string>;
  components: CostComponent[];
  /** Slim payloads (`?lite=1`) ship `components` as an empty array and
   *  carry the original count in this field so list UIs can still gate
   *  the "has breakdown" badge without paying for the full array. */
  components_count?: number;
  metadata_: CostItemMetadata;
  source: string;
}

interface CostSearchResponse {
  items: CostItem[];
  total: number;
  limit: number;
  offset: number;
}

interface RegionStat {
  region: string;
  count: number;
}

interface Project {
  id: string;
  name: string;
  currency: string;
}

interface BOQ {
  id: string;
  project_id: string;
  name: string;
  status: string;
}

interface BOQSection {
  id: string;
  ordinal: string;
  description: string;
  unit: string;
}

/* ── Export helper ─────────────────────────────────────────────────────── */

async function downloadExcelExport(): Promise<void> {
  const token = useAuthStore.getState().accessToken;
  const headers: Record<string, string> = {
    Accept: "application/octet-stream",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch("/api/v1/costs/actions/export-excel/", {
    method: "GET",
    headers,
  });
  if (!response.ok) {
    let detail = `Export failed (HTTP ${response.status})`;
    try {
      const body = await response.json();
      detail = extractErrorMessageFromBody(body) ?? detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition");
  const filename =
    disposition?.match(/filename="?(.+)"?/)?.[1] || "cost_database_export.xlsx";
  triggerDownload(blob, filename);
}

/* ── Favourites & Recently Used (localStorage) ────────────────────────── */

const FAVOURITES_KEY = "oe_cost_favourites";
const RECENT_KEY = "oe_cost_recent";
const MAX_RECENT = 20;

interface RecentItem {
  id: string;
  name: string;
  usedAt: string;
}

function loadFavourites(): Set<string> {
  try {
    const raw = localStorage.getItem(FAVOURITES_KEY);
    if (raw) return new Set(JSON.parse(raw) as string[]);
  } catch {
    // ignore
  }
  return new Set();
}

function saveFavourites(ids: Set<string>): void {
  localStorage.setItem(FAVOURITES_KEY, JSON.stringify([...ids]));
}

function loadRecent(): RecentItem[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (raw) return JSON.parse(raw) as RecentItem[];
  } catch {
    // ignore
  }
  return [];
}

function addRecentItem(item: { id: string; description: string }): void {
  const list = loadRecent().filter((r) => r.id !== item.id);
  list.unshift({
    id: item.id,
    name: item.description,
    usedAt: new Date().toISOString(),
  });
  if (list.length > MAX_RECENT) list.length = MAX_RECENT;
  localStorage.setItem(RECENT_KEY, JSON.stringify(list));
}

/* ── Mini flag ─────────────────────────────────────────────────────────── */

function MiniFlag({ code, size = 14 }: { code: string; size?: number }) {
  if (!code || code === "custom") {
    return <House size={size} className="shrink-0 text-oe-blue" />;
  }
  return (
    <CountryFlag
      code={code}
      size={Math.round(size * 1.6)}
      className="shadow-xs border border-black/5"
    />
  );
}

/* ── Region Tab Bar ───────────────────────────────────────────────────── */

function RegionTabBar({
  regions,
  regionStats,
  activeRegion,
  onChangeRegion,
  totalItemCount,
  /** ``true`` while ``/v1/costs/regions/`` is still in-flight on first
   *  paint. The endpoint does a SELECT DISTINCT scan over the active
   *  catalog and can take 18 s on cold SQLite when 100 k+ rows are
   *  loaded, so we MUST distinguish "still loading" from "definitely
   *  empty" — the previous code conflated the two and showed
   *  "No database loaded" for the entire 18 s wait, which the user
   *  reported as "the page never loads". */
  isLoadingRegions,
}: {
  regions: string[];
  regionStats: RegionStat[];
  activeRegion: string;
  onChangeRegion: (region: string) => void;
  totalItemCount: number;
  isLoadingRegions: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const totalItems = regionStats.reduce((s, r) => s + r.count, 0);
  const statsMap = new Map(regionStats.map((r) => [r.region, r.count]));

  // Check scroll overflow
  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    checkScroll();
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", checkScroll, { passive: true });
    const ro = new ResizeObserver(checkScroll);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", checkScroll);
      ro.disconnect();
    };
  }, [checkScroll, regions]);

  const scroll = useCallback((dir: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === "left" ? -200 : 200, behavior: "smooth" });
  }, []);

  // While the regions request is still in-flight, render a tab-bar
  // skeleton instead of the "No database loaded" empty state. Cold
  // SQLite responds in ~18 s on 100 k+ catalogs; without this guard
  // the user sees the empty state for the entire wait and assumes the
  // app is broken.
  if (isLoadingRegions && regions.length === 0) {
    return (
      <div
        className="mb-5 flex items-center gap-2"
        data-testid="costs-region-tabs-skeleton"
        aria-busy="true"
      >
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-9 w-24 rounded-t-lg bg-surface-secondary/60 animate-pulse"
          />
        ))}
        <span className="ms-3 text-xs text-content-tertiary inline-flex items-center gap-2">
          <Loader2 size={12} className="animate-spin" />
          {t("costs.loading_databases", {
            defaultValue: "Loading databases…‌⁠‍",
          })}
        </span>
      </div>
    );
  }

  if (regions.length === 0 && totalItemCount === 0) {
    // Use the shared EmptyState component so the copy + CTA are consistent
    // with the other module empty states (favourites, recent, no-results).
    // The CTA routes to the regional-database importer.
    return (
      <div
        className="mb-6"
        data-testid="costs-no-database-empty-state"
      >
        <EmptyState
          icon={<Database size={28} strokeWidth={1.5} />}
          title={t('costs.no_database_loaded', { defaultValue: 'No database loaded‌⁠‍' })}
          description={t('costs.import_first_hint', {
            defaultValue: 'Import a regional cost database to start searching 55,000+ items.‌⁠‍',
          })}
          action={{
            label: t('costs.import_regional_database', {
              defaultValue: 'Import a regional database‌⁠‍',
            }),
            onClick: () => navigate('/costs/import'),
          }}
        />