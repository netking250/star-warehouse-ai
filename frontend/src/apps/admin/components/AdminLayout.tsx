import { useMemo, useRef, useState, type ComponentType } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
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
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StarWarehouseLogo } from '@/components/brand/StarWarehouseLogo'
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
          <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
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
                    `group flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
                      isActive
                        ? 'bg-indigo-500/15 text-indigo-100'
                        : 'text-slate-400 hover:bg-white/[0.06] hover:text-slate-100'
                    }`
                  }
                >
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className="mt-0.5 block truncate text-[11px] text-slate-500 group-hover:text-slate-400">
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
          <span className="absolute right-0 top-0 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
            {unreadCount}
          </span>
        )}
      </Button>
      {open && (
        <div className="absolute right-0 top-11 z-40 w-80 rounded-xl border bg-white p-3 shadow-xl">
          <div className="flex items-center justify-between border-b pb-2">
            <p className="text-sm font-semibold text-slate-900">Live notifications</p>
            {unreadCount > 0 && (
              <Button type="button" variant="ghost" size="sm" onClick={markAllAsRead}>
                Mark read
              </Button>
            )}
          </div>
          {notifications.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">No new notifications.</p>
          ) : (
            <div className="max-h-72 overflow-auto">
              {notifications.slice(0, 12).map((notification) => (
                <button
                  type="button"
                  key={notification.id}
                  className={`block w-full border-b px-1 py-3 text-left last:border-0 ${notification.read ? '' : 'bg-indigo-50/60'}`}
                  onClick={() => markAsRead(notification.id)}
                >
                  <span className="block text-sm font-medium text-slate-800">
                    {notification.title}
                  </span>
                  <span className="mt-1 block text-xs text-slate-500">{notification.message}</span>
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
  const currentRole = useMemo(
    () => user?.roles?.[0]?.replace(/_/g, ' ') ?? 'operator',
    [user?.roles]
  )

  return (
    <div
      ref={shellRef}
      data-testid="admin-console-shell"
      className="min-h-screen bg-[#f4f6fb] text-slate-950"
    >
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col bg-slate-950 px-4 py-5 text-white lg:flex">
        <div className="flex items-center border-b border-white/10 px-2 pb-5">
          <StarWarehouseLogo inverse />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto py-6">
          <NavContent user={user} />
        </div>
        <div className="border-t border-white/10 pt-4">
          <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.06] p-3">
            <div className="flex items-center gap-2 text-xs text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden="true" />
              Session protected
            </div>
            <p className="mt-1.5 text-[11px] text-slate-500">Server-authoritative access</p>
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-slate-950/60"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative flex h-full w-80 max-w-[85vw] flex-col bg-slate-950 px-4 py-5 text-white">
            <div className="flex items-center justify-between border-b border-white/10 px-2 pb-5">
              <StarWarehouseLogo inverse />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="text-slate-300 hover:text-white"
                aria-label="Close navigation"
                onClick={() => setMobileOpen(false)}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto py-6">
              <NavContent user={user} onNavigate={() => setMobileOpen(false)} />
            </div>
          </aside>
        </div>
      )}

      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-slate-200/80 bg-white/90 px-4 shadow-sm backdrop-blur-xl sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </Button>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight text-slate-950">
                Enterprise console
              </p>
              <p className="truncate text-xs text-slate-500">
                Operate Star Warehouse AI with explainable controls
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <div className="hidden items-center gap-2 text-right sm:flex">
              <p className="max-w-32 truncate text-sm font-medium text-slate-800">
                {user?.full_name || user?.username}
              </p>
              <Badge variant="secondary" className="capitalize">
                {currentRole}
              </Badge>
              <p className="text-[11px] text-slate-500">Tenant {user?.tenant_id ?? 'current'}</p>
            </div>
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

        <main className="min-h-[calc(100vh-72px)] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-[1440px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
