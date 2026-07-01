'use client'

import { useEffect, useRef, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { Textarea } from '@/components/ui/textarea'
import { useExamStore } from '@/store/session'
import { apiClientFetch } from '@/lib/api-client'

interface ResponseEditorProps {
  sessionId: number
  questionId: number
  submitted: boolean
  onPaste?: () => void
}

export function ResponseEditor({ sessionId, questionId, submitted, onPaste }: ResponseEditorProps) {
  const { data: authSession } = useSession()
  const { drafts, setDraft } = useExamStore()
  const draft = drafts[questionId] ?? ''
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const autosave = useCallback(
    (text: string) => {
      if (!accessToken) return
      apiClientFetch(
        `/sessions/${sessionId}/questions/${questionId}/autosave`,
        accessToken,
        { method: 'PATCH', body: JSON.stringify({ response_text: text }) },
      ).catch(() => {})
    },
    [sessionId, questionId, accessToken],
  )

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value
    setDraft(questionId, text)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => autosave(text), 2000)
  }

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }, [])

  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium">Your response</label>
      <Textarea
        value={draft}
        onChange={handleChange}
        disabled={submitted}
        placeholder={submitted ? 'Response submitted.' : 'Write your answer here. Use the AI assistant to guide your thinking, but make sure the response reflects your own reasoning.'}
        className="min-h-[220px] resize-none font-mono text-sm"
        onPaste={onPaste}
      />
      {submitted && (
        <p className="text-xs text-muted-foreground">This question has been submitted.</p>
      )}
    </div>
  )
}
