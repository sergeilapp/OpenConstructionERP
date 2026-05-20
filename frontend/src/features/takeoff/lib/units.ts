/**
 * Frontend unit canonicalization for takeoff → BOQ flows.
 *
 * Mirrors the backend `_UNIT_ALIASES` / `_normalize_unit`
 * (`backend/app/modules/takeoff/service.py`) so quantities pushed into
 * BOQ positions carry the canonical unit vocabulary
 * (`m` / `m2` / `m3` / `kg` / `t` / `pcs` / `lsum`) instead of whatever
 * raw string a PDF table extraction or a German LV produced
 * (`Stück`, `lfm`, `m³`, `psch`, `''`). Downstream BOQ validation,
 * cost matching and bim_hub quantity sync all key on the canonical
 * form, so leaving `Stück` / `lfm` verbatim made those rows invisible
 * to pricing and compliance (D-TKC-021).
 *
 * Keep the alias table in sync with the backend; the backend is the
 * ultimate authority but normalizing client-side gives the user a
 * correct unit immediately and avoids a verbatim round-trip.
 */

/** Case-folded, dot-stripped, whitespace-collapsed alias → canonical. */
const UNIT_ALIASES: Readonly<Record<string, string>> = {
  // Length
  m: "m",
  rmt: "m",
  rm: "m",
  runningmetre: "m",
  runningmeter: "m",
  lm: "m",
  lfm: "m", // German "laufende Meter"
  ml: "m",
  rft: "m",
  // (mm / cm kept distinct — they are real, different units)
  mm: "mm",
  cm: "cm",
  // Area
  m2: "m2",
  "m²": "m2",
  sqm: "m2",
  "sq m": "m2",
  squaremetre: "m2",
  squaremeter: "m2",
  qm: "m2", // German "Quadratmeter"
  sft: "sft",
  sqft: "sft",
  "sq ft": "sft",
  squarefeet: "sft",
  squarefoot: "sft",
  // Volume
  m3: "m3",
  "m³": "m3",
  cum: "m3",
  "cu m": "m3",
  cubicmetre: "m3",
  cubicmeter: "m3",
  cbm: "m3", // German "Kubikmeter"
  cft: "cft",
  cuft: "cft",
  "cu ft": "cft",
  cubicfeet: "cft",
  // Weight
  kg: "kg",
  g: "g",
  t: "t",
  mt: "t",
  to: "t", // German "Tonne"
  tonne: "t",
  ton: "t",
  // Count
  pcs: "pcs",
  pc: "pcs",
  nos: "pcs",
  no: "pcs",
  number: "pcs",
  qty: "pcs",
  ea: "pcs",
  stück: "pcs",
  stk: "pcs", // German "Stück"
  // Lump sum
  lsum: "lsum",
  ls: "lsum",
  lumpsum: "lsum",
  psch: "lsum", // German "pauschal"
  pausch: "lsum",
  pauschal: "lsum",
};

/**
 * Map an arbitrary unit string to the canonical BOQ form.
 *
 * Empty / nullish input → `'pcs'` (matches the backend default — a
 * countable line is the safest neutral assumption). Unknown units pass
 * through lower-cased rather than being rejected: a real-world unit we
 * have not catalogued yet is better surfaced and editable than dropped.
 */
export function canonicalizeUnit(raw: string | null | undefined): string {
  if (raw == null) return "pcs";
  const text = String(raw).trim();
  if (!text) return "pcs";
  const key = text.toLowerCase().replace(/\./g, "").replace(/\s+/g, " ").trim();
  if (key in UNIT_ALIASES) return UNIT_ALIASES[key]!;
  const nospace = key.replace(/ /g, "");
  if (nospace in UNIT_ALIASES) return UNIT_ALIASES[nospace]!;
  return key;
}
