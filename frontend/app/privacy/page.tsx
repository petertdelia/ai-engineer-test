import type { Metadata } from 'next'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'

export const metadata: Metadata = { title: 'Privacy Policy' }

export default function PrivacyPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto max-w-3xl flex-1 px-4 py-16">
        <h1 className="mb-6 text-4xl font-bold">Privacy Policy</h1>
        <p className="mb-4 text-sm text-muted-foreground">Last updated: {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
        <div className="prose dark:prose-invert max-w-none">
          <h2>Data we collect</h2>
          <p>We collect your email address, name, and assessment responses. AI chat interactions within exam sessions are stored to power per-session scoring.</p>
          <h2>How we use it</h2>
          <p>Assessment data is used exclusively to compute your scores, generate certificates, and improve the platform. We do not sell personal data.</p>
          <h2>Data retention</h2>
          <p>Account data is retained for 2 years after your last login. You may request deletion at any time via Account Settings.</p>
          <h2>Your rights</h2>
          <p>You have the right to access, export, and delete your data. Use the Account Settings page or contact us at privacy@crucible.dev.</p>
          <h2>Cookies</h2>
          <p>We use a single session cookie for authentication. No third-party tracking cookies are set without your consent.</p>
          <h2>Contact</h2>
          <p>Questions? Email privacy@crucible.dev.</p>
        </div>
      </main>
      <Footer />
    </div>
  )
}
