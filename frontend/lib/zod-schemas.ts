import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

export const registerSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

export const forgotPasswordSchema = z.object({
  email: z.string().email('Enter a valid email'),
})

export const resetPasswordSchema = z
  .object({
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

export const profileSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
})

export const topicSchema = z.object({
  topic_name: z.string().min(1, 'Topic name is required'),
  study_url: z.string().url('Enter a valid URL'),
})

export const questionSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  scenario: z.string().min(1, 'Scenario is required'),
  supporting_code: z.string().optional(),
  supporting_logs: z.string().optional(),
  category: z.enum(['software_engineering', 'data_science', 'data_engineering', 'cyber_security']),
  technologies: z.string().min(1, 'At least one technology is required'),
  difficulty: z.enum(['low', 'medium', 'high']),
})

export type LoginInput = z.infer<typeof loginSchema>
export type RegisterInput = z.infer<typeof registerSchema>
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>
export type ProfileInput = z.infer<typeof profileSchema>
export type TopicInput = z.infer<typeof topicSchema>
export type QuestionInput = z.infer<typeof questionSchema>
