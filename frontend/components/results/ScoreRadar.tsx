'use client'

import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'
import type { SessionScore } from '@/types'

interface ScoreRadarProps {
  score: SessionScore
}

export function ScoreRadar({ score }: ScoreRadarProps) {
  const data = [
    { dimension: 'Eng. Skill', value: score.engineering_skill ?? 0 },
    { dimension: 'AI Collab.', value: score.ai_collaboration ?? 0 },
    { dimension: 'AI Trust', value: score.ai_trust_calibration ?? 0 },
    { dimension: 'Judgement', value: score.engineering_judgement ?? 0 },
  ]

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
        <Tooltip formatter={(v: number) => [`${Math.round(v)}`, 'Score']} />
        <Radar
          dataKey="value"
          stroke="hsl(var(--primary))"
          fill="hsl(var(--primary))"
          fillOpacity={0.3}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
