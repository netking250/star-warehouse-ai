import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { ArrowLeft, LockKeyhole } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { useAuthStore } from '@/stores/auth'
import { hasAnyCapability, type Capability } from '@/lib/authorization'
import { ConsolePageSkeleton } from './ConsoleState'

export function SessionRoute(): React.ReactElement {
  useAuth()
  const { isAuthenticated, isInitialized } = useAuthStore()
  const location = useLocation()

  if (!isInitialized) return <ConsolePageSkeleton />
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

export function AccessDeniedPage({
  capabilities,
}: {
  capabilities: readonly Capability[]
}): React.ReactElement {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-xl items-center justify-center">
      <Card className="w-full border-amber-200 bg-amber-50/60">
        <CardHeader>
          <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-amber-100 text-amber-700">
            <LockKeyhole className="h-5 w-5" aria-hidden="true" />
          </div>
          <CardTitle>Access not granted</CardTitle>
          <p className="text-sm text-amber-900/80">
            Your authenticated session is valid, but its current capabilities do not include this
            console area.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-amber-900/70">
            Required capability: {capabilities.join(' or ')}
          </p>
          <Button type="button" variant="outline" asChild>
            <Link to="/">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Return to overview
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

export function CapabilityRoute({
  capabilities,
  children,
}: {
  capabilities: readonly Capability[]
  children: React.ReactNode
}): React.ReactElement {
  const { user } = useAuthStore()
  if (!hasAnyCapability(user, capabilities)) return <AccessDeniedPage capabilities={capabilities} />
  return <>{children}</>
}
