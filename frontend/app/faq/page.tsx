import type { Metadata } from 'next'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'

export const metadata: Metadata = { title: 'FAQ' }

const faqs = [
  {
    q: 'Does using the AI assistant hurt my score?',
    a: "No — effective AI use is one of the four scoring dimensions. We reward candidates who use the assistant well: asking the right questions, iterating based on guidance, and knowing when to push back on a suggestion.",
  },
  {
    q: 'What modes are available?',
    a: "Trial (2 questions, 20 minutes), Practice (5 questions, 60 minutes), and Exam (10 questions, 90 minutes). Only Exam sessions count toward your rank.",
  },
  {
    q: 'What is AI Trust Calibration?',
    a: "It measures whether you appropriately trusted or pushed back on AI suggestions. Blindly accepting everything the assistant says scores low; so does ignoring every suggestion without reason.",
  },
  {
    q: 'When do I get my certificate?',
    a: "Certificates are issued for Exam sessions where total_score ≥ 75. Results are usually ready within 30 seconds of completing your exam.",
  },
  {
    q: 'Is email verification required?',
    a: "You need a verified email to take Exam sessions and earn a ranked score. Trial and Practice are available immediately after registration.",
  },
  {
    q: 'How is the percentile rank calculated?',
    a: "Percentile ranks are computed across all completed Exam sessions. They are only displayed once the platform has a sufficiently large population to be statistically meaningful.",
  },
  {
    q: 'Can I delete my data?',
    a: "Yes. You can export or delete your data at any time from Account Settings. Deletion removes your profile and anonymizes your session history.",
  },
]

export default function FAQPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto max-w-3xl flex-1 px-4 py-16">
        <h1 className="mb-10 text-4xl font-bold">Frequently asked questions</h1>
        <dl className="space-y-8">
          {faqs.map(({ q, a }) => (
            <div key={q}>
              <dt className="mb-2 font-semibold">{q}</dt>
              <dd className="text-muted-foreground">{a}</dd>
            </div>
          ))}
        </dl>
      </main>
      <Footer />
    </div>
  )
}
