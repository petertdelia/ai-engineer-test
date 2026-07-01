'use client'

import { useEffect, useRef, useState } from 'react'

interface UseExamTimerOptions {
  startedAt: string | null
  timeLimitSeconds: number
  onExpire: () => void
}

export function useExamTimer({ startedAt, timeLimitSeconds, onExpire }: UseExamTimerOptions) {
  const deriveRemaining = () => {
    if (!startedAt) return timeLimitSeconds
    const elapsed = (Date.now() - new Date(startedAt).getTime()) / 1000
    return Math.max(0, timeLimitSeconds - elapsed)
  }

  const [remaining, setRemaining] = useState(deriveRemaining)
  const expiredRef = useRef(false)
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire

  // Re-sync from server time on tab refocus to correct for drift
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        setRemaining(deriveRemaining())
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [startedAt, timeLimitSeconds])

  useEffect(() => {
    const tick = setInterval(() => {
      const r = deriveRemaining()
      setRemaining(r)
      if (r <= 0 && !expiredRef.current) {
        expiredRef.current = true
        clearInterval(tick)
        onExpireRef.current()
      }
    }, 1000)
    return () => clearInterval(tick)
  }, [startedAt, timeLimitSeconds])

  const seconds = Math.ceil(remaining)
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  const display = `${m}:${String(s).padStart(2, '0')}`
  const isWarning = remaining < 300  // < 5 minutes
  const isCritical = remaining < 60  // < 1 minute

  return { remaining, display, isWarning, isCritical }
}
