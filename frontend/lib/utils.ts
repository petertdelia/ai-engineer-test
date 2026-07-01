import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatScore(score: number | null): string {
  if (score === null) return '—'
  return `${Math.round(score)}`
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function difficultyLabel(d: 'low' | 'medium' | 'high'): string {
  return { low: 'Low', medium: 'Medium', high: 'High' }[d]
}

export function modeLabel(m: 'trial' | 'practice' | 'exam'): string {
  return { trial: 'Trial', practice: 'Practice', exam: 'Exam' }[m]
}

export function categoryLabel(c: string): string {
  return {
    software_engineering: 'Software Engineering',
    data_science: 'Data Science',
    data_engineering: 'Data Engineering',
    cyber_security: 'Cyber Security',
  }[c] ?? c
}
