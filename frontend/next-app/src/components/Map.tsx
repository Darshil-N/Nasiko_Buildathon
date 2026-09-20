"use client";

import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export interface MapZone {
  rank: number;
  name: string;
  score: number;
  lat: number;
  lon: number;
}

interface MapProps {
  center: [number, number];
  zoom: number;
  zones: MapZone[];
}

// A warm heat scale: cool blue for the lowest score in the set, up through teal, amber, to a
// vivid signal red for the top zone - reads clearly at a glance from across a room.
const STOPS: [number, string][] = [
  [0, "#3b82f6"],
  [0.35, "#22c55e"],
  [0.65, "#f59e0b"],
  [1, "#ef4444"],
];

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function scoreColor(t: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  let lo = STOPS[0];
  let hi = STOPS[STOPS.length - 1];
  for (let i = 0; i < STOPS.length - 1; i++) {
    if (clamped >= STOPS[i][0] && clamped <= STOPS[i + 1][0]) {
      lo = STOPS[i];
      hi = STOPS[i + 1];
      break;
    }
  }
  const span = hi[0] - lo[0] || 1;
  const localT = (clamped - lo[0]) / span;
  const [r1, g1, b1] = hexToRgb(lo[1]);
  const [r2, g2, b2] = hexToRgb(hi[1]);
  return `rgb(${Math.round(lerp(r1, r2, localT))}, ${Math.round(lerp(g1, g2, localT))}, ${Math.round(lerp(b1, b2, localT))})`;
}

function FitToZones({ zones }: { zones: MapZone[] }) {
  const map = useMap();
  useEffect(() => {
    if (zones.length === 0) return;
    const bounds = L.latLngBounds(zones.map((z) => [z.lat, z.lon] as [number, number]));
    map.fitBounds(bounds, { padding: [60, 60], maxZoom: 14 });
  }, [zones, map]);
  return null;
}

export default function Map({ center, zoom, zones = [] }: MapProps) {
  const scores = zones.map((z) => z.score);
  const min = scores.length ? Math.min(...scores) : 0;
  const max = scores.length ? Math.max(...scores) : 1;
  const range = max - min || 1;

  return (
    <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} style={{ height: "100%", width: "100%", borderRadius: "24px" }} zoomControl={false}>
      <TileLayer
        attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url={`https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=${process.env.NEXT_PUBLIC_CARTO_API_KEY ?? ""}`}
      />
      <FitToZones zones={zones} />
      {zones.map((z) => {
        const t = (z.score - min) / range;
        const color = scoreColor(t);
        const isTop = z.rank === 1;
        return (
          <CircleMarker
            key={z.rank}
            center={[z.lat, z.lon]}
            radius={isTop ? 20 : 10 + t * 6}
            pathOptions={{
              color: isTop ? "#1d1d1f" : "#ffffff",
              weight: isTop ? 3 : 2,
              fillColor: color,
              fillOpacity: isTop ? 0.95 : 0.8,
            }}
          >
            <Tooltip sticky direction="top" className="custom-tooltip">
              <div className="font-sans">
                <strong className="block text-sm">
                  #{z.rank} {z.name}
                </strong>
                <span className="text-xs text-neutral-500">Score: {z.score.toFixed(1)}</span>
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
