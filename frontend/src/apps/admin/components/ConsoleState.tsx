import { AlertCircle, Inbox, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getConsoleErrorMessage } from '@/lib/console-errors'

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
    <div className="flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed bg-white/60 px-6 text-center">
      <Inbox className="mb-3 h-5 w-5 text-slate-400" aria-hidden="true" />
      <p className="text-sm font-medium text-slate-700">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>
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
    <Card className="border-red-200 bg-red-50/60">
      <CardHeader className="flex-row items-start gap-3 space-y-0">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" aria-hidden="true" />
        <div>
          <CardTitle className="text-base text-red-950">Unable to load this view</CardTitle>
          <p className="mt-1 text-sm text-red-800">{getConsoleErrorMessage(error)}</p>
        </div>
      </CardHeader>
      {onRetry && (
        <CardContent className="pt-0">
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry
          </Button>
        </CardContent>
      )}
    </Card>
  )
}

export function ConsoleSectionLabel({
  children,
}: {
  children: React.ReactNode
}): React.ReactElement {
  return (
    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{children}</p>
  )
}
