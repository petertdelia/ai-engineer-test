'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Search, ShieldCheck, ShieldOff, Trash2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { apiClientFetch } from '@/lib/api-client'
import { formatDateTime } from '@/lib/utils'
import type { User } from '@/types'

type AdminUser = User & { session_count: number; last_active_at: string | null }

interface UserListResponse {
  items: AdminUser[]
  total: number
  page: number
  per_page: number
}

export default function AdminUsersPage() {
  const { data: authSession } = useSession()
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const perPage = 20

  const fetchUsers = async (p = page, q = search) => {
    if (!accessToken) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(perPage) })
      if (q) params.set('search', q)
      const data = await apiClientFetch<UserListResponse>(
        `/admin/users?${params}`, accessToken,
      )
      setUsers(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUsers() }, [accessToken, page])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchUsers(1, search)
  }

  const toggleBan = async (u: AdminUser) => {
    if (!accessToken) return
    const action = u.is_active ? 'ban' : 'unban'
    if (!confirm(`${action === 'ban' ? 'Ban' : 'Unban'} user ${u.email}?`)) return
    setActionLoading(u.id)
    try {
      await apiClientFetch(`/admin/users/${u.id}/${action}`, accessToken, { method: 'POST' })
      setUsers(prev => prev.map(item =>
        item.id === u.id ? { ...item, is_active: !u.is_active } : item,
      ))
    } finally {
      setActionLoading(null)
    }
  }

  const promoteToAdmin = async (u: User) => {
    if (!accessToken || !confirm(`Promote ${u.email} to admin?`)) return
    setActionLoading(u.id)
    try {
      await apiClientFetch(`/admin/users/${u.id}/promote`, accessToken, { method: 'POST' })
      setUsers(prev => prev.map(item =>
        item.id === u.id ? { ...item, role: 'admin' } : item,
      ))
    } finally {
      setActionLoading(null)
    }
  }

  const gdprDelete = async (u: User) => {
    if (!accessToken || !confirm(`GDPR-delete all data for ${u.email}? This is irreversible.`)) return
    setActionLoading(u.id)
    try {
      await apiClientFetch(`/admin/users/${u.id}/gdpr-delete`, accessToken, { method: 'DELETE' })
      setUsers(prev => prev.filter(item => item.id !== u.id))
      setTotal(prev => prev - 1)
    } finally {
      setActionLoading(null)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Users</h1>
        <span className="text-sm text-muted-foreground">{total} users</span>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name or email…"
          className="max-w-xs"
        />
        <Button type="submit" variant="outline">
          <Search className="mr-1 h-4 w-4" />
          Search
        </Button>
      </form>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-2">
          {users.map(u => (
            <Card key={u.id}>
              <CardContent className="flex items-center gap-4 py-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{u.name ?? u.email}</span>
                    <Badge variant={u.role === 'admin' ? 'default' : 'secondary'}>
                      {u.role}
                    </Badge>
                    {!u.is_active && (
                      <Badge variant="destructive">Banned</Badge>
                    )}
                    {!u.is_email_verified && (
                      <Badge variant="warning">Unverified</Badge>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {u.email}
                    {u.last_active_at && ` · Last active ${formatDateTime(u.last_active_at)}`}
                    {' · '}{u.session_count} sessions
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  {u.role !== 'admin' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => promoteToAdmin(u)}
                      disabled={actionLoading === u.id}
                      title="Promote to admin"
                    >
                      <ShieldCheck className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleBan(u)}
                    disabled={actionLoading === u.id}
                    title={u.is_active ? 'Ban user' : 'Unban user'}
                  >
                    <ShieldOff className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => gdprDelete(u)}
                    disabled={actionLoading === u.id}
                    title="GDPR delete"
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
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
