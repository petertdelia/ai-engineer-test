import type { Metadata } from 'next'
import { redirect } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { Certificate } from '@/types'

export const metadata: Metadata = { title: 'Certificate' }

interface Params { params: Promise<{ id: string }> }

export default async function CertificatePage({ params }: Params) {
  const { id } = await params
  const sessionId = parseInt(id)

  let cert: Certificate | null = null
  let notEligible = false

  try {
    cert = await apiFetch<Certificate>(`/sessions/${sessionId}/certificate`)
  } catch (err: any) {
    if (err.status === 403) {
      notEligible = true
    } else {
      redirect(`/app/session/${sessionId}/results`)
    }
  }

  if (notEligible) {
    return (
      <div className="mx-auto max-w-lg">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="mb-2 font-semibold">Certificate not available</p>
            <p className="mb-4 text-sm text-muted-foreground">
              Certificates are issued for Exam sessions where total score ≥ 75.
            </p>
            <Button asChild variant="outline">
              <Link href={`/app/session/${sessionId}/results`}>Back to results</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!cert) return null

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Your certificate</h1>
      <div className="overflow-hidden rounded-lg border shadow-lg">
        <Image
          src={cert.image_url}
          alt="Certificate"
          width={1200}
          height={630}
          className="w-full"
          priority
        />
      </div>
      <div className="flex gap-3">
        <Button asChild>
          <a href={cert.image_url} download="crucible-certificate.png">Download PNG</a>
        </Button>
        <Button variant="outline" asChild>
          <a href={cert.linkedin_url} target="_blank" rel="noopener noreferrer">Share on LinkedIn</a>
        </Button>
        <Button variant="ghost" asChild>
          <Link href={`/certificate/${cert.share_token}`}>Public share link</Link>
        </Button>
      </div>
    </div>
  )
}
