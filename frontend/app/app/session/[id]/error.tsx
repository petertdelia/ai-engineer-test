'use client'

import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useExamStore, setSessionStorage } from '@/store/session'

export default function ExamErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Persist current exam state to sessionStorage for recovery
    const state = useExamStore.getState()
    if (state.session) {
      setSessionStorage(`exam_recovery_${state.session.id}`, JSON.stringify(state))
    }
  }, [])

  return (
    <div className="flex h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Something went wrong</CardTitle>
          <CardDescription>
            Your draft responses have been saved. You can try to resume or submit what you have.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Button onClick={reset}>Try to resume</Button>
          <Button variant="outline" onClick={() => window.history.back()}>
            Go back
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
