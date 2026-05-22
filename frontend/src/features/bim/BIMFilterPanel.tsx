/**
 * BIMFilterPanel — fast element filter + group sidebar for the BIM viewer.
 *
 * Supports:
 * - Free-text search across name / type / category / storey
 * - Storey/level multi-select
 * - Type multi-select (model-format-aware)
 *     - Revit models  → Revit Categories (Walls, Doors, Floors, Furniture, …)
 *     - IFC models    → IFC Entities (IfcWall, IfcSlab, IfcDoor, …)
 * - Group-by selector (storey / type)
 *
 * Performance:
 * - All counts are memoized from the `elements` prop (O(n) once per change)
 * - Filter predicate is rebuilt only when filter state changes
 * - Parent applies the predicate via ElementManager.applyFilter() which
 *   just toggles mesh.visible — no re-render of Three.js scene
 * - 16k+ elements tested
 */

import { useMemo, useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Search,
  Layers,
  Package,
  ChevronRight,
  ChevronDown,
  Eye,
  EyeOff,
  X,
  Link2,
  Bookmark,
  Trash2,
  AlertOctagon,
  AlertTriangle,
  Unlink,
  CheckSquare,
  FileText,
  Focus,
  Check,
  Plus,
} from "lucide-react";
import type { BIMElementGroup } from "./api";
import type { BIMElementData } from "@/shared/ui/BIMViewer";
import { getCategoryColor } from "@/shared/ui/BIMViewer/ElementManager";
import {
  bucketOf,
  isNoiseCategory,
  prettifyCategoryName,
  BUCKETS,
  type BIMCategoryBucket,
} from "./bimCategoryTaxonomy";

// ── Types ────────────────────────────────────────────────────────────────

export type GroupBy = "storey" | "type";

/** Top-level grouping mode for the type filter section.
 *
 *   • category — flat list of every unique element_type / IfcEntity,
 *                sorted by count.  Best matches "show me all the
 *                Revit categories / all the IfcEntities".  This is
 *                the default because it works for BOTH Revit and IFC
 *                without any noise / curation.
 *   • typename — hierarchical Category → Type Name (Revit Browser
 *                style: "Walls > Generic - 200mm").  Best for picking
 *                a single type out of a complex model.
 *   • buckets  — semantic buckets (Structure / Envelope / MEP / …)
 *                that aggregate categories into estimator-friendly
 *                groups.  Useful when you want a quick overview but
 *                hides the raw category names.
 */
export type GroupingMode = "category" | "typename" | "buckets";

export type BIMModelFormat = "rvt" | "ifc" | "other";

export interface BIMFilterState {
  search: string;
  storeys: Set<string>; // empty = show all
  types: Set<string>; // empty = show all
  /** When true, annotation/analytical categories are excluded from the
   *  viewport regardless of explicit type-filter selection. Defaults to
   *  true so first-time users see only real building elements. */
  buildingsOnly: boolean;
  groupBy: GroupBy;
}

interface BIMFilterPanelProps {
  elements: BIMElementData[];
  /** Active BIM model id — used as a useEffect dependency to reset
   *  the panel's transient filter state (search / storey / type
   *  selections / expanded headers / active group highlight) when
   *  the user switches to a different model.  Without this the
   *  filter UI shows checkboxes for storeys / types that don't
   *  exist in the new model. */
  modelId?: string;
  /** Raw model_format string from backend ("rvt" / "ifc" / …). */
  modelFormat?: string;
  onFilterChange: (
    predicate: (el: BIMElementData) => boolean,
    visibleCount: number,
  ) => void;
  onClose?: () => void;
  onElementClick?: (elementId: string) => void;
  /** When set, the panel shows a "Link to BOQ" button that opens the
   *  AddToBOQ modal populated with the current filtered subset. */
  onQuickTakeoff?: () => void;
  /** Current visible-element count from the parent (after applyFilter). */
  visibleElementCount?: number | null;
  /** When set, the panel shows a "Save as group" button that opens the
   *  SaveGroupModal pre-filled with the current filter criteria. */
  onSaveAsGroup?: (
    filter: BIMFilterState,
    visibleElements: BIMElementData[],
  ) => void;
  /** Saved element groups for the current model — rendered at the top of
   *  the panel as a one-click apply / link / delete row. */
  savedGroups?: BIMElementGroup[];
  /** User clicked a saved group → apply its filter_criteria to the panel. */
  onApplyGroup?: (group: BIMElementGroup) => void;
  /** User clicked the link icon on a saved group → link it to BOQ. */
  onLinkGroupToBOQ?: (group: BIMElementGroup) => void;
  /** User clicked the delete icon on a saved group. */
  onDeleteGroup?: (group: BIMElementGroup) => void;
  /** Smart filter chip clicked — applies a one-shot health-bucket filter
   *  (validation errors / unlinked / has tasks / has docs).  Routed up to
   *  BIMPage.handleSmartFilter which sets the same predicate as the
   *  in-viewport health stats banner. */
  onSmartFilter?: (
    filterId: "errors" | "warnings" | "unlinked_boq" | "has_tasks" | "has_docs",
  ) => void;
  /** Active isolation set in the viewer.  When non-null, the panel
   *  narrows its "visible" calculations (counts, type/storey buckets,
   *  Link-to-BOQ button, CSV export) to just these IDs so the user sees
   *  the same scope as the 3D viewport.  `null` means no isolation. */
  isolatedIds?: string[] | null;
  /** Clear the isolation set (parent → setIsolatedIds(null)).  Wired to
   *  the "Clear" button on the isolation banner so the user can exit
   *  isolation from the same place where its scope is displayed. */
  onClearIsolation?: () => void;
}

// ── Helpers ──────────────────────────────────────────────────────────────

/**
 * Detect whether the loaded model is Revit or IFC.
 * Priority: explicit `model_format` prop → element properties fallback.
 */
function detectModelFormat(
  modelFormat: string | undefined,
  elements: BIMElementData[],
): BIMModelFormat {
  const fmt = (modelFormat || "").toLowerCase();
  if (fmt.includes("rvt") || fmt.includes("revit")) return "rvt";
  if (fmt.includes("ifc")) return "ifc";

  // Fallback: inspect first element
  const first = elements[0];
  if (first) {
    if (first.element_type?.toLowerCase().startsWith("ifc")) return "ifc";
    const props = (first.properties || {}) as Record<string, unknown>;
    // If properties.category exists with a non-IFC value, it is likely Revit
    if (
      typeof props.category === "string" &&
      props.category &&
      !props.category.toLowerCase().startsWith("ifc")
    ) {
      return "rvt";
    }
    if (Object.keys(props).some((k) => String(k).toLowerCase().includes("revit"))) {
      return "rvt";
    }