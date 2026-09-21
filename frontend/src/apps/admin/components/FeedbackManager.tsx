import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useFeedbackList,
  useExportFeedback,
  useCSATTrend,
  useRunQualityScore,
} from '@/hooks/useFeedback'
import type { FeedbackFilters } from '@/types'
import {
  MessageSquare,
  Download,
  Play,
  ChevronLeft,
  ChevronRight,
  Star,
  Signal,
} from 'lucide-react'
import { FilterBar, PageHeader, StatusBadge } from './AdminPrimitives'

function formatDate(iso: string | null | undefined) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

function ScoreBadge({ score }: { score: number | null | undefined }) {
  if (score == null) {
    return (
      <Badge variant="outline" className="flex items-center gap-1 w-fit">
        <Star className="h-3 w-3" />-
      </Badge>
    )
  }

  let variant: 'default' | 'secondary' | 'destructive' | 'outline' = 'default'
  if (score >= 4) variant = 'default'
  else if (score === 3) variant = 'secondary'
  else variant = 'destructive'

  return (
    <Badge variant={variant} className="flex w-fit items-center gap-1">
      <Star className="h-3 w-3" />
      {score}
    </Badge>
  )
}

export function FeedbackManager() {
  const [filters, setFilters] = useState<FeedbackFilters>({
    sentiment: undefined,
    date_from: undefined,
    date_to: undefined,
    offset: 0,
    limit: 20,
  })
  const [sampleSize, setSampleSize] = useState<number>(50)

  const { data: listData, isLoading: isListLoading, error: listError } = useFeedbackList(filters)
  const { mutateAsync: exportFeedback, isPending: isExporting } = useExportFeedback()
  const { data: csatData, isLoading: isCsatLoading } = useCSATTrend(30)
  const { mutateAsync: runQualityScore, isPending: isRunningQualityScore } = useRunQualityScore()

  const handleFilterChange = (
    key: keyof FeedbackFilters,
    value: FeedbackFilters[keyof FeedbackFilters]
  ) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      offset: 0,
    }))
  }

  const handlePrev = () => {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(0, (prev.offset || 0) - (prev.limit || 20)),
    }))
  }

  const handleNext = () => {
    const total = listData?.total ?? 0
    const offset = listData?.offset ?? 0
    const limit = listData?.limit ?? 20
    if (offset + limit < total) {
      setFilters((prev) => ({
        ...prev,
        offset: (prev.offset || 0) + (prev.limit || 20),
      }))
    }
  }

  const handleExport = async () => {
    const result = await exportFeedback(filters)
    const blob = new Blob([result.content], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = result.filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const handleRunQualityScore = async () => {
    await runQualityScore({ sample_size: sampleSize })
  }

  const items = listData?.items ?? []
  const total = listData?.total ?? 0
  const offset = listData?.offset ?? 0
  const limit = listData?.limit ?? 20

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Feedback"
        title="Quality signals"
        description="Review real customer feedback, isolate actionable negative signals, and run the existing bounded quality-scoring workflow."
        status={
          <StatusBadge
            tone={
              items.some((item) => item.score != null && item.score <= 2) ? 'warning' : 'success'
            }
          >
            {total} feedback records
          </StatusBadge>
        }
        actions={
          <Button variant="outline" onClick={() => void handleExport()} disabled={isExporting}>
            <Download className="h-4 w-4" />
            Export CSV
          </Button>
        }
      />

      <FilterBar>
        <div className="flex items-center gap-2">
          <label htmlFor="feedback-sentiment" className="text-sm font-medium">
            Sentiment
          </label>
          <select
            id="feedback-sentiment"
            className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={filters.sentiment || ''}
            onChange={(e) => handleFilterChange('sentiment', e.target.value || undefined)}
          >
            <option value="">All</option>
            <option value="positive">Positive</option>
            <option value="negative">Negative</option>
            <option value="neutral">Neutral</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Date</span>
          <input
            type="date"
            className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={filters.date_from || ''}
            onChange={(e) => handleFilterChange('date_from', e.target.value || undefined)}
          />
          <span className="text-sm text-muted-foreground">to</span>
          <input
            type="date"
            className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={filters.date_to || ''}
            onChange={(e) => handleFilterChange('date_to', e.target.value || undefined)}
          />
        </div>

        <div className="flex items-center gap-2 md:ml-auto">
          <label htmlFor="quality-sample" className="text-sm font-medium">
            Sample
          </label>
          <Input
            id="quality-sample"
            type="number"
            min={1}
            max={1000}
            value={sampleSize}
            onChange={(e) => setSampleSize(parseInt(e.target.value) || 0)}
            className="w-24 h-9"
          />
          <Button
            size="sm"
            onClick={() => void handleRunQualityScore()}
            disabled={isRunningQualityScore || sampleSize <= 0}
          >
            <Play className="h-4 w-4" />
            Run quality score
          </Button>
        </div>
      </FilterBar>

      {listError && (
        <Alert variant="destructive" className="shrink-0">
          <AlertDescription>{listError.message}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="min-w-0 overflow-hidden">
          <CardHeader className="border-b border-border-subtle pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquare className="h-4 w-4 text-primary" />
              Feedback review
            </CardTitle>
            <CardDescription>
              Showing {items.length} of {total} records. Low scores are emphasized for review.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-auto p-0">
            {isListLoading ? (
              <div className="p-4 space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20">User</TableHead>
                    <TableHead>Conversation</TableHead>
                    <TableHead className="w-20">Score</TableHead>
                    <TableHead>Comment</TableHead>
                    <TableHead className="w-40">Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow
                      key={item.id}
                      className={
                        item.score != null && item.score <= 2 ? 'bg-danger/[0.035]' : undefined
                      }
                    >
                      <TableCell className="font-medium">{item.user_id}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {item.thread_id}
                      </TableCell>
                      <TableCell>
                        <ScoreBadge score={item.score} />
                      </TableCell>
                      <TableCell className="max-w-xs truncate">
                        {item.comment || <span className="text-muted-foreground">No comment</span>}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {formatDate(item.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                  {items.length === 0 && (
                    <TableRow>
                      <TableCell
                        colSpan={5}
                        className="px-4 py-8 text-center text-muted-foreground"
                      >
                        No feedback records match these filters.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
          <div className="flex items-center justify-between px-4 py-3 border-t shrink-0">
            <div className="text-sm text-muted-foreground">
              Showing {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)} of {total}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrev}
                disabled={offset === 0 || isListLoading}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNext}
                disabled={offset + limit >= total || isListLoading}
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        </Card>

        <div className="min-w-0">
          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border-subtle pb-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <Signal className="h-4 w-4 text-primary" />
                CSAT · 30 days
              </CardTitle>
              <CardDescription>Real daily average score and response count.</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 overflow-auto p-0">
              {isCsatLoading ? (
                <div className="p-4 space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead className="text-right">平均分</TableHead>
                      <TableHead className="text-right">数量</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(csatData?.trend ?? []).map((point) => (
                      <TableRow key={point.date}>
                        <TableCell className="text-xs">{point.date}</TableCell>
                        <TableCell className="text-right text-sm font-medium">
                          {point.avg_score != null ? point.avg_score.toFixed(2) : '-'}
                        </TableCell>
                        <TableCell className="text-right text-xs">{point.count}</TableCell>
                      </TableRow>
                    ))}
                    {(csatData?.trend ?? []).length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={3}
                          className="px-4 py-8 text-center text-muted-foreground"
                        >
                          No CSAT data available.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
