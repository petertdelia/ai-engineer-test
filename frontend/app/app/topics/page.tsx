'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Plus, X } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { apiClientFetch } from '@/lib/api-client'
import { topicSchema, type TopicInput } from '@/lib/zod-schemas'
import type { SavedTopic } from '@/types'

export default function TopicsPage() {
  const { data: authSession } = useSession()
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const [topics, setTopics] = useState<SavedTopic[]>([])
  const [loading, setLoading] = useState(true)
  const [removing, setRemoving] = useState<string | null>(null)

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<TopicInput>({
    resolver: zodResolver(topicSchema),
  })

  useEffect(() => {
    if (!accessToken) return
    apiClientFetch<SavedTopic[]>('/users/me/topics', accessToken)
      .then(setTopics)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [accessToken])

  const onAdd = async (data: TopicInput) => {
    if (!accessToken) return
    const newTopic = await apiClientFetch<SavedTopic>('/users/me/topics', accessToken, {
      method: 'POST',
      body: JSON.stringify({ topic_name: data.topic_name, study_url: data.study_url }),
    })
    setTopics(prev => [newTopic, ...prev])
    reset()
  }

  const onRemove = async (id: string) => {
    if (!accessToken) return
    setRemoving(id)
    try {
      await apiClientFetch(`/users/me/topics/${id}`, accessToken, { method: 'DELETE' })
      setTopics(prev => prev.filter(t => t.id !== id))
    } finally {
      setRemoving(null)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Study topics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Save topics you want to focus on. They'll influence question selection in Practice mode.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add a topic</CardTitle>
          <CardDescription>e.g. "Kafka consumer groups", "RAG evaluation strategies"</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onAdd)} className="flex flex-col gap-2 sm:flex-row">
            <div className="flex-1">
              <Input
                {...register('topic_name')}
                placeholder="Enter a topic..."
                className={errors.topic_name ? 'border-destructive' : ''}
              />
              {errors.topic_name && (
                <p className="mt-1 text-xs text-destructive">{errors.topic_name.message}</p>
              )}
            </div>
            <div className="flex-1">
              <Input
                {...register('study_url')}
                placeholder="https://..."
                className={errors.study_url ? 'border-destructive' : ''}
              />
              {errors.study_url && (
                <p className="mt-1 text-xs text-destructive">{errors.study_url.message}</p>
              )}
            </div>
            <Button type="submit" disabled={isSubmitting}>
              <Plus className="mr-1 h-4 w-4" />
              Add
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Your topics</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : topics.length === 0 ? (
            <p className="text-sm text-muted-foreground">No topics saved yet.</p>
          ) : (
            <ul className="space-y-2">
              {topics.map(t => (
                <li key={t.id} className="flex items-center justify-between rounded-md border px-3 py-2">
                  <a href={t.study_url} target="_blank" rel="noreferrer" className="text-sm underline">
                    {t.topic_name}
                  </a>
                  <button
                    onClick={() => onRemove(t.id)}
                    disabled={removing === t.id}
                    className="text-muted-foreground hover:text-destructive disabled:opacity-50"
                    aria-label={`Remove ${t.topic_name}`}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="text-xs text-muted-foreground">
        <Badge variant="secondary" className="mr-1">{topics.length}</Badge>
        {topics.length === 1 ? 'topic' : 'topics'} saved
      </div>
    </div>
  )
}
