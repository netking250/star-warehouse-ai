import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Send, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

export type FeedbackCategory = 'accuracy' | 'helpfulness' | 'tone' | 'speed' | 'other'

interface FeedbackWidgetProps {
  messageId: string
  messageIndex: number
  initialSentiment?: 'up' | 'down' | null
  confidenceScore?: number
  onSubmit: (
    messageId: string,
    sentiment: 'up' | 'down',
    messageIndex: number,
    category?: string,
    comment?: string
  ) => void
  onCancel?: () => void
  autoTrigger?: boolean
}

const CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: 'accuracy', label: '准确性' },
  { value: 'helpfulness', label: '有用性' },
  { value: 'tone', label: '语气态度' },
  { value: 'speed', label: '响应速度' },
  { value: 'other', label: '其他' },
]

export function FeedbackWidget({
  messageId,
  messageIndex,
  initialSentiment,
  confidenceScore,
  onSubmit,
  onCancel,
  autoTrigger = false,
}: FeedbackWidgetProps): React.ReactElement {
  const [selectedSentiment, setSelectedSentiment] = useState<'up' | 'down' | null>(
    initialSentiment ?? null
  )
  const [selectedCategory, setSelectedCategory] = useState<FeedbackCategory | null>(null)
  const [comment, setComment] = useState('')
  const [isExpanded, setIsExpanded] = useState(autoTrigger)

  useEffect(() => {
    if (autoTrigger && confidenceScore !== undefined && confidenceScore < 0.6) {
      setIsExpanded(true)
    }
  }, [autoTrigger, confidenceScore])

  const handleSentimentClick = useCallback((sentiment: 'up' | 'down') => {
    setSelectedSentiment(sentiment)
    setIsExpanded(true)
  }, [])

  const handleSubmit = useCallback(() => {
    if (!selectedSentiment) return
    onSubmit(
      messageId,
      selectedSentiment,
      messageIndex,
      selectedCategory ?? undefined,
      comment.trim() || undefined
    )
    setIsExpanded(false)
  }, [messageId, messageIndex, selectedSentiment, selectedCategory, comment, onSubmit])

  const handleCancel = useCallback(() => {
    setSelectedSentiment(null)
    setSelectedCategory(null)
    setComment('')
    setIsExpanded(false)
    onCancel?.()
  }, [onCancel])

  const isLowConfidence = confidenceScore !== undefined && confidenceScore < 0.6

  return (
    <div className="flex max-w-xl flex-col gap-2">
      {isLowConfidence && (
        <div className="flex items-start gap-2 rounded-[var(--radius-md)] bg-warning/8 px-3 py-2 text-xs leading-5 text-warning">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>此回复置信度较低，可帮助我们改进。</span>
        </div>
      )}

      <div className="flex items-center gap-1" aria-label="回复反馈">
        <span className="mr-1 text-[11px] text-muted-foreground">此回复是否有帮助？</span>
        <Button
          variant="ghost"
          size="icon"
          className={`h-8 w-8 rounded-[var(--radius-sm)] ${
            selectedSentiment === 'up'
              ? 'bg-primary/10 text-primary hover:bg-primary/15'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => handleSentimentClick('up')}
          aria-label="点赞"
          aria-pressed={selectedSentiment === 'up'}
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={`h-8 w-8 rounded-[var(--radius-sm)] ${
            selectedSentiment === 'down'
              ? 'bg-danger/10 text-danger hover:bg-danger/15'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => handleSentimentClick('down')}
          aria-label="点踩"
          aria-pressed={selectedSentiment === 'down'}
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </Button>
      </div>

      {isExpanded && selectedSentiment && (
        <div className="animate-in fade-in slide-in-from-top-1 flex flex-col gap-3 rounded-[var(--radius-lg)] border border-border-subtle bg-surface-elevated p-3 shadow-md duration-200 sm:gap-4 sm:p-4">
          <div className="space-y-2">
            <Label className="text-xs font-medium text-foreground">
              希望我们改进什么？（可选）
            </Label>
            <div className="flex flex-wrap gap-1.5 sm:gap-2">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() =>
                    setSelectedCategory(selectedCategory === cat.value ? null : cat.value)
                  }
                  className={`min-h-7 rounded-[var(--radius-sm)] border px-2.5 py-1 text-xs transition-colors ${
                    selectedCategory === cat.value
                      ? 'border-primary/30 bg-primary/10 text-primary'
                      : 'border-border-subtle bg-surface text-muted-foreground hover:border-border'
                  }`}
                  aria-pressed={selectedCategory === cat.value}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label
              htmlFor={`feedback-comment-${messageId}`}
              className="text-xs font-medium text-foreground"
            >
              详细说明（可选）
            </Label>
            <Textarea
              id={`feedback-comment-${messageId}`}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="请描述您的问题或建议..."
              className="min-h-16 resize-none bg-surface text-xs leading-5 sm:min-h-20"
              maxLength={500}
            />
            <div className="text-right text-xs text-muted-foreground">{comment.length}/500</div>
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={handleCancel} className="text-xs">
              <X className="mr-1 h-3 w-3" />
              取消
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              className="text-xs"
              disabled={!selectedSentiment}
            >
              <Send className="mr-1 h-3 w-3" />
              提交反馈
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
