import { cn } from '@/lib/utils'

interface BrandMarkProps {
  className?: string
}

interface StarWarehouseLogoProps {
  compact?: boolean
  inverse?: boolean
  className?: string
}

/** Render the abstract Star + data grid + AI core motif. */
export function BrandMark({ className }: BrandMarkProps): React.ReactElement {
  return (
    <svg viewBox="0 0 48 48" fill="none" aria-hidden="true" className={cn('brand-mark', className)}>
      <path d="M11 16.5 24 9l13 7.5v15L24 39l-13-7.5v-15Z" className="brand-mark-grid" />
      <path
        d="m11 16.5 13 7.3 13-7.3M24 9v14.8M11 31.5l13-7.7 13 7.7M24 23.8V39"
        className="brand-mark-grid"
      />
      <ellipse cx="24" cy="24" rx="20" ry="8.5" className="brand-mark-orbit" />
      <ellipse
        cx="24"
        cy="24"
        rx="20"
        ry="8.5"
        transform="rotate(60 24 24)"
        className="brand-mark-orbit brand-mark-orbit-muted"
      />
      <circle cx="24" cy="24" r="5.5" className="brand-mark-core-halo" />
      <circle cx="24" cy="24" r="2.75" className="brand-mark-core" />
      <circle cx="43" cy="24" r="1.35" className="brand-mark-node" />
      <circle cx="14.5" cy="7.6" r="1" className="brand-mark-node brand-mark-node-muted" />
    </svg>
  )
}

/** Render the shared Star Warehouse AI brand identity. */
export function StarWarehouseLogo({
  compact = false,
  inverse = false,
  className,
}: StarWarehouseLogoProps): React.ReactElement {
  return (
    <div className={cn('flex items-center gap-3', className)} aria-label="星仓 AI 智能客服">
      <div
        className={cn(
          'brand-mark-shell relative grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-md)]',
          inverse && 'brand-mark-shell-inverse'
        )}
      >
        <BrandMark className="h-8 w-8" />
      </div>
      {!compact && (
        <div className="min-w-0 leading-none">
          <div
            className={cn(
              'text-[15px] font-semibold tracking-[-0.02em] text-foreground',
              inverse && 'text-white'
            )}
          >
            星仓 <span className={cn('text-primary', inverse && 'text-cyan-200')}>AI</span>
          </div>
          <div
            className={cn(
              'mt-1.5 text-[9px] font-semibold uppercase tracking-[0.2em] text-muted-foreground',
              inverse && 'text-white/48'
            )}
          >
            Intelligent Service
          </div>
        </div>
      )}
    </div>
  )
}
