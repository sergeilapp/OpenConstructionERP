import { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, Truck, X } from 'lucide-react';
import { Button } from '@/shared/ui';
import type {
  BedrockTruckApplyResponse,
  BedrockTruckBillingType,
  BedrockTruckOptionPreview,
  BedrockTruckPreviewRequest,
  BedrockTruckPreviewResponse,
  BedrockTruckQuantityUnit,
} from './api';

const DEFAULT_TRUCKS = [
  { kind: 'Single Axle', volume_capacity: 3, weight_capacity: 6, cost_per_hour: 115, cost_per_mile: 4, miles_per_gallon: 4 },
  { kind: 'Dual Axle', volume_capacity: 13, weight_capacity: 16, cost_per_hour: 125, cost_per_mile: 4.5, miles_per_gallon: 4 },
  { kind: 'Tri Axle', volume_capacity: 20, weight_capacity: 23, cost_per_hour: 135, cost_per_mile: 5, miles_per_gallon: 4 },
];

interface Props {
  boqId: string;
  preview: (data: BedrockTruckPreviewRequest) => Promise<BedrockTruckPreviewResponse>;
  apply: (data: { request: BedrockTruckPreviewRequest; selectedTruckType: string }) => Promise<BedrockTruckApplyResponse>;
  onClose: () => void;
}

export function BedrockTruckCalculatorPanel({ boqId, preview, apply, onClose }: Props) {
  const [materialQuantity, setMaterialQuantity] = useState('1956');
  const [quantityUnit, setQuantityUnit] = useState<BedrockTruckQuantityUnit>('CY');
  const [materialName, setMaterialName] = useState('Aggregate material');
  const [materialUnitCost, setMaterialUnitCost] = useState('0');
  const [quarryDistance, setQuarryDistance] = useState('9');
  const [billingType, setBillingType] = useState<BedrockTruckBillingType>('hour');
  const [truckCostPerLoad, setTruckCostPerLoad] = useState('');
  const [fuelCostPerGallon, setFuelCostPerGallon] = useState('6.50');
  const [speedMph, setSpeedMph] = useState('60');
  const [timeAtQuarry, setTimeAtQuarry] = useState('30');
  const [timeAtJobSite, setTimeAtJobSite] = useState('15');
  const [drivingLaborRate, setDrivingLaborRate] = useState('95');
  const [drivingLaborerCount, setDrivingLaborerCount] = useState('1');
  const [selectedTruckType, setSelectedTruckType] = useState('Tri Axle');
  const [result, setResult] = useState<BedrockTruckPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  const request = useMemo<BedrockTruckPreviewRequest>(() => ({
    material_quantity: materialQuantity || '0',
    quantity_unit: quantityUnit,
    material_name: materialName || 'Material',
    material_unit_cost: materialUnitCost || '0',
    quarry_distance: quarryDistance || '0',
    billing_type: billingType,
    truck_options: DEFAULT_TRUCKS,
    truck_cost_per_load: billingType === 'load' ? truckCostPerLoad || null : null,
    truck_cost_classification: 'haul_only',
    fuel_cost_per_gallon: billingType === 'mile' ? fuelCostPerGallon || null : null,
    speed_mph: speedMph || '60',
    time_at_quarry_minutes: timeAtQuarry || '0',
    time_at_job_site_minutes: timeAtJobSite || '0',
    driving_labor_rate: drivingLaborRate || null,
    driving_laborer_count: drivingLaborerCount || '0',
  }), [billingType, drivingLaborRate, drivingLaborerCount, fuelCostPerGallon, materialName, materialQuantity, materialUnitCost, quantityUnit, quarryDistance, speedMph, timeAtJobSite, timeAtQuarry, truckCostPerLoad]);

  const selected = result?.options.find((option) => option.truck_type === selectedTruckType) ?? null;

  const runPreview = async () => {
    setError(null);
    setIsPreviewing(true);
    try {
      const next = await preview(request);
      setResult(next);
      if (!next.options.some((option) => option.truck_type === selectedTruckType)) {
        setSelectedTruckType(next.options[0]?.truck_type ?? selectedTruckType);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preview failed');
    } finally {
      setIsPreviewing(false);
    }
  };

  const applySelected = async () => {
    if (!selected) return;
    setError(null);
    setIsApplying(true);
    try {
      await apply({ request, selectedTruckType: selected.truck_type });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Apply failed');
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <section className="mb-3 rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-4 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-amber-800">
            <Truck size={18} /> Bedrock Truck / Hauling Calculator
          </div>
          <p className="mt-1 max-w-3xl text-sm text-content-secondary">
            Preview familiar Bedrock hauling assumptions, compare truck options, then apply the selected haul line into this BOQ.
          </p>
        </div>
        <button type="button" onClick={onClose} className="rounded-full p-1.5 text-content-tertiary hover:bg-white hover:text-content-primary" aria-label="Close Bedrock calculator">
          <X size={18} />
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-4 lg:grid-cols-8">
        <label className="text-xs font-medium text-content-secondary md:col-span-2">
          Material
          <input value={materialName} onChange={(e) => setMaterialName(e.target.value)} className="mt-1 h-9 w-full rounded-md border border-border-light bg-white px-2 text-sm" />
        </label>
        <Field label="Quantity" value={materialQuantity} onChange={setMaterialQuantity} />
        <label className="text-xs font-medium text-content-secondary">
          Unit
          <select value={quantityUnit} onChange={(e) => setQuantityUnit(e.target.value as BedrockTruckQuantityUnit)} className="mt-1 h-9 w-full rounded-md border border-border-light bg-white px-2 text-sm">
            <option value="CY">CY</option>
            <option value="ton">ton</option>
            <option value="load">load</option>
          </select>
        </label>
        <Field label="Material $/unit" value={materialUnitCost} onChange={setMaterialUnitCost} />
        <Field label="Quarry mi" value={quarryDistance} onChange={setQuarryDistance} />
        <label className="text-xs font-medium text-content-secondary">
          Billing
          <select value={billingType} onChange={(e) => setBillingType(e.target.value as BedrockTruckBillingType)} className="mt-1 h-9 w-full rounded-md border border-border-light bg-white px-2 text-sm">
            <option value="load">load</option>
            <option value="hour">hour</option>
            <option value="mile">mile</option>
          </select>
        </label>
        <Field label="Haul $/load" value={truckCostPerLoad} onChange={setTruckCostPerLoad} disabled={billingType !== 'load'} />
        <Field label="Fuel $/gal" value={fuelCostPerGallon} onChange={setFuelCostPerGallon} disabled={billingType !== 'mile'} />
        <Field label="Speed mph" value={speedMph} onChange={setSpeedMph} />
        <Field label="Quarry min" value={timeAtQuarry} onChange={setTimeAtQuarry} />
        <Field label="Site min" value={timeAtJobSite} onChange={setTimeAtJobSite} />
        <Field label="Driver $/hr" value={drivingLaborRate} onChange={setDrivingLaborRate} />
        <Field label="Drivers" value={drivingLaborerCount} onChange={setDrivingLaborerCount} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button variant="primary" size="sm" onClick={runPreview} disabled={isPreviewing} icon={isPreviewing ? <Loader2 size={15} className="animate-spin" /> : <Truck size={15} />}>
          Preview trucks
        </Button>
        <Button variant="secondary" size="sm" onClick={applySelected} disabled={!selected || isApplying} icon={isApplying ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}>
          Apply selected to BOQ
        </Button>
        <span className="text-xs text-content-tertiary">BOQ {boqId.slice(0, 8)}</span>
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      {result && (
        <div className="mt-4 overflow-x-auto rounded-xl border border-border-light bg-white">
          <table className="min-w-full divide-y divide-border-light text-sm">
            <thead className="bg-surface-secondary text-xs uppercase tracking-wide text-content-secondary">
              <tr>
                <th className="px-3 py-2 text-left">Select</th>
                <th className="px-3 py-2 text-left">Truck</th>
                <th className="px-3 py-2 text-right">Capacity</th>
                <th className="px-3 py-2 text-right">Loads</th>
                <th className="px-3 py-2 text-right">Miles</th>
                <th className="px-3 py-2 text-right">Hours</th>
                <th className="px-3 py-2 text-right">Truck cost</th>
                <th className="px-3 py-2 text-right">Labor</th>
                <th className="px-3 py-2 text-right">Material</th>
                <th className="px-3 py-2 text-right">Total</th>
                <th className="px-3 py-2 text-left">Flags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-light">
              {result.options.map((option) => (
                <PreviewRow key={option.truck_type} option={option} selected={selectedTruckType === option.truck_type} onSelect={() => setSelectedTruckType(option.truck_type)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Field({ label, value, onChange, disabled }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean }) {
  return (
    <label className="text-xs font-medium text-content-secondary">
      {label}
      <input value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} inputMode="decimal" className="mt-1 h-9 w-full rounded-md border border-border-light bg-white px-2 text-sm disabled:bg-surface-secondary disabled:text-content-tertiary" />
    </label>
  );
}

function PreviewRow({ option, selected, onSelect }: { option: BedrockTruckOptionPreview; selected: boolean; onSelect: () => void }) {
  const blocking = option.review_flags.some((flag) => flag.severity === 'error');
  return (
    <tr className={selected ? 'bg-amber-50' : undefined}>
      <td className="px-3 py-2"><input type="radio" checked={selected} onChange={onSelect} /></td>
      <td className="px-3 py-2 font-medium text-content-primary">{option.truck_type}</td>
      <td className="px-3 py-2 text-right tabular-nums">{option.truck_capacity} {option.truck_capacity_unit}</td>
      <td className="px-3 py-2 text-right tabular-nums">{option.loads}</td>
      <td className="px-3 py-2 text-right tabular-nums">{option.round_trip_distance_miles}</td>
      <td className="px-3 py-2 text-right tabular-nums">{option.total_hours}</td>
      <td className="px-3 py-2 text-right tabular-nums">{option.truck_cost ?? '-'}</td>
      <td className="px-3 py-2 text-right tabular-nums">{option.driving_labor_cost ?? '-'}</td>
      <td className="px-3 py-2 text-right tabular-nums">{option.material_cost ?? '-'}</td>
      <td className="px-3 py-2 text-right font-semibold tabular-nums">{option.total_cost ?? '-'}</td>
      <td className="px-3 py-2 text-xs text-content-secondary">
        {option.review_flags.length === 0 ? 'Clear' : option.review_flags.map((flag) => flag.code).join(', ')}
        {blocking && <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-red-700">blocked</span>}
      </td>
    </tr>
  );
}
