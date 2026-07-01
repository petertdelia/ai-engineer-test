import type { Metadata } from 'next'
import Link from 'next/link'
import { CheckCircle, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export const metadata: Metadata = { title: 'Email verification' }

interface Params { params: Promise<{ token: string }> }

async function verifyToken(token: string): Promise<{ success: boolean }> {
  const base = process.env.FASTAPI_BASE_URL ?? 'http://localhost:8000'
  const res = await fetch(`${base}/auth/verify-email?token=${token}`, { method: 'GET' })
  return { success: res.ok }
}

export default async function VerifyEmailTokenPage({ params }: Params) {
  const { token } = await params
  const { success } = await verifyToken(token)

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm text-center">
        <CardHeader>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
            {success ? (
              <CheckCircle className="h-6 w-6 text-green-500" />
            ) : (
              <XCircle className="h-6 w-6 text-destructive" />
            )}
          </div>
          <CardTitle>{success ? 'Email verified' : 'Verification failed'}</CardTitle>
          <CardDescription>
            {success
              ? 'Your account is now fully activated. You can take Exam sessions.'
              : 'This link has expired or is invalid. Request a new one from your account settings.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="w-full">
            <Link href={success ? '/app/dashboard' : '/app/settings'}>
              {success ? 'Go to dashboard' : 'Account settings'}
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
