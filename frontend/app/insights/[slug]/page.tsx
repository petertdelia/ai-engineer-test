import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import fs from 'fs'
import path from 'path'
import matter from 'gray-matter'
import { remark } from 'remark'
import html from 'remark-html'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'

export const revalidate = false

interface Params { params: Promise<{ slug: string }> }

function getArticle(slug: string) {
  const file = path.join(process.cwd(), 'content/insights', `${slug}.md`)
  if (!fs.existsSync(file)) return null
  const raw = fs.readFileSync(file, 'utf-8')
  const { data, content } = matter(raw)
  return { data, content }
}

export async function generateStaticParams() {
  const dir = path.join(process.cwd(), 'content/insights')
  if (!fs.existsSync(dir)) return []
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.md'))
    .map((f) => ({ slug: f.replace('.md', '') }))
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params
  const article = getArticle(slug)
  if (!article) return {}
  return { title: article.data.title }
}

export default async function InsightArticle({ params }: Params) {
  const { slug } = await params
  const article = getArticle(slug)
  if (!article) notFound()

  const processed = await remark().use(html).process(article.content)
  const contentHtml = processed.toString()

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto max-w-3xl flex-1 px-4 py-16">
        <p className="mb-2 text-sm text-muted-foreground">
          {new Date(article.data.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
        <h1 className="mb-10 text-4xl font-bold">{article.data.title}</h1>
        <article
          className="prose dark:prose-invert max-w-none"
          dangerouslySetInnerHTML={{ __html: contentHtml }}
        />
      </main>
      <Footer />
    </div>
  )
}
