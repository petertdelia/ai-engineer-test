import type { Metadata } from 'next'
import { auth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'
import { ResultsPoller } from '@/components/results/ResultsPoller'
import { Badge } from '@/components/ui/badge'
import { modeLabel, difficultyLabel, formatDateTime } from '@/lib/utils'
import type { AssessmentSession } from '@/types'

export const metadata: Metadata = { title: 'Results' }

interface Params { params: Promise<{ id: string }> }

export default async function ResultsPage({ params }: Params) {
  const { id } = await params
  const sessionId = parseInt(id)

  const session = await apiFetch<AssessmentSession>(`/sessions/${sessionId}`).catch(() => null)

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Session results</h1>
        {session && (
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="secondary">{modeLabel(session.mode)}</Badge>
            <Badge variant="outline">{difficultyLabel(session.difficulty)}</Badge>
            {session.ended_at && <span>{formatDateTime(session.ended_at)}</span>}
          </div>
        )}
      </div>

      <ResultsPoller sessionId={sessionId} mode={session?.mode ?? 'exam'} />
    </div>
  )
}
