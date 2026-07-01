'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useAIChat } from '@/hooks/useAIChat'
import { useExamStore } from '@/store/session'
import { cn } from '@/lib/utils'
import type { AIInteraction } from '@/types'

interface AIAssistantProps {
  sessionId: number
  questionId: number
  disabled?: boolean
}

export function AIAssistant({ sessionId, questionId, disabled }: AIAssistantProps) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const { chatHistories, streamingMessage } = useExamStore()
  const messages = chatHistories[questionId] ?? []

  const { send, isStreaming, error, turnLimitReached, rateLimitRetryAfter } = useAIChat({
    sessionId,
    questionId,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessage])

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || isStreaming) return
    setInput('')
    await send(msg)
  }

  const isBlocked = disabled || turnLimitReached || !!rateLimitRetryAfter

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <Bot className="h-4 w-4" />
        AI Assistant
        <span className="ml-auto text-xs">{messages.length}/15 turns</span>
      </div>

      <div className="flex-1 overflow-y-auto rounded-md border bg-muted/30 p-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <p className="text-xs text-muted-foreground text-center mt-8">
            Ask the assistant to help you think through the problem. It won&apos;t give you the answer — but it can ask useful questions.
          </p>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {isStreaming && streamingMessage && (
          <MessageBubble
            msg={{ role: 'assistant', content: streamingMessage, timestamp: '' }}
            streaming
          />
        )}
        <div ref={bottomRef} />
      </div>

      {turnLimitReached && (
        <p className="text-xs text-muted-foreground text-center">
          You&apos;ve reached the 15-turn limit for this question.
        </p>
      )}
      {rateLimitRetryAfter && (
        <p className="text-xs text-destructive text-center">
          Rate limit reached. Try again in {rateLimitRetryAfter}s.
        </p>
      )}
      {error && !turnLimitReached && !rateLimitRetryAfter && (
        <p className="flex items-center gap-1 text-xs text-destructive">
          <AlertCircle className="h-3 w-3" />{error}
        </p>
      )}

      <div className="flex gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isBlocked ? 'Assistant unavailable' : 'Ask a question…'}
          disabled={isBlocked || isStreaming}
          className="min-h-[60px] resize-none text-sm"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
        />
        <Button size="icon" onClick={handleSend} disabled={isBlocked || isStreaming || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function MessageBubble({ msg, streaming }: { msg: AIInteraction; streaming?: boolean }) {
  const isUser = msg.role === 'user'
  return (
    <div className={cn('flex gap-2', isUser ? 'flex-row-reverse' : 'flex-row')}>
      <div className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs', isUser ? 'bg-primary text-primary-foreground' : 'bg-secondary')}>
        {isUser ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
      </div>
      <div className={cn('max-w-[85%] rounded-lg px-3 py-2 text-sm', isUser ? 'bg-primary text-primary-foreground' : 'bg-card border', streaming && 'after:animate-pulse after:content-["▍"]')}>
        {msg.content}
      </div>
    </div>
  )
}
