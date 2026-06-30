import { MapPin } from 'lucide-react';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';

import { PROXY_TILE_BASE } from './basemap';

export interface LatLng {
  lat: number;
  lng: number;
}

interface ProjectMapCardProps {
  lat?: number | null;
  lng?: number | null;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  className?: string;
  label?: string;
  onResolved?: (coords: LatLng) => void;
}

const STATIC_TILE_ZOOM = 11;

function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

function lngToTileX(lng: number, z: number): number {
  return ((lng + 180) / 360) * 2 ** z;
}

function latToTileY(lat: number, z: number): number {
  const rad = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * 2 ** z;
}

function staticTileUrl(coords: LatLng): string {
  const z = STATIC_TILE_ZOOM;
  const max = 2 ** z;
  const x = Math.min(max - 1, Math.max(0, Math.floor(lngToTileX(coords.lng, z))));
  const y = Math.min(max - 1, Math.max(0, Math.floor(latToTileY(coords.lat, z))));
  return `${PROXY_TILE_BASE}/${z}/${x}/${y}.png`;
}

function buildLabel(label?: string, city?: string | null, country?: string | null): string {
  return label || [city, country].filter(Boolean).join(', ');
}

export function ProjectMapCard({
  lat,
  lng,
  city,
  country,
  className,
  label,
  onResolved,
}: ProjectMapCardProps) {
  const { t } = useTranslation();
  const hasCoords = isFiniteNumber(lat) && isFiniteNumber(lng);
  const coords = hasCoords ? { lat, lng } : null;
  const displayLabel = buildLabel(label, city, country);

  useEffect(() => {
    if (coords) {
      onResolved?.(coords);
    }
    // Parent callbacks are often inline; the resolved coordinate is the only
    // meaningful trigger here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coords?.lat, coords?.lng]);

  const heightClass = 'h-28';
  const baseClass = clsx(
    'relative overflow-hidden rounded-xl border border-border-light bg-slate-100 dark:bg-slate-800',
    heightClass,
    className,
  );

  if (!coords) {
    return (
      <div className={baseClass}>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-content-quaternary">
          <MapPin size={18} strokeWidth={1.5} />
          <span className="max-w-[80%] truncate text-[10px] font-medium">
            {displayLabel || t('projects.map_no_location', { defaultValue: 'No location set' })}
          </span>
        </div>
      </div>
    );
  }

  const z = STATIC_TILE_ZOOM;
  const fracX = lngToTileX(coords.lng, z) % 1;
  const fracY = latToTileY(coords.lat, z) % 1;

  return (
    <div className={baseClass}>
      <img
        src={staticTileUrl(coords)}
        alt={displayLabel || t('projects.map_thumbnail_alt', { defaultValue: 'Project location map' })}
        loading="lazy"
        decoding="async"
        draggable={false}
        className="absolute inset-0 h-full w-full select-none object-cover"
      />
      <div
        className="pointer-events-none absolute z-[1] flex h-6 w-6 -translate-x-1/2 -translate-y-full items-center justify-center"
        style={{ left: `${fracX * 100}%`, top: `${fracY * 100}%` }}
        aria-hidden="true"
      >
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-oe-blue text-white shadow-md shadow-oe-blue/40 ring-2 ring-white">
          <MapPin size={11} fill="currentColor" strokeWidth={0} />
        </span>
      </div>
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />
      {displayLabel && (
        <div className="pointer-events-none absolute inset-x-2 bottom-2 flex items-center gap-1 rounded-md bg-surface-elevated/90 backdrop-blur-sm px-2 py-1 shadow-sm">
          <MapPin size={11} className="shrink-0 text-oe-blue" />
          <span className="truncate text-[11px] font-medium text-content-primary">
            {displayLabel}
          </span>
        </div>
      )}
    </div>
  );
}
