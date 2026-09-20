import { cn } from '@/lib/utils'

/** Render the shared, non-interactive atmospheric field behind both applications. */
export function AppBackground({ className }: { className?: string }): React.ReactElement {
  return (
    <div
      aria-hidden="true"
      className={cn('pointer-events-none fixed inset-0 z-0 overflow-hidden', className)}
    >
      <div className="ambient-field absolute inset-0" />
      <div className="ambient-orbit ambient-orbit-a" />
      <div className="ambient-orbit ambient-orbit-b" />
      <div className="ambient-grid absolute inset-0" />
      <div className="ambient-stars absolute inset-0" />
    </div>
  )
}

export function AppSurface({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return <div className={cn('app-surface', className)}>{children}</div>
}

export function GlassPanel({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return <div className={cn('glass-panel', className)}>{children}</div>
}

export function PageContainer({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return <div className={cn('mx-auto w-full max-w-[1440px]', className)}>{children}</div>
}

export function PageTransition({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return <div className={cn('page-enter', className)}>{children}</div>
}
