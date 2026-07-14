import type { Metadata } from 'next'
import Link from 'next/link'
import { auth } from '@/lib/auth'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatScore, modeLabel, difficultyLabel } from '@/lib/utils'
import { AlertCircle, PlayCircle } from 'lucide-react'
import type { SessionListItem, UserStats } from '@/types'

export const metadata: Metadata = { title: 'Dashboard' }

export default async function DashboardPage() {
  const session = await auth()
  const user = session?.user as any

  const [sessions, stats] = await Promise.all([
    apiFetch<SessionListItem[]>('/sessions?limit=5').catch(() => null),
    apiFetch<UserStats>('/users/me/stats').catch(() => null),
  ])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Welcome back, {user?.name?.split(' ')[0]}</h1>
          <p className="text-muted-foreground">
            {user?.is_email_verified
              ? 'Your account is fully active.'
              : 'Verify your email to unlock Exam sessions.'}
          </p>
        </div>
        <Button asChild>
          <Link href="/app/start">
            <PlayCircle className="mr-2 h-4 w-4" />
            Start assessment
          </Link>
        </Button>
      </div>

      {!user?.is_email_verified && (
        <div className="flex items-center gap-3 rounded-md border border-yellow-300 bg-yellow-50 p-4 text-sm dark:border-yellow-800 dark:bg-yellow-950">
          <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400 shrink-0" />
          <span>
            Please verify your email to access Exam mode and earn a ranked score.{' '}
            <Link href="/app/settings" className="underline">Resend verification email</Link>
          </span>
        </div>
      )}

      {/* Technology breakdown */}
      {stats && stats.tech_strengths.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-semibold">Skill breakdown</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {stats.tech_strengths.slice(0, 6).map((t) => (
              <Card key={t.technology}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-mono">{t.technology}</CardTitle>
                  <CardDescription>{t.session_count} session{t.session_count !== 1 ? 's' : ''}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Average score</span>
                    <span className="font-mono">{formatScore(t.average_score)}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Recent sessions */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Recent sessions</h2>
        {!sessions || sessions.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              No sessions yet.{' '}
              <Link href="/app/start" className="text-foreground underline">Start your first assessment.</Link>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {sessions.map((s) => (
              <Card key={s.id}>
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-3">
                    <Badge variant={s.mode === 'exam' ? 'default' : 'secondary'}>
                      {modeLabel(s.mode)}
                    </Badge>
                    <Badge variant="outline">{difficultyLabel(s.difficulty)}</Badge>
                    <span className="text-sm text-muted-foreground">{formatDate(s.started_at ?? s.ended_at ?? '')}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={s.status === 'completed' ? 'success' : 'warning'}>
                      {s.status}
                    </Badge>
                    {s.status === 'completed' && (
                      <Button size="sm" variant="outline" asChild>
                        <Link href={`/app/session/${s.id}/results`}>Results</Link>
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
