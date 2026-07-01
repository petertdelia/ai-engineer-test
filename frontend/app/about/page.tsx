import type { Metadata } from 'next'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'

export const metadata: Metadata = { title: 'About' }

export default function AboutPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto max-w-3xl flex-1 px-4 py-16">
        <h1 className="mb-6 text-4xl font-bold">About Crucible</h1>
        <div className="prose dark:prose-invert max-w-none">
          <p>
            Crucible is a next-generation engineering assessment platform built for the AI era. We
            believe that great engineers are not those who avoid AI tools — they are those who use
            them effectively, calibrate trust appropriately, and apply sound judgement throughout.
          </p>
          <h2>Our mission</h2>
          <p>
            To give engineers a credible, shareable measure of their real-world problem-solving
            ability, in a world where AI assistance is the norm rather than the exception.
          </p>
          <h2>How it works</h2>
          <p>
            Candidates work through realistic scenarios drawn from a bank of ~4,000 vetted
            problems. A built-in AI assistant helps them think — but won&apos;t give away the
            answer. Scoring measures four dimensions: Engineering Skill, AI Collaboration, AI Trust
            Calibration, and Engineering Judgement.
          </p>
          <h2>The question bank</h2>
          <p>
            Questions span Software Engineering, Data Science, Data Engineering, and Cyber
            Security. They are generated and curated through an automated pipeline, quality-checked
            by a secondary model, and reviewed by human experts before entering the live bank.
          </p>
        </div>
      </main>
      <Footer />
    </div>
  )
}
