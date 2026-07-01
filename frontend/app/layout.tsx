import type { Metadata } from 'next'
import { ThemeProvider } from 'next-themes'
import { SessionProvider } from 'next-auth/react'
import { auth } from '@/lib/auth'
import './globals.css'

export const metadata: Metadata = {
  title: { default: 'Crucible — AI Engineer Assessment', template: '%s | Crucible' },
  description:
    'The AI-era engineering assessment platform. Prove your skills with real scenarios, a guided AI assistant, and a credible shareable result.',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth()
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <SessionProvider session={session}>
            {children}
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
