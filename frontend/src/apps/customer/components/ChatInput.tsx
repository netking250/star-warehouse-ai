import { ArrowUp, Loader2, Paperclip, ShieldCheck, Square } from 'lucide-react'
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
    <div className="relative z-20 shrink-0 bg-gradient-to-t from-background via-background/95 to-transparent px-4 pb-4 pt-3 sm:px-8 sm:pb-6">
      <div className="mx-auto max-w-4xl">
        <div className="glass-panel flex items-end gap-2 rounded-2xl border p-2 shadow-lg transition focus-within:ring-2 focus-within:ring-ring/35">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="mb-0.5 shrink-0 rounded-xl text-muted-foreground hover:bg-muted hover:text-primary"
            aria-label="添加附件"
            disabled
            title="附件能力将在知识增强版本开放"
          >
            <Paperclip className="h-4 w-4" />
          </Button>
          <Textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || '输入消息...'}
            disabled={isLoading}
            className="max-h-[180px] min-h-[46px] flex-1 resize-none border-0 bg-transparent px-1 py-3 text-sm shadow-none focus-visible:ring-0"
            rows={1}
          />
          <Button
            onClick={isLoading ? onCancel : onSend}
            disabled={!isLoading && !value.trim()}
            aria-label="发送消息"
            className="mb-0.5 h-10 w-10 shrink-0 rounded-xl bg-[image:var(--gradient-primary)] p-0 shadow-md"
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
        <div className="mt-2 flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground sm:text-xs">
          <ShieldCheck className="h-3 w-3 text-success" />
          星仓 AI 可能会出错，重要操作请核对确认 · Enter 发送
        </div>
      </div>
    </div>
  )
}
