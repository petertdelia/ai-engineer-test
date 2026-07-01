import type { Metadata } from 'next'
import Link from 'next/link'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export const metadata: Metadata = { title: 'Insights' }
export const revalidate = false // SSG

function getInsights() {
  const dir = path.join(process.cwd(), 'content/insights')
  if (!fs.existsSync(dir)) return []
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.md'))
    .map((file) => {
      const raw = fs.readFileSync(path.join(dir, file), 'utf-8')
      const { data } = matter(raw)
      return { slug: file.replace('.md', ''), ...data } as {
        slug: string
        title: string
        date: string
        excerpt: string
      }
    })
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

export default function InsightsPage() {
  const articles = getInsights()
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto max-w-4xl flex-1 px-4 py-16">
        <h1 className="mb-10 text-4xl font-bold">Insights</h1>
        {articles.length === 0 ? (
          <p className="text-muted-foreground">No articles yet.</p>
        ) : (
          <div className="grid gap-6">
            {articles.map(({ slug, title, date, excerpt }) => (
              <Link key={slug} href={`/insights/${slug}`} className="group block">
                <Card className="transition-shadow group-hover:shadow-md">
                  <CardHeader>
                    <CardDescription>{new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</CardDescription>
                    <CardTitle className="group-hover:text-primary">{title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-muted-foreground">{excerpt}</p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </div>
  )
}
