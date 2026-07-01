'use client'

const BASE = process.env.NEXT_PUBLIC_FASTAPI_BASE_URL ?? 'http://localhost:8000'

export async function apiClientFetch<T>(
  path: string,
  accessToken: string | undefined,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
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

export function buildUrl(path: string): string {
  return `${BASE}${path}`
}
