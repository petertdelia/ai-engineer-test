import { auth } from './auth'

const BASE = process.env.FASTAPI_BASE_URL ?? 'http://localhost:8000'

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const session = await auth()
  const token = (session as any)?.accessToken

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw Object.assign(new Error(body.message ?? res.statusText), {
      status: res.status,
      body,
    })
  }

  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}
