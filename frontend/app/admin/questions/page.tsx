'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { CheckCircle, XCircle, Pencil } from 'lucide-react'
import {
  Card, CardContent, CardHeader, CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { apiClientFetch } from '@/lib/api-client'
import { difficultyLabel } from '@/lib/utils'
import type { Question } from '@/types'

interface QuestionListResponse {
  items: Question[]
  total: number
  page: number
  per_page: number
}

export default function AdminQuestionsPage() {
  const { data: authSession } = useSession()
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const [questions, setQuestions] = useState<Question[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const perPage = 20

  const fetchQuestions = async (p = page, q = search) => {
    if (!accessToken) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(perPage) })
      if (q) params.set('search', q)
      const data = await apiClientFetch<QuestionListResponse>(
        `/admin/questions?${params}`, accessToken,
      )
      setQuestions(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchQuestions() }, [accessToken, page])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchQuestions(1, search)
  }

  const toggleVetted = async (q: Question) => {
    if (!accessToken) return
    setActionLoading(q.id)
    try {
      await apiClientFetch(`/admin/questions/${q.id}`, accessToken, {
        method: 'PATCH',
        body: JSON.stringify({ is_vetted: !q.is_vetted }),
      })
      setQuestions(prev => prev.map(item =>
        item.id === q.id ? { ...item, is_vetted: !item.is_vetted } : item,
      ))
    } finally {
      setActionLoading(null)
    }
  }

  const softDelete = async (q: Question) => {
    if (!accessToken || !confirm(`Archive question "${q.title}"?`)) return
    setActionLoading(q.id)
    try {
      await apiClientFetch(`/admin/questions/${q.id}`, accessToken, { method: 'DELETE' })
      setQuestions(prev => prev.filter(item => item.id !== q.id))
      setTotal(prev => prev - 1)
    } finally {
      setActionLoading(null)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Question bank</h1>
        <span className="text-sm text-muted-foreground">{total} questions</span>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search questions…"
          className="max-w-xs"
        />
        <Button type="submit" variant="outline">Search</Button>
      </form>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-3">
          {questions.map(q => (
            <Card key={q.id}>
              <CardContent className="flex items-start gap-4 py-4">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{q.title}</span>
                    {q.is_vetted ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <span className="text-xs text-amber-500">Unvetted</span>
                    )}
                  </div>
                  <div className="flex gap-2 text-xs text-muted-foreground">
                    <Badge variant="secondary">{q.category}</Badge>
                    <Badge variant="outline">{difficultyLabel(q.difficulty)}</Badge>
                    {q.technologies.slice(0, 3).map(t => (
                      <Badge key={t} variant="outline">{t}</Badge>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleVetted(q)}
                    disabled={actionLoading === q.id}
                  >
                    {q.is_vetted ? 'Unvet' : 'Vet'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={actionLoading === q.id}
                    onClick={() => softDelete(q)}
                  >
                    <XCircle className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page === totalPages}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
