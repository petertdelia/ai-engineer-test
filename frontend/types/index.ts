// Shared domain types — used until openapi-typescript generates types/api.ts

export type Difficulty = 'low' | 'medium' | 'high'
export type SessionMode = 'trial' | 'practice' | 'exam'
export type SessionStatus = 'pending' | 'in_progress' | 'completed' | 'abandoned' | 'flagged'
export type ScoreStatus = 'pending' | 'completed' | 'failed'
export type Category = 'software_engineering' | 'data_science' | 'data_engineering' | 'cyber_security'

export interface User {
  id: number
  email: string
  name: string | null
  avatar_url: string | null
  auth_provider: 'email' | 'google'
  role: 'candidate' | 'admin'
  is_active: boolean
  is_admin: boolean
  is_email_verified: boolean
  is_public_rank: boolean
  created_at: string
}

export interface Question {
  id: number
  title: string
  scenario: string
  supporting_code: string | null
  supporting_logs: string | null
  supporting_metrics: Record<string, unknown> | null
  category: Category
  technologies: string[]
  difficulty: Difficulty
  is_vetted: boolean
  is_active: boolean
  generation_source: 'human' | 'ai_pipeline'
  created_at: string
}

export interface AIInteraction {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface SessionQuestion {
  id: number
  session_id: number
  question_id: number
  order_index: number
  question: Question
  response_text: string | null
  code_response: string | null
  ai_interactions: AIInteraction[]
  started_at: string | null
  submitted_at: string | null
  score_engineering_skill: number | null
  score_ai_collaboration: number | null
  score_ai_trust_calibration: number | null
  score_engineering_judgement: number | null
  scoring_notes: Record<string, string> | null
}

export interface AssessmentSession {
  id: number
  user_id: number
  user?: Pick<User, 'id' | 'email' | 'name'>
  mode: SessionMode
  difficulty: Difficulty
  started_at: string | null
  ended_at: string | null
  time_limit_seconds: number
  status: SessionStatus
  is_flagged_for_review: boolean
  flag_reason: string | null
  ai_assistant_disabled: boolean
  questions: SessionQuestion[]
}

export interface SessionScore {
  id: number
  session_id: number
  status: ScoreStatus
  engineering_skill: number | null
  ai_collaboration: number | null
  ai_trust_calibration: number | null
  engineering_judgement: number | null
  total_score: number | null
  percentile_rank: number | null
  computed_at: string | null
  failure_reason: string | null
}

export interface Certificate {
  id: number
  user_id: number
  session_id: number
  image_url: string
  share_token: string
  linkedin_url: string
  created_at: string
}

export interface SavedTopic {
  id: number
  user_id: number
  topic: string
  created_at: string
}

export interface UserStats {
  technology_breakdown: Array<{
    technology: string
    avg_engineering_skill: number
    avg_ai_collaboration: number
    avg_ai_trust_calibration: number
    avg_engineering_judgement: number
    session_count: number
  }>
  score_trend: Array<{
    session_id: number
    completed_at: string
    total_score: number
  }>
}

export interface PipelineRun {
  id: number
  triggered_by: string
  topic: string | null
  started_at: string
  completed_at: string | null
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  questions_generated: number | null
  error_message: string | null
}

export interface AdminStats {
  total_users: number
  active_users_30d: number
  sessions_today: number
  sessions_30d: number
  avg_total_score: number | null
  certificates_issued: number
  questions_in_bank: number
  vetted_questions: number
  sessions_by_mode: Record<SessionMode, number>
  score_distribution: Record<string, number>
  flagged_sessions_pending: number
}

export interface SessionEvent {
  id: number
  session_id: number
  event_type: 'leave_page' | 'return_to_page' | 'inactivity_warning' | 'tab_blur' | 'copy_paste'
  occurred_at: string
  metadata: Record<string, unknown>
}

export interface ApiError {
  error: string
  message: string
  detail?: Record<string, unknown>
}
