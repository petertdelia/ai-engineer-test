'use client'

import { useState } from 'react'
import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { apiClientFetch } from '@/lib/api-client'

const profileSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
})
type ProfileForm = z.infer<typeof profileSchema>

const passwordSchema = z.object({
  current_password: z.string().min(1, 'Required'),
  new_password: z.string().min(8, 'At least 8 characters'),
  confirm_password: z.string(),
}).refine(d => d.new_password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
})
type PasswordForm = z.infer<typeof passwordSchema>

export default function SettingsPage() {
  const { data: authSession, update } = useSession()
  const router = useRouter()
  const accessToken = (authSession as any)?.accessToken as string | undefined
  const user = (authSession as any)?.user

  const [profileSaved, setProfileSaved] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)
  const [passwordSaved, setPasswordSaved] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [exportLoading, setExportLoading] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: user?.name ?? '' },
  })

  const passwordForm = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })

  const onSaveProfile = async (data: ProfileForm) => {
    if (!accessToken) return
    setProfileError(null)
    try {
      await apiClientFetch('/me', accessToken, {
        method: 'PATCH',
        body: JSON.stringify({ name: data.name }),
      })
      await update({ name: data.name })
      setProfileSaved(true)
      setTimeout(() => setProfileSaved(false), 3000)
    } catch {
      setProfileError('Failed to save. Please try again.')
    }
  }

  const onChangePassword = async (data: PasswordForm) => {
    if (!accessToken) return
    setPasswordError(null)
    try {
      await apiClientFetch('/me/password', accessToken, {
        method: 'POST',
        body: JSON.stringify({
          current_password: data.current_password,
          new_password: data.new_password,
        }),
      })
      setPasswordSaved(true)
      passwordForm.reset()
      setTimeout(() => setPasswordSaved(false), 3000)
    } catch (err: any) {
      setPasswordError(err.detail ?? 'Failed to change password.')
    }
  }

  const onExport = async () => {
    if (!accessToken) return
    setExportLoading(true)
    try {
      const blob = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/me/export`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      }).then(r => r.blob())
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'crucible-data-export.json'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
    } finally {
      setExportLoading(false)
    }
  }

  const onDelete = async () => {
    if (!accessToken) return
    setDeleting(true)
    try {
      await apiClientFetch('/me', accessToken, { method: 'DELETE' })
      await signOut({ callbackUrl: '/' })
    } catch {
      setDeleting(false)
      setDeleteConfirm(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="text-2xl font-bold">Account settings</h1>

      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={profileForm.handleSubmit(onSaveProfile)} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium">Name</label>
              <Input {...profileForm.register('name')} />
              {profileForm.formState.errors.name && (
                <p className="mt-1 text-xs text-destructive">{profileForm.formState.errors.name.message}</p>
              )}
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Email</label>
              <Input value={user?.email ?? ''} readOnly className="bg-muted" />
              <p className="mt-1 text-xs text-muted-foreground">Email cannot be changed.</p>
            </div>
            {profileError && <p className="text-xs text-destructive">{profileError}</p>}
            {profileSaved && <p className="text-xs text-green-600">Profile saved.</p>}
            <Button type="submit" disabled={profileForm.formState.isSubmitting}>Save profile</Button>
          </form>
        </CardContent>
      </Card>

      {/* Password — only shown for credential-based accounts */}
      {!user?.image?.startsWith('https://lh3.googleusercontent.com') && (
        <Card>
          <CardHeader>
            <CardTitle>Change password</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={passwordForm.handleSubmit(onChangePassword)} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Current password</label>
                <Input type="password" {...passwordForm.register('current_password')} />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">New password</label>
                <Input type="password" {...passwordForm.register('new_password')} />
                {passwordForm.formState.errors.new_password && (
                  <p className="mt-1 text-xs text-destructive">{passwordForm.formState.errors.new_password.message}</p>
                )}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Confirm new password</label>
                <Input type="password" {...passwordForm.register('confirm_password')} />
                {passwordForm.formState.errors.confirm_password && (
                  <p className="mt-1 text-xs text-destructive">{passwordForm.formState.errors.confirm_password.message}</p>
                )}
              </div>
              {passwordError && <p className="text-xs text-destructive">{passwordError}</p>}
              {passwordSaved && <p className="text-xs text-green-600">Password changed.</p>}
              <Button type="submit" disabled={passwordForm.formState.isSubmitting}>Change password</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Data export */}
      <Card>
        <CardHeader>
          <CardTitle>Data export</CardTitle>
          <CardDescription>Download a JSON copy of all your sessions, scores, and responses.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={onExport} disabled={exportLoading}>
            {exportLoading ? 'Preparing…' : 'Export my data'}
          </Button>
        </CardContent>
      </Card>

      {/* Delete account */}
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">Delete account</CardTitle>
          <CardDescription>
            Permanently deletes your account and all associated data. This cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!deleteConfirm ? (
            <Button variant="destructive" onClick={() => setDeleteConfirm(true)}>
              Delete my account
            </Button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm font-medium">Are you absolutely sure?</p>
              <div className="flex gap-3">
                <Button variant="destructive" onClick={onDelete} disabled={deleting}>
                  {deleting ? 'Deleting…' : 'Yes, delete everything'}
                </Button>
                <Button variant="outline" onClick={() => setDeleteConfirm(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
