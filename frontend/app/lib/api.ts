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