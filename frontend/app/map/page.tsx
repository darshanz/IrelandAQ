'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import { Box, CircularProgress } from '@mui/material'
import { getStations, type Station } from '../lib/api'
import StationDrawer from './components/StationDrawer'

const AQMap = dynamic(() => import('./components/AQMap'), { ssr: false })

export default function MapPage() {
  const router = useRouter()
  const [stations, setStations]        = useState<Station[]>([])
  const [selectedStation, setSelected] = useState<Station | null>(null)
  const [token, setToken]              = useState('')
  const [loading, setLoading]          = useState(true)

  useEffect(() => {
    const t = sessionStorage.getItem('token') ?? ''
    if (!t) { router.push('/'); return }
    setToken(t)
    getStations(t)
      .then(setStations)
      .catch(() => router.push('/'))
      .finally(() => setLoading(false))
  }, [router])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', width: '100vw', height: '100vh' }}>
      <Box sx={{ flex: 1, height: '100%' }}>
        <AQMap stations={stations} onStationClick={setSelected} />
      </Box>
      <StationDrawer station={selectedStation} token={token} />
    </Box>
  )
}