'use client'

import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@radix-ui/react-tabs'
import { Badge } from '@/components/ui/badge'
import { cn, categoryLabel, difficultyLabel } from '@/lib/utils'
import type { Question } from '@/types'

interface QuestionPanelProps {
  question: Question
  index: number
  total: number
}

export function QuestionPanel({ question, index, total }: QuestionPanelProps) {
  const hasCode = !!question.supporting_code
  const hasLogs = !!question.supporting_logs
  const hasMetrics = !!question.supporting_metrics

  const tabs = [
    { value: 'scenario', label: 'Scenario', always: true },
    { value: 'code', label: 'Code', always: false, show: hasCode },
    { value: 'logs', label: 'Logs', always: false, show: hasLogs },
    { value: 'metrics', label: 'Metrics', always: false, show: hasMetrics },
  ].filter((t) => t.always || t.show)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Question {index + 1} of {total}</span>
          <Badge variant="outline">{categoryLabel(question.category)}</Badge>
          <Badge variant="secondary">{difficultyLabel(question.difficulty)}</Badge>
          {question.technologies.map((t) => (
            <Badge key={t} variant="outline" className="font-mono text-xs">{t}</Badge>
          ))}
        </div>
      </div>

      <h2 className="text-xl font-semibold">{question.title}</h2>

      <Tabs defaultValue="scenario">
        <TabsList className="mb-3 flex gap-1 border-b">
          {tabs.map(({ value, label }) => (
            <TabsTrigger
              key={value}
              value={value}
              className={cn(
                'px-3 py-1.5 text-sm font-medium transition-colors',
                'data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:text-foreground',
                'text-muted-foreground hover:text-foreground',
              )}
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="scenario">
          <p className="whitespace-pre-wrap leading-relaxed">{question.scenario}</p>
        </TabsContent>

        {hasCode && (
          <TabsContent value="code">
            <pre className="overflow-x-auto rounded-md bg-muted p-4 text-sm">
              <code>{question.supporting_code}</code>
            </pre>
          </TabsContent>
        )}

        {hasLogs && (
          <TabsContent value="logs">
            <pre className="overflow-x-auto rounded-md bg-muted p-4 font-mono text-xs leading-relaxed">
              {question.supporting_logs}
            </pre>
          </TabsContent>
        )}

        {hasMetrics && (
          <TabsContent value="metrics">
            <pre className="overflow-x-auto rounded-md bg-muted p-4 text-sm">
              {JSON.stringify(question.supporting_metrics, null, 2)}
            </pre>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
