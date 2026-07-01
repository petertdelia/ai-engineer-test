import Link from 'next/link'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CheckCircle, Brain, BarChart3, Award, Zap, Shield } from 'lucide-react'

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />

      {/* Hero */}
      <section className="mx-auto flex max-w-5xl flex-col items-center gap-6 px-4 py-24 text-center">
        <Badge variant="secondary">Now in beta</Badge>
        <h1 className="text-5xl font-bold tracking-tight">
          The engineering assessment<br />built for the AI era
        </h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Realistic scenarios. A guided AI assistant that helps without giving away the answer.
          Four scoring dimensions that measure your judgement — not the AI's.
        </p>
        <div className="flex gap-3">
          <Button size="lg" asChild>
            <Link href="/register">Take a free trial</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/about">Learn more</Link>
          </Button>
        </div>
      </section>

      {/* Feature grid */}
      <section className="border-t bg-muted/40 py-20">
        <div className="mx-auto max-w-5xl px-4">
          <h2 className="mb-12 text-center text-3xl font-bold">What makes Crucible different</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: Brain,
                title: 'AI assistant, your rules',
                desc: 'The assistant guides your thinking — asks questions, points to concepts — but won\'t write your answer. Your reasoning is what\'s scored.',
              },
              {
                icon: BarChart3,
                title: 'Four scoring dimensions',
                desc: 'Engineering Skill, AI Collaboration, AI Trust Calibration, and Engineering Judgement. Rewarding effective AI use, not penalising it.',
              },
              {
                icon: Zap,
                title: 'Real scenarios',
                desc: '~4,000 vetted problems across Software Engineering, Data Science, Data Engineering, and Cyber Security — with supporting code, logs, and metrics.',
              },
              {
                icon: Shield,
                title: 'Three modes',
                desc: 'Trial to try it out, Practice to rehearse, and the timed Exam — the only mode that counts toward your rank.',
              },
              {
                icon: Award,
                title: 'Shareable certificate',
                desc: 'Strong results earn a certificate you can download and share directly to LinkedIn.',
              },
              {
                icon: CheckCircle,
                title: 'Difficulty control',
                desc: 'Low, Medium, or High difficulty. More AI help and gentler grading on easier settings.',
              },
            ].map(({ icon: Icon, title, desc }) => (
              <Card key={title}>
                <CardHeader>
                  <Icon className="mb-2 h-6 w-6 text-primary" />
                  <CardTitle className="text-lg">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription>{desc}</CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 text-center">
        <div className="mx-auto max-w-2xl px-4">
          <h2 className="mb-4 text-3xl font-bold">Ready to prove your skills?</h2>
          <p className="mb-8 text-muted-foreground">
            Free trial available — no credit card required.
          </p>
          <Button size="lg" asChild>
            <Link href="/register">Get started free</Link>
          </Button>
        </div>
      </section>

      <Footer />
    </div>
  )
}
