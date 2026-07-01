import type { Metadata } from 'next'
import { apiFetch } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatScore } from '@/lib/utils'
import type { AdminStats } from '@/types'

export const metadata: Metadata = { title: 'Platform Stats' }
export const revalidate = 60

export default async function AdminStatsPage() {
  const stats = await apiFetch<AdminStats>('/admin/stats').catch(() => null)

  if (!stats) {
    return <p className="text-sm text-muted-foreground">Failed to load stats.</p>
  }

  const statCards = [
    { label: 'Total users', value: stats.total_users.toLocaleString() },
    { label: 'Active users (30d)', value: stats.active_users_30d.toLocaleString() },
    { label: 'Sessions today', value: stats.sessions_today.toLocaleString() },
    { label: 'Sessions (30d)', value: stats.sessions_30d.toLocaleString() },
    { label: 'Avg total score', value: formatScore(stats.avg_total_score) },
    { label: 'Certificates issued', value: stats.certificates_issued.toLocaleString() },
    { label: 'Questions in bank', value: stats.questions_in_bank.toLocaleString() },
    { label: 'Vetted questions', value: stats.vetted_questions.toLocaleString() },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Platform stats</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map(({ label, value }) => (
          <Card key={label}>
            <CardHeader className="pb-1">
              <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {stats.sessions_by_mode && (
        <div>
          <h2 className="mb-3 text-lg font-semibold">Sessions by mode</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(stats.sessions_by_mode).map(([mode, count]) => (
              <Card key={mode}>
                <CardContent className="flex items-center justify-between py-4">
                  <span className="capitalize text-sm">{mode}</span>
                  <span className="font-mono font-semibold">{(count as number).toLocaleString()}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {stats.score_distribution && (
        <div>
          <h2 className="mb-3 text-lg font-semibold">Score distribution</h2>
          <div className="grid gap-2 sm:grid-cols-4">
            {Object.entries(stats.score_distribution).map(([bucket, count]) => (
              <Card key={bucket}>
                <CardContent className="flex items-center justify-between py-3">
                  <span className="text-sm text-muted-foreground">{bucket}</span>
                  <span className="font-mono">{(count as number).toLocaleString()}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
