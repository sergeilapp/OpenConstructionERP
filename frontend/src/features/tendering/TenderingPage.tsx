import { useState, useMemo, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Package,
  Plus,
  ChevronDown,
  ChevronRight,
  Send,
  Award,
  BarChart3,
  Clock,
  Mail,
  Building2,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Download,
  FileText,
  AlertTriangle,
} from "lucide-react";
import {
  Button,
  Card,
  Badge,
  EmptyState,
  Skeleton,
  InfoHint,
  SkeletonTable,
  Breadcrumb,
  ConfirmDialog,
} from "@/shared/ui";
import {
  WideModal,
  WideModalSection,
  WideModalField,
} from "@/shared/ui/WideModal";
import { useConfirm } from "@/shared/hooks/useConfirm";
import { apiGet, apiPost, apiPatch } from "@/shared/lib/api";
import { useToastStore } from "@/stores/useToastStore";
import { useProjectContextStore } from "@/stores/useProjectContextStore";
import { BidComparisonChart } from "./BidComparisonChart";
import { AddendumList } from "./AddendumList";
import { LevelingMatrix } from "./LevelingMatrix";
import { getIntlLocale } from "@/shared/lib/formatters";

/* ── Types ─────────────────────────────────────────────────────────────── */

interface Project {
  id: string;
  name: string;
  description: string;
  currency: string;
}

interface BOQ {
  id: string;
  project_id: string;
  name: string;
  description: string;
  status: string;
}

interface BidData {
  id: string;
  package_id: string;
  company_name: string;
  contact_email: string;
  total_amount: string;
  currency: string;
  submitted_at: string | null;
  status: string;
  notes: string;
  line_items: LineItem[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface LineItem {
  position_id?: string;
  description: string;
  unit: string;
  quantity: number;
  unit_rate: number;
  total: number;
}

interface TenderPackage {
  id: string;
  project_id: string;
  boq_id: string;
  name: string;
  description: string;
  status: string;
  deadline: string | null;
  metadata: Record<string, unknown>;
  bid_count: number;
  created_at: string;
  updated_at: string;
}

interface PackageWithBids extends TenderPackage {
  bids: BidData[];
}

interface BidComparisonRow {
  position_id: string | null;
  description: string;
  unit: string;
  budget_quantity: number;
  budget_rate: number;
  budget_total: number;
  bids: {
    company_name: string;
    bid_id: string;
    unit_rate: number;
    total: number;
    deviation_pct: number;
  }[];
}

interface BidComparison {
  package_id: string;
  package_name: string;
  bid_count: number;
  bid_companies: string[];
  budget_total: number;
  rows: BidComparisonRow[];
  bid_totals: {
    bid_id: string;
    company_name: string;
    total: number;
    currency: string;
    deviation_pct: number;
    status: string;
  }[];
}

/* ── Helpers ───────────────────────────────────────────────────────────── */

const STATUS_COLORS: Record<
  string,
  "neutral" | "blue" | "success" | "warning" | "error"
> = {
  draft: "neutral",
  issued: "blue",
  collecting: "blue",
  evaluating: "warning",
  awarded: "success",
  closed: "neutral",
  pending: "neutral",
  submitted: "blue",
  accepted: "success",
  rejected: "error",
};

function formatCurrency(amount: number | string, currency?: string): string {
  const num = typeof amount === "string" ? parseFloat(amount) || 0 : amount;
  const code = (currency || "").trim().toUpperCase();
  // NEVER hard-fallback to EUR (task #217): a project priced in BRL/INR
  // must not render its tender amounts with a Euro sign. When the currency
  // is unknown, show a plain decimal number with no symbol.
  if (!/^[A-Z]{3}$/.test(code)) {
    return new Intl.NumberFormat(getIntlLocale(), {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num);
  }
  try {
    return new Intl.NumberFormat(getIntlLocale(), {
      style: "currency",
      currency: code,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num);
  } catch {
    return `${num.toFixed(0)} ${code}`;
  }
}

function formatNumber(n: number, decimals: number = 2): string {
  return new Intl.NumberFormat(getIntlLocale(), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function DeviationBadge({ pct }: { pct: number }) {
  if (Math.abs(pct) < 0.1) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-content-tertiary">
        <Minus size={10} /> 0%
      </span>
    );
  }
  if (pct < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-semantic-success">
        <ArrowDownRight size={12} /> {pct.toFixed(1)}%
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-medium text-semantic-error">
      <ArrowUpRight size={12} /> +{pct.toFixed(1)}%
    </span>
  );
}

function translateStatus(
  status: string,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  const STATUS_I18N: Record<string, string> = {
    draft: t("tendering.status_draft", "Draft"),
    issued: t("tendering.status_issued", "Issued"),
    collecting: t("tendering.status_collecting", "Collecting"),
    evaluating: t("tendering.status_evaluating", "Evaluating"),
    awarded: t("tendering.status_awarded", "Awarded"),
    closed: t("tendering.status_closed", "Closed"),
    pending: t("tendering.status_pending", "Pending"),
    submitted: t("tendering.status_submitted", "Submitted"),
    accepted: t("tendering.status_accepted", "Accepted"),
    rejected: t("tendering.status_rejected", "Rejected"),
  };
  return STATUS_I18N[status] || status;
}

function formatDate(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat(getIntlLocale(), {
      dateStyle: "medium",
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

/* ── Select Dropdown ──────────────────────────────────────────────────── */

function SelectDropdown({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`h-10 w-full rounded-lg border border-border bg-surface-primary px-3 text-sm transition-all duration-normal ease-oe focus:outline-none focus:ring-2 focus:ring-oe-blue/30 focus:border-oe-blue hover:border-content-tertiary ${
        !value ? "text-content-tertiary" : "text-content-primary"
      }`}
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

/* ── Create Package Dialog ────────────────────────────────────────────── */

function CreatePackageDialog({
  projectId,
  boqs,
  onClose,
  onCreated,
}: {
  projectId: string;
  boqs: BOQ[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [boqId, setBoqId] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");

  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const createMutation = useMutation({
    mutationFn: () =>
      apiPost<TenderPackage>("/v1/tendering/packages/", {
        project_id: projectId,
        boq_id: boqId,
        name,
        description,
        deadline: deadline || null,
      }),
    onSuccess: () => {
      onCreated();
      onClose();
      addToast({
        type: "success",
        title: t("toasts.package_created", {
          defaultValue: "Tender package created‌⁠‍",
        }),
      });
    },
    onError: (error: Error) => {
      addToast({
        type: "error",
        title: t("toasts.error", { defaultValue: "Error" }),
        message: error.message,
      });
    },
  });

  const fieldCls =
    "h-10 w-full rounded-lg border border-border bg-surface-primary px-3 text-sm text-content-primary placeholder:text-content-tertiary transition-all focus:outline-none focus:ring-2 focus:ring-oe-blue/30 focus:border-oe-blue";

  return (
    <WideModal
      open
      onClose={onClose}
      title={t("tendering.new_package", "New Tender Package")}
      size="lg"
      busy={createMutation.isPending}
      footer={
        <>
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={createMutation.isPending}
          >
            {t("common.cancel", "Cancel")}
          </Button>
          <Button
            variant="primary"
            disabled={!name.trim() || !boqId}
            loading={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {t("tendering.create_package", "Create Package")}
          </Button>
        </>
      }
    >
      <WideModalSection columns={2}>
        <WideModalField
          label={t("tendering.package_name", "Package Name")}
          required
          span={2}
        >
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t(
              "tendering.package_name_placeholder",
              "e.g. Concrete Works Package",
            )}
            className={fieldCls}
          />
        </WideModalField>
        <WideModalField
          label={t("tendering.source_boq", "Source BOQ")}
          required
        >
          <SelectDropdown
            value={boqId}
            onChange={setBoqId}
            options={boqs.map((b) => ({ value: b.id, label: b.name }))}
            placeholder={t("tendering.select_boq", "Select a BOQ...")}
          />
        </WideModalField>
        <WideModalField label={t("tendering.deadline", "Deadline")}>
          <input
            type="date"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className={fieldCls}
          />
        </WideModalField>
        <WideModalField
          label={t("tendering.description", "Description")}
          span={2}
        >
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-border bg-surface-primary px-3 py-2 text-sm text-content-primary placeholder:text-content-tertiary transition-all focus:outline-none focus:ring-2 focus:ring-oe-blue/30 focus:border-oe-blue resize-none"
            placeholder={t(
              "tendering.description_placeholder",
              "Brief description of the package scope...",
            )}
          />
        </WideModalField>
      </WideModalSection>
    </WideModal>
  );
}

/* ── Add Bid Dialog ───────────────────────────────────────────────────── */

function AddBidDialog({
  packageId,
  currency,
  onClose,
  onCreated,
}: {
  packageId: string;
  currency: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const addToast = useToastStore((s) => s.addToast);
  const [companyName, setCompanyName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [totalAmount, setTotalAmount] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const createMutation = useMutation({
    mutationFn: () =>
      apiPost<BidData>(`/v1/tendering/packages/${packageId}/bids/`, {
        company_name: companyName,
        contact_email: contactEmail,
        total_amount: totalAmount || "0",
        currency,
        submitted_at: new Date().toISOString().slice(0, 10),
        status: "submitted",
        notes,
      }),
    onSuccess: () => {
      onCreated();
      onClose();
      addToast({
        type: "success",
        title: t("toasts.bid_submitted", { defaultValue: "Bid submitted‌⁠‍" }),
      });
    },
    onError: (error: Error) => {
      addToast({
        type: "error",
        title: t("toasts.error", { defaultValue: "Error" }),
        message: error.message,
      });
    },
  });

  const fieldCls =
    "h-10 w-full rounded-lg border border-border bg-surface-primary px-3 text-sm text-content-primary placeholder:text-content-tertiary transition-all focus:outline-none focus:ring-2 focus:ring-oe-blue/30 focus:border-oe-blue";

  return (
    <WideModal
      open
      onClose={onClose}
      title={t("tendering.add_bid", "Add Bid")}
      size="lg"
      busy={createMutation.isPending}
      footer={
        <>
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={createMutation.isPending}
          >
            {t("common.cancel", "Cancel")}
          </Button>
          <Button
            variant="primary"
            disabled={!companyName.trim()}
            loading={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {t("tendering.submit_bid", "Submit Bid")}
          </Button>
        </>
      }
    >
      <WideModalSection columns={2}>
        <WideModalField
          label={t("tendering.company_name", "Company Name")}
          required
          span={2}
        >
          <input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder={t(
              "tendering.company_placeholder",
              "e.g. Schmidt Bau GmbH",
            )}
            className={fieldCls}
          />
        </WideModalField>
        <WideModalField label={t("tendering.contact_email", "Contact Email")}>
          <input
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            placeholder="contact@example.com"
            className={fieldCls}
          />
        </WideModalField>
        <WideModalField
          label={
            currency
              ? `${t("tendering.total_amount", "Total Amount")} (${currency})`
              : t("tendering.total_amount", "Total Amount")
          }
        >
          <input
            type="number"
            value={totalAmount}
            onChange={(e) => setTotalAmount(e.target.value)}
            placeholder="0"
            className={fieldCls}
          />
        </WideModalField>
        <WideModalField label={t("tendering.notes", "Notes")} span={2}>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-border bg-surface-primary px-3 py-2 text-sm text-content-primary placeholder:text-content-tertiary transition-all focus:outline-none focus:ring-2 focus:ring-oe-blue/30 focus:border-oe-blue resize-none"
            placeholder={t("tendering.notes_placeholder", "Optional notes...")}
          />
        </WideModalField>
      </WideModalSection>
    </WideModal>
  );
}

/* ── Package Card ─────────────────────────────────────────────────────── */

function PackageCard({
  pkg,
  isSelected,
  onClick,
}: {
  pkg: TenderPackage;
  isSelected: boolean;
  onClick: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Card
      hoverable
      padding="none"
      className={`cursor-pointer transition-all ${
        isSelected ? "ring-2 ring-oe-blue/40 border-oe-blue/40" : ""
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3 px-5 py-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-oe-blue-subtle text-oe-blue">
          <Package size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-content-primary truncate">
            {pkg.name}
          </h3>
          <div className="mt-0.5 flex items-center gap-3 text-xs text-content-secondary">
            <span className="flex items-center gap-1">
              <FileText size={12} />
              {t("tendering.bid_count", {
                defaultValue: "{{count}} bids‌⁠‍",
                count: pkg.bid_count,
              })}
            </span>
            {pkg.deadline && (
              <span className="flex items-center gap-1">
                <Clock size={12} />
                {formatDate(pkg.deadline)}
              </span>
            )}
          </div>
        </div>
        <Badge variant={STATUS_COLORS[pkg.status] || "neutral"} size="sm">
          {translateStatus(pkg.status, t)}
        </Badge>
        <span className="text-content-tertiary">
          {isSelected ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>
      </div>
    </Card>
  );
}

/* ── Bid Comparison Table ─────────────────────────────────────────────── */

function BidComparisonTable({
  comparison,
  currency,
}: {
  comparison: BidComparison;
  currency: string;
}) {
  const { t } = useTranslation();
  const [hideLowVariance, setHideLowVariance] = useState(false);
  const [varianceThreshold, setVarianceThreshold] = useState(5);

  const visibleRows = useMemo(() => {
    if (!hideLowVariance) return comparison.rows;
    return comparison.rows.filter((row) => {
      const rates = row.bids.map((b) => b.unit_rate).filter((r) => r > 0);
      if (rates.length < 2) return true;
      const mean = rates.reduce((s, r) => s + r, 0) / rates.length;
      if (mean === 0) return true;
      const min = Math.min(...rates);
      const max = Math.max(...rates);
      const spreadPct = ((max - min) / mean) * 100;
      return spreadPct > varianceThreshold;
    });
  }, [comparison.rows, hideLowVariance, varianceThreshold]);

  if (comparison.bid_count === 0) {
    return (
      <EmptyState
        icon={<BarChart3 size={28} strokeWidth={1.5} />}
        title={t("tendering.no_bids_yet", "No bids yet")}
        description={t(
          "tendering.no_bids_description",
          "Add bids to see a side-by-side comparison.",
        )}
      />
    );
  }

  const stickyColClass =
    "sticky left-0 z-10 bg-surface-primary shadow-[2px_0_3px_-2px_rgba(0,0,0,0.1)]";
  const hiddenCount = comparison.rows.length - visibleRows.length;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-end gap-3 text-xs">
        <label className="inline-flex items-center gap-2 text-content-secondary cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hideLowVariance}
            onChange={(e) => setHideLowVariance(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-border text-oe-blue focus:ring-oe-blue/30"
          />
          {t(
            "tendering.compare.collapseLowVariance",
            "Hide low-variance positions",
          )}
        </label>
        <label
          className={`inline-flex items-center gap-2 transition-opacity ${
            hideLowVariance
              ? "text-content-secondary"
              : "text-content-tertiary opacity-60"
          }`}
        >
          <span>
            {t("tendering.compare.varianceThreshold", "Variance threshold")}
          </span>
          <select
            value={varianceThreshold}
            onChange={(e) => setVarianceThreshold(Number(e.target.value))}
            disabled={!hideLowVariance}
            className="h-7 rounded border border-border bg-surface-primary px-1.5 text-xs text-content-primary focus:outline-none focus:ring-2 focus:ring-oe-blue/30 disabled:cursor-not-allowed"
          >
            <option value={5}>5%</option>
            <option value={10}>10%</option>
            <option value={15}>15%</option>
            <option value={20}>20%</option>
            <option value={25}>25%</option>
          </select>
        </label>
        {hideLowVariance && hiddenCount > 0 && (
          <span className="text-content-tertiary">
            {t("tendering.compare.hiddenCount", {
              defaultValue: "{{count}} hidden",
              count: hiddenCount,
            })}
          </span>
        )}
      </div>
      <div className="overflow-x-auto relative">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-surface-primary">
            <tr className="border-b border-border-light">
              <th
                className={`whitespace-nowrap px-3 py-2.5 text-left font-semibold text-content-primary ${stickyColClass} z-20`}
              >
                {t("tendering.position", "Position")}
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 text-right font-semibold text-content-primary">
                {t("tendering.budget", "Budget")}
              </th>
              {comparison.bid_companies.map((company) => (
                <th
                  key={company}
                  className="whitespace-nowrap px-3 py-2.5 text-right font-semibold text-content-primary"
                >
                  <span className="flex items-center justify-end gap-1.5">
                    <Building2 size={12} className="text-content-tertiary" />
                    {company}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, idx) => (
              <tr
                key={`${row.description}-${row.unit}-${idx}`}
                className="group border-b border-border-light/50 transition-colors hover:bg-surface-secondary/30"
              >
                <td
                  className={`px-3 py-2.5 ${stickyColClass} z-20 group-hover:bg-surface-secondary/30`}
                >
                  <span className="text-content-primary">
                    {row.description || "-"}
                  </span>
                  <span className="ml-2 text-xs text-content-tertiary">
                    {row.unit}
                  </span>