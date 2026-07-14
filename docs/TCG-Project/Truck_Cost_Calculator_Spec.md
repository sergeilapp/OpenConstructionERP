# Truck Cost Calculator Spec

Status: Active

Source system: Bedrock Rails app (`app-bedrock`)

Target context: OCERP estimate/material calculator migration

## Purpose

This spec captures the truck cost calculator logic used by Bedrock's estimate calculators and site preparation material editor. The visible UI table is a preview/comparison grid that evaluates all current dump truck types for the current material quantity, quarry distance, and billing method.

The saved estimate cost uses the same core distance, hours, and cost formulas, but only for the selected truck type and persisted load count.

## Source References

- UI table markup and JavaScript: `app-bedrock/app/views/site_preparation_materials/_dump_truck_table.html.erb`
- Materials editor integration: `app-bedrock/app/views/site_preparation_materials/_form.html.erb`
- Job calculator integration: `app-bedrock/app/views/jobs/_form.html.erb`
- Material server-side calculator: `app-bedrock/app/models/material_calculator.rb`
- Job-level fill dirt calculators:
- `app-bedrock/app/models/site_preparation_job_calculator.rb`
- `app-bedrock/app/models/rock_pad_calculator.rb`
- `app-bedrock/app/models/concrete_job_calculator.rb`
- Effective-dated variable lookup: `app-bedrock/app/models/rock_pad_variable.rb`

## Shared UI Table Locations

The same partial renders in both contexts:

- Materials editor: `site_preparation_materials/_form.html.erb` renders `site_preparation_materials/dump_truck_table`.
- Job calculators: `jobs/_form.html.erb` renders `site_preparation_materials/dump_truck_table`.

## Data Dependencies

### Truck Types

The table loads the current effective row for each truck `kind` from `dump_truck_types`, ordered by `weight_capacity ASC`.

Required fields:

- `kind`: display label, for example `Single Axle`, `Dual Axle`, `Tri Axle`
- `weight_capacity`: capacity in tons
- `volume_capacity`: capacity in cubic yards
- `cost_per_hour`: hourly truck cost
- `cost_per_mile`: maintenance/operating cost per mile
- `miles_per_gallon`: fuel efficiency
- `effective_at`: effective date

Current-effective selection rule:

```text
For each truck kind, use the row with max(effective_at) where effective_at <= calculation_date.
```

### Billing Types

The calculator supports three billing modes from `dump_truck_billing_types.description`:

- `hour`
- `mile`
- `load`

Comparison is case-insensitive.

### Runtime Variables

The table reads these effective-dated values from `rock_pad_variables`:

- `speed_for_hour_calculation`: average truck speed in miles per hour
- `gas_cost`: fuel cost per gallon
- `dump_truck_time_at_quarry`: loading/wait time at quarry in minutes per load
- `dump_truck_time_at_job_site`: unloading/wait time at job site in minutes per load

Current-effective selection rule:

```text
Use the row with max(effective_at) for the variable key where effective_at <= calculation_date.
```

## Inputs

### Material Editor Inputs

- `material_volume`: `site_preparation_material.volume`, cubic yards
- `material_weight`: `site_preparation_material.weight`, tons
- `quarry_distance`: `site_preparation_material.quarry_distance`, one-way miles
- `dump_truck_billing_type_id`: selected billing type
- `truck_cost_per_load`: entered dollars per load, required only for load billing
- `measurement_unit_id`: selected preparation material's measurement unit

### Job Calculator Inputs

- `material_volume`: `job.excavation_volume`, cubic yards
- `material_weight`: not used by the job-level call; passed as `0`
- `quarry_distance`: `job.quarry_distance`, one-way miles
- `dump_truck_billing_type_id`: selected billing type
- `truck_cost_per_load`: entered dollars per load, required only for load billing
- `measurement_unit_id`: defaults to volume in the shared table call

## Measurement Unit Selection

The table decides whether to calculate load count by weight or volume.

```text
if measurement_unit_id == 1:
  calculated_by = "Weight"
  loads = ceil(material_weight / truck.weight_capacity)
  truck_capacity_label = "{truck.weight_capacity} tons"
else:
  calculated_by = "Volume"
  loads = ceil(material_volume / truck.volume_capacity)
  truck_capacity_label = "{truck.volume_capacity} yds"
```

Notes:

- Bedrock treats `measurement_unit_id == 1` as weight.
- All other measurement units use volume.
- The UI table computes loads independently for every truck type.

## Core Formulas

For each truck type:

```text
loads = ceil(material_quantity / truck_capacity)
```

```text
total_distance = quarry_distance * loads * 2
```

`quarry_distance` is one-way. The `* 2` converts each load to a round trip.

```text
handling_hours_per_load =
  (dump_truck_time_at_quarry / 60) +
  (dump_truck_time_at_job_site / 60)
```

```text
total_hours =
  (total_distance / speed_for_hour_calculation) +
  (loads * handling_hours_per_load)
```

## Cost Formulas

### Billing by Hour

```text
cost = round(total_hours * truck.cost_per_hour)
```

### Billing by Mile

```text
gas_total = (gas_cost / truck.miles_per_gallon) * total_distance
maintenance_total = truck.cost_per_mile * total_distance
cost = round(gas_total + maintenance_total)
```

### Billing by Load

```text
cost = truck_cost_per_load * loads
```

## Display Rounding

The UI table displays:

- `loads`: integer from `ceil(...)`
- `distance`: `round(total_distance)`
- `hours`: `total_hours` with two decimal places
- `cost`: `$` plus calculated cost

Hourly and mileage costs are rounded to the nearest whole dollar. Load-based costs are not explicitly rounded in the UI because they are an integer multiplication in the source app.

## Saved Estimate Behavior

The preview table compares all truck types. Saved estimate calculations do not recalculate every truck option. They use persisted selections and fields.

For site preparation materials, the persisted fields are on `site_preparation_materials`:

- `volume`
- `weight`
- `quarry_distance`
- `truck_loads`
- `dump_truck_type_id`
- `dump_truck_billing_type_id`
- `truck_cost_per_load`

Server-side formulas mirror the UI table:

```text
total_distance = quarry_distance * truck_loads * 2
```

```text
driving_hours =
  (total_distance / speed_for_hour_calculation) +
  (truck_loads * handling_hours_per_load)
```

```text
if billing_type includes "hour":
  truck_cost_cents = truck.cost_per_hour * driving_hours * 100

if billing_type includes "mile":
  truck_cost_cents = truck_gas_cost + truck_maintenance_cost

if billing_type includes "load":
  truck_cost_cents = truck_loads * truck_cost_per_load * 100
```

For job-level fill dirt, equivalent persisted fields live on `jobs`:

- `excavation_volume`
- `quarry_distance`
- `dump_truck_loads`
- `dump_truck_type_id`
- `dump_truck_billing_type_id`
- `truck_cost_per_load`

## Validation Rules

When billing type is `load`, `truck_cost_per_load` is required.

Bedrock enforces this in:

- `SitePreparationMaterial#truck_cost_per_load_required`
- `Job#truck_cost_per_load_required`

Recommended OCERP behavior:

```text
if billing_type == "load" and truck_cost_per_load is blank:
  reject save or mark calculation invalid
```

## Worked Example From Bedrock UI

Copied table:

```text
Calculated by: Volume

Truck Type         Single Axle   Dual Axle   Tri Axle
Truck Capacity    3 yds         13 yds      20 yds
# loads           652           151         98
Distance          11736         2718        1764
Hours             912.80        211.40      137.20
Cost              $257540       $59645      $38710
```

Implied inputs:

```text
material_volume = 1956 yd3
quarry_distance = 9 miles one-way
speed_for_hour_calculation = 60 mph
handling_hours_per_load = 1.1 hours
truck_cost_per_load = $395
billing_type = load
```

The handling time implies:

```text
dump_truck_time_at_quarry + dump_truck_time_at_job_site = 66 minutes
```

Tri Axle calculation:

```text
loads = ceil(1956 / 20) = 98
distance = 9 * 98 * 2 = 1764 miles
hours = (1764 / 60) + (98 * 1.1) = 137.20
cost = 395 * 98 = 38,710
```

Dual Axle calculation:

```text
loads = ceil(1956 / 13) = 151
distance = 9 * 151 * 2 = 2718 miles
hours = (2718 / 60) + (151 * 1.1) = 211.40
cost = 395 * 151 = 59,645
```

Single Axle calculation:

```text
loads = ceil(1956 / 3) = 652
distance = 9 * 652 * 2 = 11,736 miles
hours = (11736 / 60) + (652 * 1.1) = 912.80
cost = 395 * 652 = 257,540
```

## Implementation Notes For OCERP

Recommended service boundary:

```text
TruckCostCalculator.calculate(
  material_volume,
  material_weight,
  measurement_unit,
  quarry_distance,
  billing_type,
  truck_cost_per_load,
  truck_types,
  speed_for_hour_calculation,
  gas_cost,
  dump_truck_time_at_quarry,
  dump_truck_time_at_job_site,
)
```

Recommended output per truck type:

```text
truck_type
truck_capacity
truck_capacity_unit
loads
distance_miles
hours
cost
cost_method
```

Preserve two separate calculation concepts:

- Preview grid: calculate all current-effective truck types from live form inputs.
- Saved estimate cost: calculate selected/persisted truck type and persisted load count.

## Edge Cases

- If material quantity or truck capacity is blank/zero, do not divide by zero. Return an invalid/empty row or `loads = 0` depending on UI needs.
- If billing type is `load`, require `truck_cost_per_load` before save.
- If billing type is `mile`, require `miles_per_gallon`, `cost_per_mile`, and `gas_cost`.
- If billing type is `hour`, require `cost_per_hour` and `speed_for_hour_calculation`.
- Effective-dated truck types and variables must use the estimate/job/material calculation date, not necessarily today's date.
