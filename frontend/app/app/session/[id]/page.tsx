'use client'

import { useEffect, useCallback, use } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { Timer } from '@/components/exam/Timer'
import { QuestionPanel } from '@/components/exam/QuestionPanel'
import { ResponseEditor } from '@/components/exam/ResponseEditor'
import { AIAssistant } from '@/components/exam/AIAssistant'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useExamSession } from '@/hooks/useExamSession'
import { useExamStore } from '@/store/session'
import { apiClientFetch } from '@/lib/api-client'
import { ChevronLeft, ChevronRight, CheckSquare } from 'lucide-react'

export default function ExamSessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const sessionId = parseInt(id)
  const { data: authSession } = useSession()
  const router = useRouter()
  const accessToken = (authSession as any)?.accessToken as string | undefined

  const { session, emitEvent, abandon } = useExamSession(sessionId)
  const { currentIndex, setCurrentIndex, markSubmitted, drafts } = useExamStore()

  // Leave-page integrity tracking
  useEffect(() => {
    const onBlur = () => emitEvent('tab_blur')
    const onFocus = () => emitEvent('return_to_page')
    const onUnload = () => {
      emitEvent('leave_page')
      abandon()
    }

    document.addEventListener('visibilitychange', () =>
      document.hidden ? onBlur() : onFocus())
    window.addEventListener('beforeunload', onUnload)
    return () => {
      document.removeEventListener('visibilitychange', () => {})
      window.removeEventListener('beforeunload', onUnload)
    }
  }, [emitEvent, abandon])

  const handleExpire = useCallback(async () => {
    if (!session || !accessToken) return
    await apiClientFetch(`/sessions/${sessionId}/complete`, accessToken, { method: 'POST' })
      .catch(() => {})
    router.push(`/app/session/${sessionId}/results`)
  }, [session, accessToken, sessionId, router])

  const handleSubmitQuestion = async () => {
    if (!session || !accessToken) return
    const sq = session.questions[currentIndex]
    const draft = drafts[sq.question_id] ?? ''
    await apiClientFetch(
      `/sessions/${sessionId}/questions/${sq.id}/respond`,
      accessToken,
      { method: 'POST', body: JSON.stringify({ response_text: draft }) },
    ).catch(() => {})
    markSubmitted(sq.question_id)
  }

  const handleComplete = async () => {
    if (!session || !accessToken) return
    await apiClientFetch(`/sessions/${sessionId}/complete`, accessToken, { method: 'POST' })
    router.push(`/app/session/${sessionId}/results`)
  }

  const handlePaste = () => {
    if (!session) return
    emitEvent('copy_paste', { question_id: session.questions[currentIndex]?.question_id })
  }

  if (!session) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        Loading session…
      </div>
    )
  }

  const sq = session.questions[currentIndex]
  if (!sq) return null

  const isLastQuestion = currentIndex === session.questions.length - 1
  const allSubmitted = session.questions.every((q) => !!q.submitted_at)

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b px-4 py-2 shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{session.mode}</Badge>
          <span className="text-sm text-muted-foreground">
            {currentIndex + 1} / {session.questions.length}
          </span>
        </div>
        <Timer
          startedAt={session.started_at}
          timeLimitSeconds={session.time_limit_seconds}
          onExpire={handleExpire}
        />
        <Button
          size="sm"
          onClick={handleComplete}
          disabled={!allSubmitted}
          title={allSubmitted ? 'Submit exam' : 'Submit all questions first'}
        >
          <CheckSquare className="mr-1 h-4 w-4" />
          Submit exam
        </Button>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: question + editor */}
        <div className="flex w-3/5 flex-col gap-4 overflow-y-auto border-r p-4">
          <QuestionPanel
            question={sq.question}
            index={currentIndex}
            total={session.questions.length}
          />
          <ResponseEditor
            sessionId={sessionId}
            questionId={sq.question_id}
            submitted={!!sq.submitted_at}
            onPaste={handlePaste}
          />
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex(currentIndex - 1)}
              >
                <ChevronLeft className="h-4 w-4" /> Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={isLastQuestion}
                onClick={() => setCurrentIndex(currentIndex + 1)}
              >
                Next <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            {!sq.submitted_at && (
              <Button size="sm" onClick={handleSubmitQuestion}>
                Submit answer
              </Button>
            )}
          </div>
        </div>

        {/* Right: AI assistant */}
        <div className="flex w-2/5 flex-col p-4">
          <AIAssistant
            sessionId={sessionId}
            questionId={sq.question_id}
            disabled={session.ai_assistant_disabled}
          />
        </div>
      </div>
    </div>
  )
}
