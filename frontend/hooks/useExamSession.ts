'use client'

import { useEffect, useCallback, useRef } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { apiClientFetch, buildUrl } from '@/lib/api-client'
import { useExamStore, setSessionStorage } from '@/store/session'
import type { AssessmentSession } from '@/types'

export function useExamSession(sessionId: number) {
  const { data: authSession } = useSession()
  const router = useRouter()
  const { session, setSession } = useExamStore()
  const syncIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const accessToken = (authSession as any)?.accessToken as string | undefined

  const fetchSession = useCallback(async () => {
    try {
      const data = await apiClientFetch<AssessmentSession>(
        `/sessions/${sessionId}`,
        accessToken,
      )
      setSession(data)
      return data
    } catch (err: any) {
      if (err.status === 401) {
        // Save state before redirect
        setSessionStorage('exam_resume', JSON.stringify(useExamStore.getState()))
        router.push(`/login?resume=${sessionId}`)
      }
      throw err
    }
  }, [sessionId, accessToken, setSession, router])

  // Initial hydration
  useEffect(() => {
    if (!accessToken) return
    fetchSession()
  }, [accessToken])

  // Periodic sync every 60s to keep NextAuth session alive and catch server-side state changes
  useEffect(() => {
    if (!accessToken) return
    syncIntervalRef.current = setInterval(fetchSession, 60_000)
    return () => {
      if (syncIntervalRef.current) clearInterval(syncIntervalRef.current)
    }
  }, [accessToken, fetchSession])

  const emitEvent = useCallback(
    (eventType: string, metadata: Record<string, unknown> = {}) => {
      if (!accessToken) return
      // Fire-and-forget
      fetch(buildUrl(`/sessions/${sessionId}/events`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ event_type: eventType, metadata }),
      }).catch(() => {})
    },
    [sessionId, accessToken],
  )

  const abandon = useCallback(() => {
    if (!accessToken) return
    navigator.sendBeacon(
      buildUrl(`/sessions/${sessionId}/abandon`),
      JSON.stringify({}),
    )
  }, [sessionId, accessToken])

  return { session, fetchSession, emitEvent, abandon }
}
