import type { HTMLAttributes, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

interface PageHeaderProps {
  eyebrow: string
  title: string
  description: string
  status?: ReactNode
  actions?: ReactNode
}

/** Stable operational heading shared by every active Admin workspace. */
export function PageHeader({
  eyebrow,
  title,
  description,
  status,
  actions,
}: PageHeaderProps): React.ReactElement {
  return (
    <header className="flex flex-col justify-between gap-5 border-b border-border-subtle pb-6 md:flex-row md:items-end">
      <div className="min-w-0">
        <p className="text-caption uppercase tracking-[0.2em] text-primary">{eyebrow}</p>
        <h1 className="mt-2 text-page-title text-foreground">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
        {status && <div className="mt-3 flex flex-wrap items-center gap-2">{status}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export function SectionHeader({
  title,
  description,
  icon: Icon,
  action,
}: {
  title: string
  description?: string
  icon?: LucideIcon
  action?: ReactNode
}): React.ReactElement {
  return (
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
      <div className="flex min-w-0 gap-3">
        {Icon && (
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-primary/15 bg-primary/[0.07] text-primary">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
        )}
        <div>
          <h2 className="text-section-title text-foreground">{title}</h2>
          {description && (
            <p className="mt-1 text-sm leading-5 text-muted-foreground">{description}</p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function DataPanel({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return (
    <section
      className={cn(
        'rounded-lg border border-border-subtle bg-surface/88 shadow-sm backdrop-blur-[2px]',
        className
      )}
      {...props}
    >
      {children}
    </section>
  )
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = 'info',
}: {
  label: string
  value: ReactNode
  detail: string
  icon: LucideIcon
  tone?: StatusTone
}): React.ReactElement {
  return (
    <DataPanel className="group relative min-h-32 overflow-hidden p-5 transition-[border-color,box-shadow,transform] duration-150 hover:-translate-y-px hover:border-primary/20 hover:shadow-md">
      <div
        aria-hidden="true"
        className={cn(
          'absolute inset-x-0 top-0 h-px',
          tone === 'success' && 'bg-success/55',
          tone === 'warning' && 'bg-warning/55',
          tone === 'danger' && 'bg-danger/55',
          tone === 'info' && 'bg-info/55',
          tone === 'neutral' && 'bg-border'
        )}
      />
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-caption uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
          <p className="numeric mt-3 text-2xl font-semibold tracking-[-0.035em] text-foreground">
            {value}
          </p>
          <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{detail}</p>
        </div>
        <span
          className={cn(
            'grid h-9 w-9 shrink-0 place-items-center rounded-md border',
            tone === 'success' && 'border-success/20 bg-success/10 text-success',
            tone === 'warning' && 'border-warning/20 bg-warning/10 text-warning',
            tone === 'danger' && 'border-danger/20 bg-danger/10 text-danger',
            tone === 'info' && 'border-info/20 bg-info/10 text-info',
            tone === 'neutral' && 'border-border bg-muted text-muted-foreground'
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
    </DataPanel>
  )
}

export function StatusBadge({
  tone = 'neutral',
  children,
  pulse = false,
  className,
}: {
  tone?: StatusTone
  children: ReactNode
  pulse?: boolean
  className?: string
}): React.ReactElement {
  return (
    <span
      className={cn(
        'inline-flex w-fit items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold leading-none',
        tone === 'success' && 'border-success/20 bg-success/10 text-success',
        tone === 'warning' && 'border-warning/20 bg-warning/10 text-warning',
        tone === 'danger' && 'border-danger/20 bg-danger/10 text-danger',
        tone === 'info' && 'border-info/20 bg-info/10 text-info',
        tone === 'neutral' && 'border-border bg-muted/70 text-muted-foreground',
        className
      )}
    >
      <span
        className={cn('h-1.5 w-1.5 rounded-full bg-current', pulse && 'motion-safe:animate-pulse')}
        aria-hidden="true"
      />
      {children}
    </span>
  )
}

export function FilterBar({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return (
    <div
      className={cn(
        'flex flex-wrap items-end gap-3 rounded-lg border border-border-subtle bg-surface/72 p-3 shadow-sm',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function DataTableShell({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return (
    <div
      className={cn('overflow-x-auto rounded-md border border-border-subtle', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export const adminTableClassName =
  'w-full text-left text-sm [&_thead]:bg-muted/45 [&_thead]:text-[11px] [&_thead]:uppercase [&_thead]:tracking-[0.08em] [&_thead]:text-muted-foreground [&_th]:h-10 [&_th]:px-3 [&_th]:font-medium [&_td]:px-3 [&_td]:py-3 [&_tbody_tr]:border-t [&_tbody_tr]:border-border-subtle [&_tbody_tr]:transition-colors [&_tbody_tr:hover]:bg-muted/35'
