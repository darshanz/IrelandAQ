'use client'

import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import type { Station } from '../../lib/api'

const MAPTILER_KEY = process.env.NEXT_PUBLIC_MAPTILER_KEY ?? ''

function aqiToColor(aqi: number | null): string {
  if (aqi === null) return '#9e9e9e'
  if (aqi <= 50)   return '#4caf50'
  if (aqi <= 100)  return '#ffeb3b'
  if (aqi <= 150)  return '#ff9800'
  return '#f44336'
}

interface Props {
  stations: Station[]
  onStationClick?: (station: Station) => void
}

export default function AQMap({ stations, onStationClick }: Props) {
  return (
    <MapContainer
      center={[53.3, -8.0]}
      zoom={6}
      style={{ width: '100%', height: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.maptiler.com/copyright/">MapTiler</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url={`https://api.maptiler.com/maps/satellite/{z}/{x}/{y}.jpg?key=${MAPTILER_KEY}`}
      />

      {stations.map(station => (
        <CircleMarker
          key={station.id}
          center={[station.latitude, station.longitude]}
          radius={10}
          pathOptions={{
            color: '#ffffff',
            weight: 2,
            fillColor: aqiToColor(station.current_aqi),
            fillOpacity: 1,
          }}
          eventHandlers={{
            click: () => onStationClick?.(station),
          }}
        >
          <Tooltip>{station.city}</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}