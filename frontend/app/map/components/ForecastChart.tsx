'use client'

import dynamic from 'next/dynamic'
import { Box, CircularProgress } from '@mui/material'
import type { Prediction } from '../../lib/api'

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false })

// EPA PM2.5 breakpoints → AQI
const PM25_BREAKPOINTS = [
  { cLow: 0.0,   cHigh: 12.0,  aLow: 0,   aHigh: 50  },
  { cLow: 12.1,  cHigh: 35.4,  aLow: 51,  aHigh: 100 },
  { cLow: 35.5,  cHigh: 55.4,  aLow: 101, aHigh: 150 },
  { cLow: 55.5,  cHigh: 150.4, aLow: 151, aHigh: 200 },
  { cLow: 150.5, cHigh: 250.4, aLow: 201, aHigh: 300 },
  { cLow: 250.5, cHigh: 350.4, aLow: 301, aHigh: 400 },
  { cLow: 350.5, cHigh: 500.4, aLow: 401, aHigh: 500 },
]

function pm25ToAqi(pm25: number): number {
  const bp = PM25_BREAKPOINTS.find(b => pm25 <= b.cHigh) ?? PM25_BREAKPOINTS.at(-1)!
  return Math.round(
    ((bp.aHigh - bp.aLow) / (bp.cHigh - bp.cLow)) * (pm25 - bp.cLow) + bp.aLow
  )
}

interface Props {
  predictions: Prediction[]
}

export default function ForecastChart({ predictions }: Props) {
  if (!predictions.length) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
        <CircularProgress size={24} />
      </Box>
    )
  }

  const times  = predictions.map(p => p.timestamp)
  const values = predictions.map(p => pm25ToAqi(p.predicted_pm25))
  const uppers = predictions.map(p => pm25ToAqi(p.confidence_upper))
  const lowers = predictions.map(p => pm25ToAqi(p.confidence_lower))

  const data = [
    {
      x: [...times, ...times.slice().reverse()],
      y: [...uppers, ...lowers.slice().reverse()],
      fill: 'toself' as const,
      fillcolor: 'rgba(33,150,243,0.15)',
      line: { color: 'transparent' },
      name: 'Confidence band',
      type: 'scatter' as const,
      hoverinfo: 'skip' as const,
    },
    {
      x: times,
      y: values,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: 'AQI forecast',
      line: { color: '#2196f3', width: 2 },
    },
  ]

  return (
    <Plot
      data={data}
      layout={{
        height: 220,
        margin: { t: 10, r: 10, b: 40, l: 40 },
        xaxis: { type: 'date', tickformat: '%H:%M\n%b %d', tickangle: -45 },
        yaxis: { title: 'AQI' },
        showlegend: false,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  )
}
