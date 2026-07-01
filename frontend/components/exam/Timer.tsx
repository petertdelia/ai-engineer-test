'use client'

import { cn } from '@/lib/utils'
import { useExamTimer } from '@/hooks/useExamTimer'
import { Clock } from 'lucide-react'

interface TimerProps {
  startedAt: string | null
  timeLimitSeconds: number
  onExpire: () => void
}

export function Timer({ startedAt, timeLimitSeconds, onExpire }: TimerProps) {
  const { display, isWarning, isCritical } = useExamTimer({ startedAt, timeLimitSeconds, onExpire })

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-mono font-semibold tabular-nums',
        isCritical
          ? 'bg-destructive/10 text-destructive animate-pulse'
          : isWarning
          ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
          : 'bg-muted text-muted-foreground',
      )}
      aria-live="polite"
      aria-label={`Time remaining: ${display}`}
    >
      <Clock className="h-4 w-4" />
      {display}
    </div>
  )
}
