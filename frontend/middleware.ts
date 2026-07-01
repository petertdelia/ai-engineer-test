import { auth } from './lib/auth'
import { NextResponse } from 'next/server'

export default auth((req) => {
  const { nextUrl, auth: session } = req as any
  const isLoggedIn = !!session

  const isAppRoute = nextUrl.pathname.startsWith('/app')
  const isAdminRoute = nextUrl.pathname.startsWith('/admin')

  if ((isAppRoute || isAdminRoute) && !isLoggedIn) {
    return NextResponse.redirect(
      new URL(`/login?callbackUrl=${encodeURIComponent(nextUrl.pathname)}`, nextUrl),
    )
  }

  if (isAdminRoute && !session?.user?.is_admin) {
    return NextResponse.redirect(new URL('/app/dashboard', nextUrl))
  }

  return NextResponse.next()
})

export const config = {
  matcher: ['/app/:path*', '/admin/:path*'],
}
