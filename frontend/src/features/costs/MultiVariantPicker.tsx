// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
//
// MultiVariantPicker — centered modal that handles a CostItem with MULTIPLE
// independent variant slots in one go.
//
// The single-slot case (one CWICR rate that splits into N alternatives) is
// served by VariantPicker.tsx — a portal popover anchored to a button. That
// flow is fine when there's one decision to make.
//
// The multi-slot case is different. A CWICR row whose components include
// 2+ abstract resources — concrete grade × rebar diameter × formwork type —
// needs the user to make N decisions before the position is meaningful. The
// previous behaviour silently stamped median defaults on every slot and
// hoped the user would discover the per-resource re-pick pills later. They
// often didn't. This modal makes the choice explicit and bulk-fast:
//
//   * One card per variant slot, vertically stacked, always visible.
//   * Each card shows the resource name, unit, qty, and the currently
//     selected variant with delta-vs-mean chip.
//   * Click the card to expand its full variant list inline — compact
//     rows with a radio control, label, unit price, and delta. Only one
//     card expands at a time so the modal height stays bounded.
//   * Bulk action bar at the top: "Median for all", "Mean for all",
//     "Cheapest for all", "Most expensive for all" — one click to seed
//     all slots, then refine individually.
//   * Live subtotal at the bottom: Σ (selected variant price × slot qty).
//   * Apply or Cancel. Cancel falls back to the previous silent-default
//     behaviour (median per slot) so power users aren't slowed down.

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import {
  X,
  Check,
  ChevronDown,
  ChevronRight,
  Layers3,
  Wand2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Button, Badge } from "@/shared/ui";
import { getIntlLocale } from "@/shared/lib/formatters";
import type { CostVariant, VariantStats } from "./api";

/* ── Types ────────────────────────────────────────────────────────────── */

/** One independent variant decision the user has to make for a position.
 *  Slot ids are stable within a position so the parent can route each pick
 *  back to the right `metadata.resources[i]` entry. */
export interface VariantSlot {
  slotId: string;
  name: string;
  unit: string;
  /** Per-unit qty applied to this slot when the position is created.
   *  Multiplied with the chosen variant price for the live subtotal. */
  quantity: number;
  variants: CostVariant[];
  stats: VariantStats;
  currency: string;
}

/** What the user chose for one slot. */
export type SlotPick =
  | { kind: "variant"; variant: CostVariant }
  | { kind: "default"; strategy: "mean" | "median" };

export interface MultiVariantPickerResult {
  /** Map of slotId → pick. Every slot in the input is present here on apply. */
  picks: Record<string, SlotPick>;
  /** When true, the caller should re-use these picks for every remaining
   *  multi-variant item in the batch instead of opening the modal again.
   *  Slot-name matching across items is the caller's responsibility — this
   *  flag just authorises the fast-forward. */
  applyToAll?: boolean;
}

interface MultiVariantPickerProps {
  /** Title shown in the modal header — typically the position description. */
  positionTitle: string;
  /** Two or more slots. The single-slot fast path uses VariantPicker. */
  slots: VariantSlot[];
  /** Optional progress chip ("Item N of M") for batch-add flows where the
   *  modal opens once per cost item. Omit when there's a single position. */
  batchProgress?: { current: number; total: number };
  /** When the user is mid-batch (more multi-variant items waiting after
   *  this one), the modal exposes an "Apply to remaining N items" CTA.
   *  Omit or set to 0 to hide that affordance. */
  remainingCount?: number;
  /** Optional pre-seed when the previous item was applied with
   *  `applyToAll`. Slot-name matched by the caller; used as the initial
   *  picks instead of the default median baseline. */
  suggestedPicks?: Record<string, SlotPick>;
  onApply: (result: MultiVariantPickerResult) => void;
  onCancel: () => void;
}

/* ── Helpers ──────────────────────────────────────────────────────────── */

function formatPrice(value: number, currency: string): string {
  // Currency-style formatting requires an ISO code — when the caller passes
  // an empty string, render the bare number. Never substitute USD/EUR —
  // see CLAUDE.md "no hardcoded currency fallbacks".
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