'use client'

import { useState, useEffect, useRef } from 'react'
import {
  Box, Typography, Button, Chip,
  Divider, CircularProgress,
} from '@mui/material'
import {
  triggerForecast, getForecastStatus,
  type Station, type ForecastRun,
} from '../../lib/api'

export const DRAWER_WIDTH = 340

interface Props {
  station: Station | null
  token: string
}

function statusColor(status: ForecastRun['status']) {
  const map = {
    queued: 'default', running: 'warning',
    success: 'success', failed: 'error',
  } as const
  return map[status]
}

export default function StationDrawer({ station, token }: Props) {
  const [run, setRun]         = useState<ForecastRun | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const pollRef               = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    setRun(null)
    setError('')
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [station])

  async function handleRunForecast() {
    if (!station) return
    setLoading(true)
    setError('')
    try {
      const newRun = await triggerForecast(station.id, token)
      setRun(newRun)
      pollRef.current = setInterval(async () => {
        const updated = await getForecastStatus(newRun.id, token)
        setRun(updated)
        if (updated.status === 'success' || updated.status === 'failed') {
          clearInterval(pollRef.current!)
          pollRef.current = null
        }
      }, 4000)
    } catch {
      setError('Failed to start forecast. Is Airflow running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        height: '100vh',
        borderLeft: 1,
        borderColor: 'divider',
        p: 2.5,
        overflowY: 'auto',
        bgcolor: 'background.paper',
      }}
    >
      <Typography variant="h6" gutterBottom>Station Detail</Typography>
      <Divider sx={{ mb: 2 }} />

      {!station ? (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 4, textAlign: 'center' }}>
          Click a station on the map to view details
        </Typography>
      ) : (
        <>
          <Typography variant="subtitle1" fontWeight={700}>{station.name}</Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {station.city}
          </Typography>

          <Divider sx={{ my: 1.5 }} />

          <Typography variant="body2">
            Current AQI: <strong>{station.current_aqi ?? 'No data'}</strong>
          </Typography>

          <Divider sx={{ my: 1.5 }} />

          <Button
            variant="contained" fullWidth onClick={handleRunForecast}
            disabled={loading || run?.status === 'running' || run?.status === 'queued'}
          >
            {loading
              ? <CircularProgress size={20} color="inherit" />
              : 'Run 24h Forecast'}
          </Button>

          {error && (
            <Typography variant="body2" color="error" sx={{ mt: 1 }}>{error}</Typography>
          )}

          {run && (
            <Box sx={{ mt: 2 }}>
              <Chip
                label={`Status: ${run.status}`}
                color={statusColor(run.status)}
                size="small"
              />
              {(run.status === 'queued' || run.status === 'running') && (
                <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                  Airflow is running the pipeline — polling every 4 s…
                </Typography>
              )}
            </Box>
          )}
        </>
      )}
    </Box>
  )
}