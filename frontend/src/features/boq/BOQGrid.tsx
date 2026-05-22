import {
  useState,
  useMemo,
  useCallback,
  useRef,
  useEffect,
  forwardRef,
  useImperativeHandle,
} from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { AgGridReact } from "ag-grid-react";
import type {
  GridApi,
  CellValueChangedEvent,
  CellEditingStartedEvent,
  CellEditingStoppedEvent,
  RowDragEndEvent,
  GridReadyEvent,
  GetRowIdParams,
  RowClassParams,
  ColumnResizedEvent,
  TabToNextCellParams,
  CellPosition,
  SelectionChangedEvent,
  IsFullWidthRowParams,
  RowHeightParams,
  CellContextMenuEvent,
} from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import {
  Plus,
  Database,
  MessageSquare,
  Trash2,
  Copy,
  ChevronDown,
  ChevronRight,
  BookmarkPlus,
  ExternalLink,
  Wrench,
  X,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  Tag,
  Layers,
  Boxes,
  Cuboid,
  Link2,
  Link2Off,
} from "lucide-react";

import {
  type Position,
  type UpdatePositionData,
  type CostAutocompleteItem,
  type ResourceCodeMatch,
  isSection,
  getPositionDepth,
  DEFAULT_MAX_NESTING_DEPTH,
} from "./api";
import {
  acquireLock as acquireCollabLock,
  releaseLock as releaseCollabLock,
  type CollabLock,
} from "@/features/collab_locks";
import { getColumnDefs, getCustomColumnDefs } from "./grid/columnDefs";
import type { FormulaVariable } from "./grid/formula";
import {
  FormulaCellEditor,
  AutocompleteCellEditor,
  UnitCellEditor,
} from "./grid/cellEditors";
import {
  ActionsCellRenderer,
  ExpandCellRenderer,
  OrdinalCellRenderer,
  BimLinkCellRenderer,
  QuantityCellRenderer,
  UnitCellRenderer,
  UnitRateCellRenderer,
  SectionFullWidthRenderer,
  ResourceFullWidthRenderer,
  BimQtyPickerCellRenderer,
  DescriptionCellRenderer,
  type ContextMenuTarget,
  type FullGridContext,
} from "./grid/cellRenderers";
import { countComments } from "./CommentDrawer";
import {
  convertToBase,
  fmtWithCurrency,
  getUnitsForLocale,
  resourceAwareTotalInBase,
  saveCustomUnit,
} from "./boqHelpers";
import { RESOURCE_TYPES, getResourceTypeLabel } from "./boqResourceTypes";
import { CURRENCY_GROUPS } from "@/features/projects/CreateProjectPage";
import { useToastStore } from "@/stores/useToastStore";
import { getIntlLocale } from "@/shared/lib/formatters";
import { VariantPicker } from "@/features/costs/VariantPicker";
import type { CostVariant, VariantStats } from "@/features/costs/api";

/* ── Column width persistence ─────────────────────────────────────── */

const COLUMN_WIDTHS_KEY = "oe_boq_column_widths";

function loadColumnWidths(): Record<string, number> {
  try {
    const raw = localStorage.getItem(COLUMN_WIDTHS_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // Ignore corrupt data
  }
  return {};
}

function saveColumnWidths(widths: Record<string, number>): void {
  try {
    localStorage.setItem(COLUMN_WIDTHS_KEY, JSON.stringify(widths));
  } catch {
    // Ignore storage errors (quota, etc.)
  }
}

/* ── Clipboard: fields that cannot be pasted into ─────────────────── */

/** Columns that are computed or read-only — paste is suppressed for these. */
const PASTE_PROTECTED_FIELDS = new Set([
  "total",
  "_actions",
  "_drag",
  "_checkbox",
  "_expand",
  "_bim_link",
  "_bim_qty",
]);

/** Numeric column fields — pasted text must be parsed to a number. */
const NUMERIC_FIELDS = new Set(["quantity", "unit_rate"]);

/**
 * Parse a pasted string into a number. Handles thousand separators
 * (both comma and period variants) and strips currency symbols.
 * Returns NaN when the string is not a valid number.
 */
export function parseClipboardNumber(raw: string): number {
  // Strip leading/trailing whitespace
  let cleaned = raw.trim();
  // Remove common currency symbols / prefixes that users may copy from spreadsheets
  cleaned = cleaned.replace(/^[€$£¥₹₽Fr.C\$A\$NZ\$zł₺Kčkr]+/i, "").trim();
  // If both comma and period are present, the last one is the decimal separator
  const hasComma = cleaned.includes(",");
  const hasPeriod = cleaned.includes(".");
  if (hasComma && hasPeriod) {
    if (cleaned.lastIndexOf(",") > cleaned.lastIndexOf(".")) {
      // e.g. "1.234,56" → period is thousand sep, comma is decimal
      cleaned = cleaned.replace(/\./g, "").replace(",", ".");
    } else {
      // e.g. "1,234.56" → comma is thousand sep, period is decimal
      cleaned = cleaned.replace(/,/g, "");
    }
  } else if (hasComma && !hasPeriod) {
    // Could be "1,5" (decimal) or "1,000" (thousand sep).
    // Heuristic: if exactly 3 digits after the last comma, treat as thousand sep.
    const parts = cleaned.split(",");
    const lastPart = parts[parts.length - 1] ?? "";
    if (
      parts.length === 2 &&
      lastPart.length === 3 &&
      (parts[0] ?? "").length <= 3
    ) {
      // Ambiguous — but "1,000" is more likely thousand-separated in BOQ context
      cleaned = cleaned.replace(/,/g, "");
    } else {
      cleaned = cleaned.replace(",", ".");
    }
  }
  return parseFloat(cleaned);
}

/* ── Types ─────────────────────────────────────────────────────────── */

interface FooterRow {
  _isFooter: true;
  _footerType: string;
  id: string;
  description: string;
  total: number;
  ordinal: string;
  unit: string;
  quantity: number;
  unit_rate: number;
}

interface SectionRow {
  _isSection: true;
  _childCount: number;
  _subtotal: number;
  /**
   * Issue #136 — nesting level of this row in the section tree.
   * 0 = top-level. Drives left-indentation so sections-within-sections
   * and their child positions read as a real hierarchy in the grid.
   * Present on section rows AND on the position rows beneath them.
   */
  _depth?: number;
}

interface ResourceRow {
  _isResource: true;
  _parentPositionId: string;
  _resourceIndex: number;
  _resourceName: string;
  _resourceType: string;
  _resourceUnit: string;
  _resourceQty: number;
  _resourceRate: number;
  /** Optional ISO 4217 code for foreign-currency resources (RFC 37 / #93). */
  _resourceCurrency?: string;
  /** Optional resource code (e.g. CWICR id) — used by inline editor. */
  _resourceCode?: string;
  /**
   * Cached CWICR variant catalog for this resource (v2.6.26+).  Populated at
   * apply-time from ``CostItem.metadata_.variants``; absent on legacy rows.
   * Drives the per-resource re-pick pill.
   */
  _resourceAvailableVariants?: Array<Record<string, unknown>>;
  /** Aggregate stats matching ``_resourceAvailableVariants`` for the picker UI. */
  _resourceAvailableVariantStats?: Record<string, unknown>;
  /** Currently-applied variant marker (mirrors the resource's ``variant`` key). */
  _resourceVariant?: { label: string; price: number; index: number };
  /** Auto-default strategy when the user accepted mean / median (no explicit pick). */
  _resourceVariantDefault?: "mean" | "median";
  /** Frozen snapshot stamped by the backend; surfaced for hover tooltips. */
  _resourceVariantSnapshot?: Record<string, unknown>;
  id: string;
  // Fields needed for GridRow compatibility
  description: string;
  ordinal: string;
  unit: string;
  quantity: number;
  unit_rate: number;
  total: number;
}

interface AddResourceRow {
  _isAddResource: true;
  _parentPositionId: string;
  _positionResourceTotal: number;
  id: string;
  description: string;
  ordinal: string;
  unit: string;
  quantity: number;
  unit_rate: number;
  total: number;
}

/**
 * Synthetic "abstract variant" header row prepended to the resource panel
 * for legacy CWICR position-mode applies. Surfaces the variant catalog
 * (``cost_item_variants``) as a visible, clickable row inside the resource
 * area so the user finds the picker by scanning down — not just by hunting
 * the description-cell V icon. The row is read-only and its only action
 * is to re-open the position-level picker (same as the V icon).
 */
interface VariantHeaderRow {
  _isVariantHeader: true;
  _parentPositionId: string;
  _variantHeaderName: string;
  _variantHeaderChosenLabel: string | null;
  _variantHeaderChosenPrice: number | null;
  _variantHeaderCount: number;
  _variantHeaderCurrency: string;
  /** Position-level quantity — the abstract variant inherits the position's
   *  quantity so the user sees the same volume × variant-price math as on
   *  the position row above (and on every other component resource). */
  _variantHeaderQty: number;
  /** Position-level unit (e.g. "t", "m³"). Needed to render the unit cell
   *  in alignment with the rest of the resource grid. */
  _variantHeaderUnit: string;
  id: string;
  // Fields needed for GridRow compatibility (kept empty / 0).
  description: string;
  ordinal: string;
  unit: string;
  quantity: number;
  unit_rate: number;
  total: number;
}

type GridRow =
  | (Position & Partial<SectionRow>)
  | (FooterRow & Record<string, unknown>)
  | (ResourceRow & Record<string, unknown>)
  | (AddResourceRow & Record<string, unknown>)
  | (VariantHeaderRow & Record<string, unknown>);

export interface ManualResource {
  name: string;
  type: string;
  unit: string;
  quantity: number;
  unit_rate: number;
  /** Optional ISO 4217 code for foreign-currency resources (RFC 37 / #93). */
  currency?: string;
  /** Optional reusable resource code (Issue #133). Persisted on the
   *  resource entry so it stays referenceable for future reuse. */
  code?: string;
}

export interface BOQGridProps {
  positions: Position[];
  onUpdatePosition: (
    id: string,
    data: UpdatePositionData,
    oldData: UpdatePositionData,
  ) => void;
  onDeletePosition: (id: string) => void;
  onAddPosition: (sectionId?: string) => void;
  onSelectSuggestion: (positionId: string, item: CostAutocompleteItem) => void;
  onSaveToDatabase: (positionId: string) => void;
  onAddComment?: (positionId: string) => void;
  onFormulaApplied: (
    positionId: string,
    formula: string,
    result: number,
  ) => void;
  onReorderSections?: (fromId: string, toId: string) => void;
  onReorderPositions?: (reorderedIds: string[]) => void;
  onDeleteSection?: (sectionId: string) => void;
  collapsedSections: Set<string>;
  onToggleSection: (sectionId: string) => void;
  highlightPositionId?: string;
  currencySymbol: string;
  currencyCode: string;
  /**
   * Optional FX rate template (RFC 37 / #93). Used by per-resource currency
   * picker. Each entry maps a foreign currency to a rate-to-base.
   */
  fxRates?: { currency: string; rate: number; label?: string }[];
  /**
   * ── Display-currency override (Issue #88 follow-up).
   * When set, all monetary aggregates rendered by the grid (per-position
   * total, section subtotals, footer rows) are formatted in `code` using
   * `rate` for conversion. View-only — does NOT alter what the server
   * persists. `null` / undefined ⇒ render in project base currency.
   */
  displayCurrency?: { code: string; rate: number } | null;
  /**
   * Issue #105 — open-handler for the Project Settings → FX Rates page.
   * Wired by BOQEditorPage to `navigate('/projects/:id/settings#fx-rates')`.
   * When omitted, the warning badge stays a non-clickable info chip.
   */
  onOpenFxRateSettings?: () => void;
  locale: string;
  footerRows: FooterRow[];
  onSelectionChanged?: (selectedIds: string[]) => void;
  /**
   * Issue #139 — the row the user last *interacted with* (clicked a cell
   * in / focused), regardless of checkbox selection. ``rowSelection`` has
   * ``enableClickSelection:false`` (a plain click edits, it does NOT tick
   * the checkbox), so ``onSelectionChanged`` stays empty when the user
   * simply clicks a partida and hits "Add Position". Without this signal
   * the editor fell back to appending at the LAST section instead of
   * inserting directly below the clicked row — the exact #139 symptom.
   * ``null`` clears the anchor (focus left the data rows).
   */
  onActiveRowChange?: (positionId: string | null) => void;
  onRemoveResource?: (positionId: string, resourceIndex: number) => void;
  onUpdateResource?: (
    positionId: string,
    resourceIndex: number,
    field: string,
    value: number | string,
  ) => void;
  onUpdateResourceFields?: (
    positionId: string,
    resourceIndex: number,
    fields: Record<string, number | string>,
  ) => void;
  /** Per-resource custom-field write — stored at
   *  ``parent.metadata.resources[i].metadata.custom_fields[fieldName]`` so a
   *  resource can carry its own supplier / lead time / QC inspector etc. */
  onUpdateResourceCustomField?: (
    positionId: string,
    resourceIndex: number,
    fieldName: string,
    value: number | string,
  ) => void;
  onSaveResourceToCatalog?: (positionId: string, resourceIndex: number) => void;
  /**
   * Save the variant-header synthetic row to the user's catalog under a
   * custom name. The variant header is not in ``metadata.resources`` so the
   * standard ``onSaveResourceToCatalog`` can't reach it — this dedicated
   * handler reads the chosen variant off the position metadata directly.
   */
  onSaveVariantHeaderToCatalog?: (
    positionId: string,
    customName: string,
  ) => void;
  onOpenCostDbForPosition?: (positionId: string) => void;
  onOpenCatalogForPosition?: (positionId: string) => void;
  /**
   * Re-pick the variant on an already-added resource row (v2.6.26+).
   * Reads ``available_variants`` cached on the resource entry and PATCHes
   * ``/positions/{id}/resources/{idx}/variant/`` server-side. Optional —
   * when omitted, the row's re-pick pill is hidden (graceful degrade).
   */
  onRepickResourceVariant?: (
    positionId: string,
    resourceIndex: number,
    variantCode: string,
  ) => void;
  onAddManualResource?: (positionId: string, resource: ManualResource) => void;
  /**
   * Issue #133 — project-wide resource-code lookup. When the user types a
   * code in the manual-resource form that is already used elsewhere,
   * resolve the existing resource's reusable definition so the form can
   * offer "insert the existing resource" vs "create a new one with
   * another code". Returns ``null`` when the code is free. Optional —
   * when omitted the code is treated as a plain free-text field.
   */
  onLookupResourceByCode?: (code: string) => Promise<ResourceCodeMatch | null>;
  onDuplicatePosition?: (positionId: string) => void;
  /**
   * Issue #127 — reuse an existing project code at a given placement.
   * Prompts for the code and creates a linked instance (own ordinal + own
   * editable quantity). `sectionId` scopes the placement when invoked from
   * a section row.
   */
  onReuseCode?: (sectionId?: string) => void;
  /**
   * Issue #136 — add a child Partida under the given position (deep
   * nesting of partidas-within-partidas). Disabled in the UI once the
   * configurable depth cap is reached.
   */
  onAddChildPosition?: (parentId: string) => void;
  /**
   * Issue #136 — add a sub-section under the given section (deep nesting
   * of sections-within-sections). Disabled at the depth cap.
   */
  onAddSubSection?: (parentSectionId: string) => void;
  /**
   * Issue #136 — server-enforced maximum nesting depth (tiers). The grid
   * disables "add child" / "add sub-section" once a row sits at this
   * depth and shows an i18n tooltip explaining the cap.
   */
  maxNestingDepth?: number;
  /** Issue #127 — open the linked-positions modal for a position. */
  onShowLinks?: (positionId: string) => void;
  /** Issue #127 — detach a position from its shared code (value-preserving). */
  onUnlinkPosition?: (positionId: string) => void;
  /** Feature 1 — open the model→quantity binding panel for a position. */
  onModelLink?: (positionId: string) => void;
  /* AI features */
  onSuggestRate?: (positionId: string) => void;
  onClassify?: (positionId: string) => void;
  onCheckAnomalies?: () => void;
  /** Map of position_id → anomaly info, populated from anomaly check */
  anomalyMap?: Map<
    string,
    { severity: string; message: string; suggestion: number }
  >;
  /** Apply the suggested rate from an anomaly to a position */
  onApplyAnomalySuggestion?: (
    positionId: string,
    suggestedRate: number,
  ) => void;
  /** Save a BOQ position as a reusable assembly */
  onSaveAsAssembly?: (positionId: string) => void;
  /** Custom column definitions from BOQ metadata */
  customColumns?: import("./grid/columnDefs").CustomColumnDef[];
  /**
   * BOQ-scoped named variables ($GFA, $LABOR_RATE, …). Used by `calculated`
   * custom columns; safe to omit when no calculated columns are defined.
   */
  boqVariables?: import("./api").BOQVariable[];
  /** First ready BIM model ID for the project (used for mini 3D preview in ordinal badge). */
  bimModelId?: string | null;
  /** Highlight linked BIM elements in the 3D viewer (triggered from ordinal badge click). */
  onHighlightBIMElements?: (elementIds: string[]) => void;
}

/** Imperative handle exposed by BOQGrid for external control (e.g. clearing selection). */
export interface BOQGridHandle {
  clearSelection: () => void;
  /**
   * Open a freshly-added leaf partida directly in inline edit on its
   * Description cell, so the user types straight away instead of hunting
   * for a cell to click ("Click any cell to edit" UX gap). Polls briefly
   * because the row only materialises after the post-add refetch; a no-op
   * for sections, collapsed/missing rows, or once the retry budget is
   * spent (graceful fall-back to the previous click-to-edit behaviour).
   */
  beginEditDescription: (positionId: string) => void;
}

/* ── Component ─────────────────────────────────────────────────────── */

const BOQGrid = forwardRef<BOQGridHandle, BOQGridProps>(function BOQGrid({
  positions,
  onUpdatePosition,
  onDeletePosition,
  onAddPosition,
  onSelectSuggestion: _onSelectSuggestion,
  onSaveToDatabase,
  onAddComment,
  onFormulaApplied,
  onReorderSections,
  onReorderPositions,
  onDeleteSection,
  collapsedSections,
  onToggleSection,
  highlightPositionId,
  currencySymbol,
  currencyCode,
  fxRates,
  displayCurrency,
  onOpenFxRateSettings,
  locale,
  footerRows,
  onSelectionChanged,
  onActiveRowChange,
  onRemoveResource,
  onUpdateResource,
  onUpdateResourceFields,
  onUpdateResourceCustomField,
  onSaveResourceToCatalog,
  onSaveVariantHeaderToCatalog,
  onOpenCostDbForPosition,
  onOpenCatalogForPosition,
  onRepickResourceVariant,
  onAddManualResource,
  onLookupResourceByCode,
  onDuplicatePosition,
  onReuseCode,
  onAddChildPosition,
  onAddSubSection,
  maxNestingDepth = DEFAULT_MAX_NESTING_DEPTH,
  onShowLinks,
  onUnlinkPosition,
  onModelLink,
  onSuggestRate,
  onClassify,
  // onCheckAnomalies is consumed by BOQToolbar, not directly by the grid
  anomalyMap,
  onApplyAnomalySuggestion,
  onSaveAsAssembly,
  customColumns,
  boqVariables,
  bimModelId,
  onHighlightBIMElements,
}, ref) {
  const { t, i18n } = useTranslation();
  // `t` is a fresh function on every render which would invalidate the
  // `columnDefs` useMemo every render and force AG Grid to rebuild its
  // column model (resets sort, width, pinning state). Mirror the latest
  // `t` into a ref and key the memo on the actual language string instead
  // — v4.3 audit (BOQGrid column-defs thrash).
  const tRef = useRef(t);
  tRef.current = t;