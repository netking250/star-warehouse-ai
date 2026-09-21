import { ArrowUp, Loader2, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onCancel?: () => void
  isLoading: boolean
  placeholder?: string
}

/** Render the customer composer with keyboard and safety affordances. */
export function ChatInput({
  value,
  onChange,
  onSend,
  onCancel,
  isLoading,
  placeholder,
}: ChatInputProps): React.ReactElement {
  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }

  return (
    <div className="relative z-20 shrink-0 bg-gradient-to-t from-background via-background/98 via-70% to-transparent px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-5 sm:px-8 sm:pb-6">
      <div className="mx-auto max-w-[52rem]">
        <div className="glass-panel flex items-end gap-2 rounded-[var(--radius-xl)] border p-2 shadow-lg transition-[border-color,box-shadow,background-color] duration-200 focus-within:border-primary/30 focus-within:shadow-[var(--shadow-lg)] focus-within:ring-2 focus-within:ring-ring/25">
          <Textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || '输入消息...'}
            disabled={isLoading}
            aria-label="消息输入"
            className="max-h-[180px] min-h-[48px] flex-1 resize-none border-0 bg-transparent px-3 py-3 text-[15px] leading-6 shadow-none focus-visible:ring-0"
            rows={1}
          />
          <Button
            type="button"
            onClick={isLoading ? onCancel : onSend}
            disabled={!isLoading && !value.trim()}
            aria-label={isLoading ? '停止生成' : '发送消息'}
            title={isLoading ? '停止生成' : '发送消息'}
            className={`mb-0.5 h-10 w-10 shrink-0 rounded-[var(--radius-md)] p-0 shadow-md ${
              isLoading
                ? 'border border-danger/20 bg-danger/10 text-danger hover:bg-danger/15'
                : 'bg-[image:var(--gradient-primary)]'
            }`}
          >
            {isLoading ? (
              onCancel ? (
                <Square className="h-3.5 w-3.5" />
              ) : (
                <Loader2 className="h-4 w-4 animate-spin" />
              )
            ) : (
              <ArrowUp className="h-4 w-4" />
            )}
          </Button>
        </div>
        <p className="mt-2 text-center text-[10px] leading-4 text-muted-foreground sm:text-xs">
          星仓 AI 可能会出错，重要信息请核对确认 · Enter 发送，Shift + Enter 换行
        </p>
      </div>
    </div>
  )
}
