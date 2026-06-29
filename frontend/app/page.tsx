'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Box, Button, TextField, Typography, Alert, CircularProgress,
} from '@mui/material'
import { loginUser } from './lib/api'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { access } = await loginUser(username, password)
      sessionStorage.setItem('token', access)
      router.push('/map')
    } catch {
      setError('Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        display: 'flex', flexDirection: 'column', gap: 2,
        maxWidth: 360, mx: 'auto', mt: 12, px: 3,
      }}
    >
      <Typography variant="h5" fontWeight={700}>IrelandAQ</Typography>
      <Typography variant="body2" color="text.secondary">
        Sign in to view the air quality map
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <TextField
        label="Username" value={username} required
        onChange={e => setUsername(e.target.value)}
      />
      <TextField
        label="Password" type="password" value={password} required
        onChange={e => setPassword(e.target.value)}
      />
      <Button type="submit" variant="contained" disabled={loading}>
        {loading ? <CircularProgress size={22} color="inherit" /> : 'Sign in'}
      </Button>
    </Box>
  )
}