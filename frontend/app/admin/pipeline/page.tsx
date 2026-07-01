'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Play, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { apiClientFetch } from '@/lib/api-client'
import { formatDateTime } from '@/lib/utils'
import type { PipelineRun } from '@/types'

export default function AdminPipelinePage() {
  const { data: authSession } = useSession()
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const [runs, setRuns] = useState<PipelineRun[]>([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [topic, setTopic] = useState('')
  const [count, setCount] = useState('5')
  const [triggerError, setTriggerError] = useState<string | null>(null)
  const [triggerSuccess, setTriggerSuccess] = useState(false)
  const [polling, setPolling] = useState(false)

  const fetchRuns = async () => {
    if (!accessToken) return
    try {
      const data = await apiClientFetch<PipelineRun[]>('/admin/pipeline/runs', accessToken)
      setRuns(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchRuns() }, [accessToken])

  // Poll while any run is in progress
  useEffect(() => {
    const hasActive = runs.some(r => r.status === 'in_progress')
    if (!hasActive) { setPolling(false); return }
    setPolling(true)
    const timer = setInterval(fetchRuns, 5000)
    return () => clearInterval(timer)
  }, [runs])

  const handleTrigger = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!accessToken) return
    setTriggering(true)
    setTriggerError(null)
    try {
      const run = await apiClientFetch<PipelineRun>('/admin/pipeline/run', accessToken, {
        method: 'POST',
        body: JSON.stringify({ topic: topic || undefined, count: parseInt(count) }),
      })
      setRuns(prev => [run, ...prev])
      setTopic('')
      setTriggerSuccess(true)
      setTimeout(() => setTriggerSuccess(false), 3000)
    } catch (err: any) {
      setTriggerError(err.detail ?? 'Failed to trigger pipeline.')
    } finally {
      setTriggering(false)
    }
  }

  const statusVariant = (status: string) => {
    if (status === 'completed') return 'success' as const
    if (status === 'failed') return 'destructive' as const
    if (status === 'in_progress') return 'secondary' as const
    return 'outline' as const
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Question pipeline</h1>

      <Card>
        <CardHeader>
          <CardTitle>Trigger run</CardTitle>
          <CardDescription>Generate new questions via the AI pipeline.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleTrigger} className="flex gap-3 flex-wrap">
            <Input
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="Topic (optional, e.g. Kafka)"
              className="w-64"
            />
            <Input
              type="number"
              value={count}
              onChange={e => setCount(e.target.value)}
              min={1}
              max={20}
              className="w-24"
            />
            <Button type="submit" disabled={triggering}>
              <Play className="mr-1 h-4 w-4" />
              {triggering ? 'Triggering…' : 'Run pipeline'}
            </Button>
          </form>
          {triggerError && <p className="mt-2 text-xs text-destructive">{triggerError}</p>}
          {triggerSuccess && <p className="mt-2 text-xs text-green-600">Pipeline triggered.</p>}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Run history</h2>
        <Button variant="ghost" size="sm" onClick={fetchRuns} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${polling ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : runs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No pipeline runs yet.</p>
      ) : (
        <div className="space-y-3">
          {runs.map(run => (
            <Card key={run.id}>
              <CardContent className="flex items-center gap-4 py-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                    <span className="text-sm font-medium">
                      {run.topic ? `Topic: ${run.topic}` : 'General run'}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Started {formatDateTime(run.started_at)}
                    {run.completed_at && ` · Finished ${formatDateTime(run.completed_at)}`}
                    {run.questions_generated !== null && ` · ${run.questions_generated} questions generated`}
                  </div>
                  {run.error_message && (
                    <p className="mt-1 text-xs text-destructive">{run.error_message}</p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
