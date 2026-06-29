'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import { Box, CircularProgress } from '@mui/material'
import { getStations, type Station } from '../lib/api'

const AQMap = dynamic(() => import('./components/AQMap'), { ssr: false })

export default function MapPage() {
  const router = useRouter()
  const [stations, setStations] = useState<Station[]>([])
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    const token = sessionStorage.getItem('token')
    if (!token) { router.push('/'); return }

    getStations(token)
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
    <Box sx={{ width: '100vw', height: '100vh', position: 'relative' }}>
      <AQMap stations={stations} />
    </Box>
  )
}