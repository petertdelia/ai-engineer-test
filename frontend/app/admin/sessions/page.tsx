'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { apiClientFetch } from '@/lib/api-client'
import { formatDateTime, modeLabel } from '@/lib/utils'
import type { AssessmentSession, SessionEvent } from '@/types'

interface FlaggedSession {
  session: AssessmentSession
  events: SessionEvent[]
}

interface FlaggedResponse {
  items: FlaggedSession[]
  total: number
}

export default function AdminSessionsPage() {
  const { data: authSession } = useSession()
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const [flagged, setFlagged] = useState<FlaggedSession[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<number | null>(null)

  useEffect(() => {
    if (!accessToken) return
    apiClientFetch<FlaggedResponse>('/admin/sessions/flagged', accessToken)
      .then(data => { setFlagged(data.items); setTotal(data.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [accessToken])

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Flagged sessions</h1>
        <span className="text-sm text-muted-foreground">{total} flagged</span>
      </div>

      {flagged.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No flagged sessions.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {flagged.map(({ session: s, events }) => (
            <Card key={s.id} className="border-amber-500">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                      Session #{s.id} — {s.user?.name ?? s.user?.email}
                    </CardTitle>
                    <CardDescription>
                      {modeLabel(s.mode)} · {formatDateTime(s.started_at)}
                      {s.ended_at && ` → ${formatDateTime(s.ended_at)}`}
                    </CardDescription>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                  >
                    {expanded === s.id ? 'Hide events' : `${events.length} event${events.length !== 1 ? 's' : ''}`}
                  </Button>
                </div>
              </CardHeader>

              {expanded === s.id && (
                <CardContent>
                  <ul className="space-y-2">
                    {events.map(ev => (
                      <li key={ev.id} className="rounded-md border px-3 py-2 text-xs">
                        <div className="flex items-center justify-between">
                          <Badge variant="warning" className="text-xs">{ev.event_type}</Badge>
                          <span className="text-muted-foreground">{formatDateTime(ev.occurred_at)}</span>
                        </div>
                        {ev.metadata && (
                          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-muted-foreground">
                            {JSON.stringify(ev.metadata, null, 2)}
                          </pre>
                        )}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
