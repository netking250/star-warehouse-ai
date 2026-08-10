import { ArrowUp, Loader2, Paperclip, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  isLoading: boolean
  placeholder?: string
}

/** Render the customer composer with keyboard and safety affordances. */
export function ChatInput({
  value,
  onChange,
  onSend,
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
    <div className="relative z-20 shrink-0 bg-gradient-to-t from-[#f5f7fb] via-[#f5f7fb] to-transparent px-4 pb-4 pt-3 sm:px-8 sm:pb-6">
      <div className="mx-auto max-w-4xl">
        <div className="glass-panel flex items-end gap-2 rounded-2xl border border-white p-2 shadow-[0_16px_50px_-22px_rgba(15,23,42,0.28)] ring-1 ring-slate-200/70 transition focus-within:ring-2 focus-within:ring-indigo-300">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="mb-0.5 shrink-0 rounded-xl text-slate-400 hover:bg-slate-100 hover:text-indigo-600"
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
            onClick={onSend}
            disabled={isLoading || !value.trim()}
            aria-label="发送消息"
            className="mb-0.5 h-10 w-10 shrink-0 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 p-0 shadow-md shadow-indigo-200"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowUp className="h-4 w-4" />
            )}
          </Button>
        </div>
        <div className="mt-2 flex items-center justify-center gap-1.5 text-[10px] text-slate-400 sm:text-xs">
          <ShieldCheck className="h-3 w-3 text-emerald-500" />
          星仓AI可能会出错，重要操作请核对确认 · Enter 发送
        </div>
      </div>
    </div>
  )
}
