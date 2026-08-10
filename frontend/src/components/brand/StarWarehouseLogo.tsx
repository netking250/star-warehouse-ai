import { Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StarWarehouseLogoProps {
  compact?: boolean
  inverse?: boolean
  className?: string
}

/** Render the shared Star Warehouse AI brand mark. */
export function StarWarehouseLogo({
  compact = false,
  inverse = false,
  className,
}: StarWarehouseLogoProps): React.ReactElement {
  return (
    <div className={cn('flex items-center gap-3', className)} aria-label="星仓AI智能客服">
      <div
        className={cn(
          'relative grid h-10 w-10 shrink-0 place-items-center rounded-2xl shadow-[0_10px_30px_-12px_rgba(79,70,229,0.9)]',
          inverse
            ? 'bg-white/15 text-white ring-1 ring-white/25'
            : 'bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-400 text-white'
        )}
      >
        <Sparkles className="h-5 w-5" strokeWidth={2.2} />
        <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-cyan-300" />
      </div>
      {!compact && (
        <div className="min-w-0 leading-none">
          <div className={cn('text-base font-bold tracking-tight', inverse && 'text-white')}>
            星仓
            <span className={cn('ml-1', inverse ? 'text-cyan-200' : 'text-indigo-600')}>AI</span>
          </div>
          <div
            className={cn(
              'mt-1.5 text-[10px] font-medium tracking-[0.18em]',
              inverse ? 'text-indigo-100' : 'text-slate-400'
            )}
          >
            智能客服
          </div>
        </div>
      )}
    </div>
  )
}
