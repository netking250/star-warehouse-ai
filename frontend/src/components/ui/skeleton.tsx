import { cn } from '@/lib/utils'

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-gradient-to-r from-muted via-surface-elevated to-muted bg-[length:220%_100%]',
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
