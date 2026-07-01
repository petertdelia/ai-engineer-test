import NextAuth from 'next-auth'
import Credentials from 'next-auth/providers/credentials'
import Google from 'next-auth/providers/google'
import type { NextAuthConfig } from 'next-auth'

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL ?? 'http://localhost:8000'

async function refreshAccessToken(refreshToken: string) {
  const res = await fetch(`${FASTAPI_BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) return null
  return res.json() as Promise<{ access_token: string; refresh_token: string; expires_in: number }>
}

export const authConfig: NextAuthConfig = {
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    Credentials({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const res = await fetch(`${FASTAPI_BASE_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        })
        if (!res.ok) return null
        const data = await res.json()
        return {
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.name,
          image: data.user.avatar_url,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          accessTokenExpires: Date.now() + data.expires_in * 1000,
          is_admin: data.user.is_admin,
          is_email_verified: data.user.is_email_verified,
        }
      },
    }),
  ],
  callbacks: {
    async signIn({ account, profile }) {
      if (account?.provider === 'google') {
        const res = await fetch(`${FASTAPI_BASE_URL}/auth/google`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: account.id_token }),
        })
        if (!res.ok) return false
        const data = await res.json()
        account.accessToken = data.access_token
        account.refreshToken = data.refresh_token
        account.accessTokenExpires = Date.now() + data.expires_in * 1000
        account.userId = data.user.id
        account.is_admin = data.user.is_admin
        account.is_email_verified = data.user.is_email_verified
      }
      return true
    },

    async jwt({ token, user, account }) {
      // Initial sign-in
      if (user) {
        return {
          ...token,
          accessToken: (user as any).accessToken ?? account?.accessToken,
          refreshToken: (user as any).refreshToken ?? account?.refreshToken,
          accessTokenExpires: (user as any).accessTokenExpires ?? account?.accessTokenExpires,
          is_admin: (user as any).is_admin ?? account?.is_admin,
          is_email_verified: (user as any).is_email_verified ?? account?.is_email_verified,
        }
      }

      // Proactively refresh when within 60s of expiry
      const expiresAt = token.accessTokenExpires as number
      if (Date.now() < expiresAt - 60_000) return token

      const refreshed = await refreshAccessToken(token.refreshToken as string)
      if (!refreshed) {
        return { ...token, error: 'RefreshTokenExpired' }
      }

      return {
        ...token,
        accessToken: refreshed.access_token,
        refreshToken: refreshed.refresh_token,
        accessTokenExpires: Date.now() + refreshed.expires_in * 1000,
        error: undefined,
      }
    },

    async session({ session, token }) {
      return {
        ...session,
        accessToken: token.accessToken as string,
        error: token.error as string | undefined,
        user: {
          ...session.user,
          is_admin: token.is_admin as boolean,
          is_email_verified: token.is_email_verified as boolean,
        },
      }
    },
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  session: { strategy: 'jwt', maxAge: 8 * 60 * 60 },
}

export const { handlers, signIn, signOut, auth } = NextAuth(authConfig)
