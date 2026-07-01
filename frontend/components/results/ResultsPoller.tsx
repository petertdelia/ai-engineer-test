'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { ScoreRadar } from './ScoreRadar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { apiClientFetch } from '@/lib/api-client'
import { formatScore } from '@/lib/utils'
import type { SessionScore, SessionQuestion } from '@/types'

interface ResultsData {
  status: 'pending' | 'completed' | 'failed'
  score: SessionScore | null
  questions: SessionQuestion[]
  failure_reason?: string
}

interface ResultsPolllerProps {
  sessionId: number
  mode: 'trial' | 'practice' | 'exam'
}

export function ResultsPoller({ sessionId, mode }: ResultsPolllerProps) {
  const { data: authSession } = useSession()
  const accessToken = (authSession as any)?.accessToken as string | undefined
  const [data, setData] = useState<ResultsData | null>(null)

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>

    const poll = async () => {
      try {
        const result = await apiClientFetch<ResultsData>(
          `/sessions/${sessionId}/results`,
          accessToken,
        )
        setData(result)
        if (result.status !== 'pending') clearInterval(timer)
      } catch {}
    }

    poll()
    timer = setInterval(poll, 3000)
    return () => clearInterval(timer)
  }, [sessionId, accessToken])

  if (!data || data.status === 'pending') {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-muted-foreground">Scoring your session… this takes about 30 seconds.</p>
      </div>
    )
  }

  if (data.status === 'failed') {
    return (
      <Card className="border-destructive">
        <CardContent className="py-8 text-center">
          <p className="mb-2 font-semibold text-destructive">Scoring failed</p>
          <p className="mb-4 text-sm text-muted-foreground">{data.failure_reason ?? 'An unexpected error occurred.'}</p>
          <p className="text-sm text-muted-foreground">Contact support and mention session #{sessionId}.</p>
        </CardContent>
      </Card>
    )
  }

  const score = data.score

  // Trial / Practice — show responses without scores
  if (mode !== 'exam' || !score) {
    return (
      <div className="space-y-4">
        <p className="text-muted-foreground">
          {mode !== 'exam' ? 'Practice sessions are not scored.' : 'No score available.'} Here are your responses.
        </p>
        {data.questions.map((sq, i) => (
          <Card key={sq.id}>
            <CardHeader>
              <CardTitle className="text-base">Q{i + 1}: {sq.question.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-sm">{sq.response_text ?? 'No response submitted.'}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Overall score */}
      <div className="flex items-start gap-6">
        <Card className="flex-1">
          <CardContent className="pt-6">
            <div className="mb-1 text-sm text-muted-foreground">Total score</div>
            <div className="text-5xl font-bold">{formatScore(score.total_score)}</div>
            {score.percentile_rank !== null && (
              <p className="mt-1 text-sm text-muted-foreground">
                Top {100 - Math.round(score.percentile_rank)}% of candidates
              </p>
            )}
          </CardContent>
        </Card>
        <div className="w-72">
          <ScoreRadar score={score} />
        </div>
      </div>

      {/* Dimension breakdown */}
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          { label: 'Engineering Skill', value: score.engineering_skill },
          { label: 'AI Collaboration', value: score.ai_collaboration },
          { label: 'AI Trust Calibration', value: score.ai_trust_calibration },
          { label: 'Engineering Judgement', value: score.engineering_judgement },
        ].map(({ label, value }) => (
          <Card key={label}>
            <CardContent className="flex items-center justify-between py-4">
              <span className="text-sm">{label}</span>
              <span className="font-mono font-semibold">{formatScore(value)}</span>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Certificate prompt */}
      {score.total_score !== null && score.total_score >= 75 && (
        <Card className="border-primary bg-primary/5">
          <CardContent className="flex items-center justify-between py-4">
            <p className="text-sm font-medium">You qualify for a certificate!</p>
            <Button asChild size="sm">
              <Link href={`/app/session/${sessionId}/certificate`}>View certificate</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Per-question breakdown */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Question breakdown</h2>
        {data.questions.map((sq, i) => (
          <Card key={sq.id}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Q{i + 1}: {sq.question.title}</CardTitle>
                <div className="flex gap-2">
                  {sq.score_engineering_skill !== null && (
                    <Badge variant="secondary">Skill: {formatScore(sq.score_engineering_skill)}</Badge>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="whitespace-pre-wrap text-sm">{sq.response_text ?? 'No response submitted.'}</p>
              {sq.scoring_notes && (
                <div className="rounded-md bg-muted p-3 text-xs space-y-1">
                  {Object.entries(sq.scoring_notes).map(([dim, rationale]) => (
                    <div key={dim}>
                      <span className="font-medium capitalize">{dim.replace(/_/g, ' ')}: </span>
                      {rationale}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
