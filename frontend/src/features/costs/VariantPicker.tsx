// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
//
// VariantPicker — portal popover that lets the user choose one of N
// CWICR abstract-resource price variants when applying a cost item to a
// BOQ position.
//
// v2.6.24 redesign — when CWICR variants carry long descriptive labels
// ("Ready-mix concrete C30/37, 32mm agg, S3 slump, supplier: ..."), a
// single-line truncated row was unreadable. The picker now:
//
//   * widens to 520 px (max-w 92vw on small screens) so two-line labels fit;
//   * shows the FULL label, wrapped, with a clamp at 3 lines + tooltip;
//   * surfaces a delta-vs-mean chip per row so the user can see how each
//     variant deviates from the average at a glance;
//   * adds a search input (visible when ≥ 6 variants) to narrow by keyword;
//   * adds a sort dropdown (default / price asc / price desc / label).
//
// Keyboard / portal behaviour preserved from the original implementation:
//   * portal-rendered into `document.body` so AG Grid clipping cannot hide it;
//   * anchored to a DOM element (typically the row's Add button);
//   * Esc / outside-click / explicit close all call `onClose()`;
//   * Apply does NOT auto-close — parent owns the close lifecycle so it
//     can sequence multiple pickers in a multi-select flow.

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import {
  X,
  Search,
  ArrowUpDown,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Badge, Button, KvList, Kv, QtyTile } from "@/shared/ui";
import { getIntlLocale } from "@/shared/lib/formatters";
import type { CostVariant, VariantStats } from "./api";

/* ── Props ────────────────────────────────────────────────────────────── */

export interface VariantPickerProps {
  variants: CostVariant[];
  stats: VariantStats;
  /** Pre-selected row.  When omitted, the row whose price matches
   *  `stats[defaultStrategy]` is preferred; otherwise `floor(len/2)`. */
  defaultIndex?: number;
  /** Which `VariantStats` field drives the auto-default.  `"mean"` is the
   *  production default for new applies (matches CostX/iTWO behaviour);
   *  `"median"` is kept for the legacy panel that tags the median row in
   *  the cost-DB browser. */
  defaultStrategy?: "mean" | "median";
  /** Anchor element used to position the popover.  When `null`, the
   *  popover renders centered on screen as a graceful fallback. */
  anchorEl: HTMLElement | null;
  unitLabel: string;
  currency: string;
  onApply: (chosen: CostVariant) => void;
  /** Optional one-click "use average" path — when supplied, the picker
   *  surfaces an extra footer button that applies the mean rate without
   *  forcing the user to pick a row.  The argument is the strategy that
   *  was honoured (passed up so the parent can stamp `variant_default`). */
  onUseDefault?: (strategy: "mean" | "median") => void;
  onClose: () => void;
}

type SortMode = "default" | "price_asc" | "price_desc" | "label";

/* ── Helpers ──────────────────────────────────────────────────────────── */

/** Format a price in the given currency using the active i18n locale. */
function formatPrice(value: number, currency: string): string {
  // Currency-style formatting requires an ISO code — when the caller passes
  // an empty string (no project currency context, no per-row currency in the
  // CWICR row), skip the currency style entirely and render the bare number.
  // Never substitute USD/EUR — see CLAUDE.md "no hardcoded currency fallbacks".
  if (!currency) {
    return new Intl.NumberFormat(getIntlLocale(), {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }
  try {
    return new Intl.NumberFormat(getIntlLocale(), {
      style: 'currency',
      currency,