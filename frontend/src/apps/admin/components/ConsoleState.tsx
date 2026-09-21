import { AlertCircle, Inbox, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { getConsoleErrorMessage } from '@/lib/console-errors'
import { DataPanel } from './AdminPrimitives'

export function ConsolePageSkeleton(): React.ReactElement {
  return (
    <div className="space-y-6" aria-label="Loading console data" aria-busy="true">
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-32" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  )
}

export function ConsoleEmptyState({
  title,
  description,
}: {
  title: string
  description: string
}): React.ReactElement {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 text-center">
      <span className="mb-3 grid h-9 w-9 place-items-center rounded-md border border-border-subtle bg-surface-elevated text-muted-foreground">
        <Inbox className="h-4 w-4" aria-hidden="true" />
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

export function ConsoleErrorState({
  error,
  onRetry,
}: {
  error: unknown
  onRetry?: () => void
}): React.ReactElement {
  return (
    <DataPanel className="border-danger/20 bg-danger/[0.055] p-5">
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold text-foreground">Unable to load this view</p>
          <p className="mt-1 text-sm text-danger">{getConsoleErrorMessage(error)}</p>
        </div>
      </div>
      {onRetry && (
        <div className="mt-4 pl-8">
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry
          </Button>
        </div>
      )}
    </DataPanel>
  )
}

export function ConsoleSectionLabel({
  children,
}: {
  children: React.ReactNode
}): React.ReactElement {
  return (
    <p className="text-caption uppercase tracking-[0.18em] text-muted-foreground">{children}</p>
  )
}
