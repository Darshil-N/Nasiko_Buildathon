"use client";

import { MapContainer, TileLayer, Polygon, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

// Fix Leaflet SSR issues
import L from "leaflet";
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

interface MapProps {
  center: [number, number];
  zoom: number;
}

export default function Map({ center, zoom }: MapProps) {
  // Dummy polygons for demo
  const polygons = [
    { id: 1, positions: [[12.9716, 77.5946], [12.9756, 77.5946], [12.9756, 77.5986], [12.9716, 77.5986]], score: 85, name: "Kaverappa Layout" },
    { id: 2, positions: [[12.9616, 77.5846], [12.9656, 77.5846], [12.9656, 77.5886], [12.9616, 77.5886]], score: 75, name: "Ashok Nagar" }
  ];

  return (
    <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} style={{ height: "100%", width: "100%", borderRadius: "24px" }} zoomControl={false}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      />
      {polygons.map(p => (
        <Polygon
          key={p.id}
          positions={p.positions as any}
          pathOptions={{
            color: '#1d1d1f',
            fillColor: p.score > 80 ? '#1d1d1f' : '#86868b',
            fillOpacity: 0.6,
            weight: 2
          }}
        >
          <Tooltip sticky direction="top" className="custom-tooltip">
            <div className="font-sans">
              <strong className="block text-sm">{p.name}</strong>
              <span className="text-xs text-neutral-500">Score: {p.score}</span>
            </div>
          </Tooltip>
        </Polygon>
      ))}
    </MapContainer>
  );
}
