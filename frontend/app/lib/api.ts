const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export interface LoginResponse {
  access: string
  refresh: string
}

export async function loginUser(
  username: string,
  password: string
): Promise<LoginResponse> {
  const res = await fetch(`${API}/api/token/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) throw new Error('Invalid credentials')
  return res.json()
}

export interface Station {
  id: number
  openaq_id: string
  name: string
  city: string
  latitude: number
  longitude: number
  current_aqi: number | null
}

export async function getStations(token: string): Promise<Station[]> {
  const res = await fetch(`${API}/api/stations/`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to fetch stations')
  return res.json()
}



export interface ForecastRun {
  id: number
  status: 'queued' | 'running' | 'success' | 'failed'
  dag_run_id: string
  created_at: string
}

export async function triggerForecast(
  stationId: number,
  token: string
): Promise<ForecastRun> {
  const res = await fetch(`${API}/api/forecasts/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ station_id: stationId }),
  })
  if (!res.ok) throw new Error('Failed to trigger forecast')
  return res.json()
}

export async function getForecastStatus(
  runId: number,
  token: string
): Promise<ForecastRun> {
  const res = await fetch(`${API}/api/forecasts/${runId}/`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to fetch forecast status')
  return res.json()
}


export interface Prediction {
  timestamp: string
  predicted_pm25: number
  confidence_lower: number
  confidence_upper: number
}

export async function getForecastPredictions(
  runId: number,
  token: string
): Promise<Prediction[]> {
  const res = await fetch(`${API}/api/forecasts/${runId}/predictions/`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to fetch predictions')
  return res.json()
}


