import { useMemo, useRef, useState, type ComponentType } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity,
  Bell,
  BookOpen,
  Bot,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  ShieldCheck,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { StarWarehouseLogo } from '@/components/brand/StarWarehouseLogo'
import { AppBackground, PageContainer, PageTransition } from '@/components/shell/AppShell'
import { ThemeToggle } from '@/components/theme/ThemeToggle'
import { useAuth } from '@/hooks/useAuth'
import { useNotifications } from '@/hooks/useNotifications'
import { useWebSocket } from '@/hooks/useWebSocket'
import { hasAnyCapability, type Capability } from '@/lib/authorization'
import type { User } from '@/types'

interface NavItem {
  href: string
  label: string
  description: string
  icon: ComponentType<{ className?: string }>
  capabilities: readonly Capability[]
}

interface NavGroup {
  label: string
  items: readonly NavItem[]
}

const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: 'Command center',
    items: [
      {
        href: '/',
        label: 'Overview',
        description: 'Current operational posture',
        icon: LayoutDashboard,
        capabilities: [
          'operations.read',
          'reviews.read',
          'conversations.read',
          'identity.read',
          'compliance.read',
          'evaluation.read',
        ],
      },
      {
        href: '/operations',
        label: 'Operations',
        description: 'Review, runtime, and alerts',
        icon: Activity,
        capabilities: ['operations.read', 'reviews.read', 'conversations.read'],
      },
      {
        href: '/ai',
        label: 'AI runtime',
        description: 'Agent configuration and quality',
        icon: Bot,
        capabilities: ['operations.read'],
      },
    ],
  },
  {
    label: 'Control plane',
    items: [
      {
        href: '/security',
        label: 'Security & access',
        description: 'Tenant membership authority',
        icon: ShieldCheck,
        capabilities: ['identity.read'],
      },
      {
        href: '/compliance',
        label: 'Compliance',
        description: 'Approvals and retention',
        icon: ClipboardCheck,
        capabilities: ['compliance.read'],
      },
    ],
  },
  {
    label: 'Existing workspaces',
    items: [
      {
        href: '/knowledge',
        label: 'Knowledge',
        description: 'Tenant knowledge sources',
        icon: BookOpen,
        capabilities: ['knowledge.read'],
      },
      {
        href: '/feedback',
        label: 'Feedback',
        description: 'Quality signals and export requests',
        icon: MessageSquare,
        capabilities: ['operations.read'],
      },
      {
        href: '/metrics',
        label: 'Metrics',
        description: 'Existing quality analytics',
        icon: Activity,
        capabilities: ['operations.read'],
      },
    ],
  },
]

function visibleGroups(user: User | null): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => hasAnyCapability(user, item.capabilities)),
  })).filter((group) => group.items.length > 0)
}

function NavContent({ user, onNavigate }: { user: User | null; onNavigate?: () => void }) {
  const groups = visibleGroups(user)
  return (
    <nav aria-label="Enterprise console navigation" className="space-y-7">
      {groups.map((group) => (
        <div key={group.label}>
          <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/70">
            {group.label}
          </p>
          <div className="space-y-1">
            {group.items.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.href}
                  to={item.href}
                  end={item.href === '/'}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `group flex items-start gap-3 rounded-md border border-transparent px-3 py-2.5 transition-[background-color,border-color,color] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                      isActive
                        ? 'border-primary/15 bg-primary/10 text-foreground shadow-sm'
                        : 'text-muted-foreground hover:bg-muted/55 hover:text-foreground'
                    }`
                  }
                >
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className="mt-0.5 block truncate text-[11px] text-muted-foreground/75 group-hover:text-muted-foreground">
                      {item.description}
                    </span>
                  </span>
                </NavLink>
              )
            })}
          </div>
        </div>
      ))}
    </nav>
  )
}

function NotificationBell({ user }: { user: User | null }): React.ReactElement | null {
  const { notifications, unreadCount, markAsRead, markAllAsRead, handleWsMessage } =
    useNotifications()
  const [open, setOpen] = useState(false)
  const canReceiveNotifications = hasAnyCapability(user, ['operations.read'])
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const socketUrl = `${protocol}//${window.location.host}/api/v1/ws/admin/${user?.user_id ?? ''}`
  useWebSocket({
    url: socketUrl,
    enabled: canReceiveNotifications && user?.user_id !== undefined,
    onMessage: handleWsMessage,
  })

  if (!canReceiveNotifications) return null

  return (
    <div className="relative">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : 'Notifications'}
        onClick={() => setOpen((current) => !current)}
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute right-0 top-0 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-semibold text-danger-foreground">
            {unreadCount}
          </span>
        )}
      </Button>
      {open && (
        <div className="glass-panel absolute right-0 top-11 z-40 w-80 rounded-lg border p-3 shadow-lg">
          <div className="flex items-center justify-between border-b pb-2">
            <p className="text-sm font-semibold text-foreground">Live notifications</p>
            {unreadCount > 0 && (
              <Button type="button" variant="ghost" size="sm" onClick={markAllAsRead}>
                Mark read
              </Button>
            )}
          </div>
          {notifications.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No new notifications.</p>
          ) : (
            <div className="max-h-72 overflow-auto">
              {notifications.slice(0, 12).map((notification) => (
                <button
                  type="button"
                  key={notification.id}
                  className={`block w-full border-b border-border-subtle px-1 py-3 text-left last:border-0 ${notification.read ? '' : 'bg-primary/5'}`}
                  onClick={() => markAsRead(notification.id)}
                >
                  <span className="block text-sm font-medium text-foreground">
                    {notification.title}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {notification.message}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function AdminLayout(): React.ReactElement {
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const shellRef = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const currentRole = useMemo(
    () => user?.roles?.[0]?.replace(/_/g, ' ') ?? 'operator',
    [user?.roles]
  )

  return (
    <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
      <div
        ref={shellRef}
        data-testid="admin-console-shell"
        className="relative min-h-screen bg-background text-foreground"
      >
        <AppBackground />
        <aside className="glass-panel fixed inset-y-0 left-0 z-30 hidden w-72 flex-col border-r border-border-subtle px-4 py-5 lg:flex">
          <div className="flex items-center border-b border-border-subtle px-2 pb-5">
            <StarWarehouseLogo />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto py-6">
            <NavContent user={user} />
          </div>
          <div className="border-t border-border-subtle pt-4">
            <div className="rounded-lg border border-success/15 bg-success/[0.055] p-3">
              <div className="flex items-center gap-2 text-xs text-success">
                <span className="h-2 w-2 rounded-full bg-success" aria-hidden="true" />
                Session protected
              </div>
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Server-authoritative access
              </p>
            </div>
          </div>
        </aside>

        <SheetContent
          aria-describedby={undefined}
          closeLabel="Close navigation"
          className="glass-panel left-0 right-auto flex w-80 max-w-[85vw] flex-col gap-0 border-l-0 border-r border-border-subtle px-4 py-5 shadow-lg data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:max-w-[20rem] lg:hidden"
        >
          <SheetTitle className="sr-only">Enterprise console navigation</SheetTitle>
          <div className="flex items-center border-b border-border-subtle px-2 pb-5">
            <StarWarehouseLogo />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto py-6">
            <NavContent user={user} onNavigate={() => setMobileOpen(false)} />
          </div>
        </SheetContent>

        <div className="relative z-10 lg:pl-72">
          <header className="glass-panel sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-border-subtle px-4 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <SheetTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="lg:hidden"
                  aria-label="Open navigation"
                >
                  <Menu className="h-5 w-5" aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold tracking-tight text-foreground">
                  Enterprise console
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  Operate Star Warehouse AI with explainable controls
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:gap-4">
              <div className="hidden items-center gap-2 text-right sm:flex">
                <p className="max-w-32 truncate text-sm font-medium text-foreground">
                  {user?.full_name || user?.username}
                </p>
                <Badge variant="secondary" className="capitalize">
                  {currentRole}
                </Badge>
                <p className="text-[11px] text-muted-foreground">
                  Tenant {user?.tenant_id ?? 'current'}
                </p>
              </div>
              <ThemeToggle />
              <NotificationBell user={user} />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                data-testid="logout-button"
                onClick={() => void logout()}
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">Sign out</span>
              </Button>
            </div>
          </header>

          <main className="admin-content min-h-[calc(100vh-72px)] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            <PageContainer>
              <PageTransition key={location.pathname}>
                <Outlet />
              </PageTransition>
            </PageContainer>
          </main>
        </div>
      </div>
    </Sheet>
  )
}
