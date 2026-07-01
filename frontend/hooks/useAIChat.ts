'use client'

import { useState, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { buildUrl } from '@/lib/api-client'
import { useExamStore } from '@/store/session'

interface UseAIChatOptions {
  sessionId: number
  questionId: number
}

export function useAIChat({ sessionId, questionId }: UseAIChatOptions) {
  const { data: session } = useSession()
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [turnLimitReached, setTurnLimitReached] = useState(false)
  const [rateLimitRetryAfter, setRateLimitRetryAfter] = useState<number | null>(null)

  const { appendStreamToken, flushStreamingMessage, streamingMessage } = useExamStore()

  const send = useCallback(
    async (message: string) => {
      if (isStreaming || turnLimitReached) return
      setError(null)
      setIsStreaming(true)

      try {
        const accessToken = (session as any)?.accessToken
        const res = await fetch(
          buildUrl(`/sessions/${sessionId}/questions/${questionId}/ai-chat`),
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
            },
            body: JSON.stringify({ message }),
          },
        )

        if (res.status === 429) {
          const body = await res.json().catch(() => ({}))
          if (body.error === 'TURN_LIMIT_REACHED') {
            setTurnLimitReached(true)
          } else {
            const retryAfter = Number(res.headers.get('Retry-After') ?? 60)
            setRateLimitRetryAfter(retryAfter)
            setError(`Rate limit reached. Try again in ${retryAfter}s.`)
          }
          return
        }

        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          setError(body.message ?? 'Something went wrong. Please try again.')
          return
        }

        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() ?? ''
          for (const block of blocks) {
            const data = block.replace(/^data: /, '').trim()
            if (data && data !== '[DONE]') appendStreamToken(data)
          }
        }

        flushStreamingMessage(questionId)
      } catch (err) {
        // Preserve partial streamed content already flushed to state
        setError('Connection lost. Your partial response was saved.')
        flushStreamingMessage(questionId)
      } finally {
        setIsStreaming(false)
      }
    },
    [sessionId, questionId, session, isStreaming, turnLimitReached, appendStreamToken, flushStreamingMessage],
  )

  const clearRateLimit = useCallback(() => setRateLimitRetryAfter(null), [])

  return { send, isStreaming, error, turnLimitReached, rateLimitRetryAfter, clearRateLimit, streamingMessage }
}
