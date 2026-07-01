'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { apiClientFetch } from '@/lib/api-client'
import { cn } from '@/lib/utils'
import type { Difficulty, SessionMode, AssessmentSession } from '@/types'

const MODES: Array<{ value: SessionMode; label: string; desc: string; questions: number; time: string }> = [
  { value: 'trial', label: 'Trial', desc: 'Quick taste of the platform. Not scored.', questions: 2, time: '20 min' },
  { value: 'practice', label: 'Practice', desc: 'Full experience. Not ranked.', questions: 5, time: '60 min' },
  { value: 'exam', label: 'Exam', desc: 'Counts toward your rank. Email verification required.', questions: 10, time: '90 min' },
]

const DIFFICULTIES: Array<{ value: Difficulty; label: string; desc: string }> = [
  { value: 'low', label: 'Low', desc: 'More AI guidance, gentler scoring' },
  { value: 'medium', label: 'Medium', desc: 'Balanced challenge' },
  { value: 'high', label: 'High', desc: 'Minimal guidance, strict scoring' },
]

export default function StartPage() {
  const { data: authSession } = useSession()
  const router = useRouter()
  const [mode, setMode] = useState<SessionMode>('practice')
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const user = authSession?.user as any
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const handleStart = async () => {
    setLoading(true)
    setError(null)
    try {
      const created = await apiClientFetch<AssessmentSession>('/sessions', accessToken, {
        method: 'POST',
        body: JSON.stringify({ mode, difficulty }),
      })
      await apiClientFetch(`/sessions/${created.id}/start`, accessToken, { method: 'POST' })
      router.push(`/app/session/${created.id}`)
    } catch (err: any) {
      if (err.status === 403) {
        setError('Verify your email to start Exam sessions.')
      } else {
        setError(err.message ?? 'Failed to start session.')
      }
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">Start an assessment</h1>

      <div>
        <h2 className="mb-3 font-semibold">Mode</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {MODES.map((m) => {
            const blocked = m.value === 'exam' && !user?.is_email_verified
            return (
              <Card
                key={m.value}
                className={cn(
                  'cursor-pointer transition-colors',
                  mode === m.value ? 'border-primary ring-1 ring-primary' : '',
                  blocked ? 'cursor-not-allowed opacity-50' : 'hover:border-primary/50',
                )}
                onClick={() => !blocked && setMode(m.value)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{m.label}</CardTitle>
                    {blocked && <Badge variant="warning" className="text-xs">Email required</Badge>}
                  </div>
                  <CardDescription>{m.desc}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{m.questions} questions · {m.time}</p>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>

      <div>
        <h2 className="mb-3 font-semibold">Difficulty</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {DIFFICULTIES.map((d) => (
            <Card
              key={d.value}
              className={cn(
                'cursor-pointer transition-colors hover:border-primary/50',
                difficulty === d.value ? 'border-primary ring-1 ring-primary' : '',
              )}
              onClick={() => setDifficulty(d.value)}
            >
              <CardHeader>
                <CardTitle className="text-base">{d.label}</CardTitle>
                <CardDescription>{d.desc}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button size="lg" onClick={handleStart} disabled={loading} className="w-full sm:w-auto">
        {loading ? 'Starting…' : 'Start session'}
      </Button>
    </div>
  )
}
