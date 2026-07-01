import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import Image from 'next/image'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import type { Certificate } from '@/types'

interface Params { params: Promise<{ token: string }> }

async function getCertificate(token: string): Promise<Certificate | null> {
  const base = process.env.FASTAPI_BASE_URL ?? 'http://localhost:8000'
  const res = await fetch(`${base}/sessions/certificate/share?token=${token}`, {
    next: { revalidate: 3600 },
  })
  if (!res.ok) return null
  return res.json()
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { token } = await params
  const cert = await getCertificate(token)
  if (!cert) return { title: 'Certificate not found' }
  return {
    title: 'Engineering Assessment Certificate',
    openGraph: {
      images: [{ url: cert.image_url, width: 1200, height: 630 }],
    },
    twitter: { card: 'summary_large_image', images: [cert.image_url] },
  }
}

export default async function CertificateSharePage({ params }: Params) {
  const { token } = await params
  const cert = await getCertificate(token)
  if (!cert) notFound()

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto flex max-w-3xl flex-1 flex-col items-center gap-6 px-4 py-16">
        <h1 className="text-3xl font-bold">Engineering Assessment Certificate</h1>
        <div className="w-full overflow-hidden rounded-lg border shadow-lg">
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
            <a href={cert.image_url} download="crucible-certificate.png">
              Download PNG
            </a>
          </Button>
          <Button variant="outline" asChild>
            <a href={cert.linkedin_url} target="_blank" rel="noopener noreferrer">
              Share on LinkedIn
            </a>
          </Button>
        </div>
      </main>
      <Footer />
    </div>
  )
}
