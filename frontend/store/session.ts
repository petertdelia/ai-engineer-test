import { create } from 'zustand'
import type { AIInteraction, AssessmentSession, SessionQuestion } from '@/types'

interface ExamState {
  session: AssessmentSession | null
  currentIndex: number
  drafts: Record<number, string>        // question_id → draft response_text
  codeDrafts: Record<number, string>    // question_id → draft code_response
  chatHistories: Record<number, AIInteraction[]>  // question_id → local chat history
  streamingMessage: string              // token buffer for in-progress AI response

  setSession: (s: AssessmentSession) => void
  setCurrentIndex: (i: number) => void
  setDraft: (questionId: number, text: string) => void
  setCodeDraft: (questionId: number, code: string) => void
  appendChatMessage: (questionId: number, msg: AIInteraction) => void
  appendStreamToken: (token: string) => void
  flushStreamingMessage: (questionId: number) => void
  markSubmitted: (questionId: number) => void
  reset: () => void
}

const initial = {
  session: null,
  currentIndex: 0,
  drafts: {},
  codeDrafts: {},
  chatHistories: {},
  streamingMessage: '',
}

export const useExamStore = create<ExamState>((set, get) => ({
  ...initial,

  setSession: (session) => {
    // Hydrate drafts and chat histories from server state on recovery
    const drafts: Record<number, string> = {}
    const codeDrafts: Record<number, string> = {}
    const chatHistories: Record<number, AIInteraction[]> = {}

    for (const sq of session.questions) {
      if (sq.response_text) drafts[sq.question_id] = sq.response_text
      if (sq.code_response) codeDrafts[sq.question_id] = sq.code_response
      chatHistories[sq.question_id] = sq.ai_interactions ?? []
    }

    set({ session, drafts, codeDrafts, chatHistories })
  },

  setCurrentIndex: (currentIndex) => set({ currentIndex }),

  setDraft: (questionId, text) =>
    set((s) => ({ drafts: { ...s.drafts, [questionId]: text } })),

  setCodeDraft: (questionId, code) =>
    set((s) => ({ codeDrafts: { ...s.codeDrafts, [questionId]: code } })),

  appendChatMessage: (questionId, msg) =>
    set((s) => ({
      chatHistories: {
        ...s.chatHistories,
        [questionId]: [...(s.chatHistories[questionId] ?? []), msg],
      },
    })),

  appendStreamToken: (token) =>
    set((s) => ({ streamingMessage: s.streamingMessage + token })),

  flushStreamingMessage: (questionId) => {
    const { streamingMessage } = get()
    if (!streamingMessage) return
    set((s) => ({
      chatHistories: {
        ...s.chatHistories,
        [questionId]: [
          ...(s.chatHistories[questionId] ?? []),
          { role: 'assistant', content: streamingMessage, timestamp: new Date().toISOString() },
        ],
      },
      streamingMessage: '',
    }))
  },

  markSubmitted: (questionId) =>
    set((s) => ({
      session: s.session
        ? {
            ...s.session,
            questions: s.session.questions.map((q) =>
              q.question_id === questionId
                ? { ...q, submitted_at: new Date().toISOString() }
                : q,
            ),
          }
        : null,
    })),

  reset: () => set(initial),
}))

export function getSessionStorage(key: string): string | null {
  if (typeof window === 'undefined') return null
  return sessionStorage.getItem(key)
}

export function setSessionStorage(key: string, value: string): void {
  if (typeof window === 'undefined') return
  sessionStorage.setItem(key, value)
}
