import Link from 'next/link'

export function Footer() {
  return (
    <footer className="border-t py-8 text-sm text-muted-foreground">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-4 sm:flex-row sm:justify-between">
        <p>© {new Date().getFullYear()} Crucible. All rights reserved.</p>
        <nav className="flex gap-4">
          <Link href="/about" className="hover:text-foreground">About</Link>
          <Link href="/faq" className="hover:text-foreground">FAQ</Link>
          <Link href="/privacy" className="hover:text-foreground">Privacy</Link>
          <Link href="/insights" className="hover:text-foreground">Insights</Link>
        </nav>
      </div>
    </footer>
  )
}
