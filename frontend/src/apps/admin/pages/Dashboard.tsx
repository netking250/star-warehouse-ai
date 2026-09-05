import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card } from '@/components/ui/card'
import { StarWarehouseLogo } from '@/components/brand/StarWarehouseLogo'
import {
  LogOut,
  Bell,
  User,
  BarChart3,
  BarChart4,
  MessageSquare,
  BookOpen,
  Bot,
  FlaskConical,
  ShieldAlert,
  CheckCircle,
  AlertCircle,
  Info,
  Activity,
  LayoutDashboard,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useTasks, useTaskStats } from '@/hooks/useTasks'
import { useNotifications } from '@/hooks/useNotifications'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { Task, TaskFilters } from '@/types'
import { TaskList } from '../components/TaskList'
import { TaskDetail } from '../components/TaskDetail'
import { DecisionPanel } from '../components/DecisionPanel'
import { NotificationToast } from '../components/NotificationToast'
import { Performance } from '../components/Performance'
import { EvaluationViewer } from '../components/EvaluationViewer'
import { ConversationLogs } from '../components/ConversationLogs'
import { KnowledgeBase } from '../pages/KnowledgeBase'
import { AgentConfig } from '../pages/AgentConfig'
import { ExperimentManager } from '../components/ExperimentManager'
import { AnalyticsV2 } from '../components/AnalyticsV2'
import { ComplaintQueue } from '../components/ComplaintQueue'
import { FeedbackManager } from '../components/FeedbackManager'
import { MetricsPage } from '../pages/MetricsPage'

export function Dashboard() {
  const { user, logout } = useAuth()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [filters, setFilters] = useState<TaskFilters>({ riskLevel: 'ALL' })
  const { tasks, isLoading, submitDecision, isSubmitting } = useTasks(filters)
  const { data: stats } = useTaskStats()
  const { notifications, unreadCount, markAsRead, markAllAsRead, handleWsMessage } =
    useNotifications()
  const [showNotifications, setShowNotifications] = useState(false)
  const notificationRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/admin/${user?.user_id ?? ''}`
  useWebSocket({ url: wsUrl, enabled: Boolean(user?.user_id), onMessage: handleWsMessage })

  const handleDecision = async (
    auditLogId: number,
    action: 'APPROVE' | 'REJECT',
    comment: string
  ) => {
    await submitDecision({
      audit_log_id: auditLogId,
      action,
      comment,
      admin_id: user?.user_id || '',
    })
    setSelectedTask(null)
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500 shrink-0" />
      default:
        return <Info className="h-4 w-4 text-blue-500 shrink-0" />
    }
  }

  return (
    <div className="h-screen overflow-hidden bg-[#f5f7fb]">
      <Tabs defaultValue="tasks" className="flex h-full overflow-hidden">
        <aside className="hidden w-64 shrink-0 flex-col bg-slate-950 text-white lg:flex">
          <div className="flex h-[76px] items-center border-b border-white/10 px-5">
            <StarWarehouseLogo inverse />
          </div>
          <div className="px-4 pb-2 pt-6">
            <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
              运营工作台
            </p>
          </div>
          <TabsList className="flex h-auto flex-1 flex-col items-stretch justify-start gap-1 overflow-y-auto rounded-none bg-transparent px-3 pb-5 text-slate-400">
            <TabsTrigger
              value="tasks"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <LayoutDashboard className="h-4 w-4" /> 审核任务
            </TabsTrigger>
            <TabsTrigger
              value="performance"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <BarChart3 className="h-4 w-4" /> 性能指标
            </TabsTrigger>
            <TabsTrigger
              value="conversations"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <MessageSquare className="h-4 w-4" /> 会话审计
            </TabsTrigger>
            <TabsTrigger
              value="evaluation"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <BarChart3 className="h-4 w-4" /> 质量评测
            </TabsTrigger>
            <TabsTrigger
              value="knowledge"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <BookOpen className="h-4 w-4" /> 企业知识库
            </TabsTrigger>
            <TabsTrigger
              value="agent-config"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <Bot className="h-4 w-4" /> AI Agent
            </TabsTrigger>
            <TabsTrigger
              value="experiments"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <FlaskConical className="h-4 w-4" /> 策略实验
            </TabsTrigger>
            <TabsTrigger
              value="complaints"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <ShieldAlert className="h-4 w-4" /> 投诉工单
            </TabsTrigger>
            <TabsTrigger
              value="feedback"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <MessageSquare className="h-4 w-4" /> 用户反馈
            </TabsTrigger>
            <TabsTrigger
              value="analytics-v2"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <BarChart4 className="h-4 w-4" /> 运营分析
            </TabsTrigger>
            <TabsTrigger
              value="metrics"
              className="h-10 justify-start gap-3 rounded-xl px-3 data-[state=active]:bg-indigo-500/15 data-[state=active]:text-indigo-200 data-[state=active]:shadow-none"
            >
              <Activity className="h-4 w-4" /> 系统监控
            </TabsTrigger>
          </TabsList>
          <div className="border-t border-white/10 p-4">
            <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.06] p-3">
              <div className="flex items-center gap-2 text-xs text-emerald-300">
                <span className="h-2 w-2 rounded-full bg-emerald-400" /> 平台运行正常
              </div>
              <p className="mt-1.5 text-[10px] text-slate-500">星仓 AI 企业服务集群</p>
            </div>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <header className="glass-panel flex h-[76px] shrink-0 items-center justify-between border-b px-4 sm:px-6">
            <div className="flex items-center gap-3">
              <StarWarehouseLogo className="lg:hidden" />
              <div className="hidden sm:block">
                <div className="flex items-center gap-3">
                  <h1 className="text-lg font-semibold tracking-tight text-slate-950">
                    运营控制中心
                  </h1>
                  {stats && (
                    <div className="flex gap-2">
                      <Badge
                        variant="secondary"
                        className="rounded-full bg-indigo-50 text-indigo-600"
                      >
                        待审核 {stats.pending}
                      </Badge>
                      <Badge variant="destructive" className="rounded-full">
                        高风险 {stats.high_risk}
                      </Badge>
                    </div>
                  )}
                </div>
                <p className="mt-1 text-xs text-slate-400">统一管理 AI 服务质量、知识与风险</p>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-4">
              <div className="relative" ref={notificationRef}>
                <Button
                  variant="ghost"
                  size="icon"
                  className="relative"
                  onClick={() => setShowNotifications((v) => !v)}
                >
                  <Bell className="h-5 w-5" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 h-5 w-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                      {unreadCount}
                    </span>
                  )}
                </Button>
                {showNotifications && (
                  <Card className="absolute right-0 top-full mt-2 w-80 z-50 shadow-lg">
                    <div className="flex items-center justify-between px-4 py-3 border-b">
                      <span className="font-medium text-sm">通知</span>
                      {unreadCount > 0 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={markAllAsRead}
                        >
                          全部已读
                        </Button>
                      )}
                    </div>
                    <div className="max-h-80 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <div className="px-4 py-6 text-sm text-gray-500 text-center">暂无通知</div>
                      ) : (
                        notifications.slice(0, 20).map((n) => (
                          <div
                            key={n.id}
                            className={`px-4 py-3 border-b last:border-b-0 cursor-pointer hover:bg-gray-50 ${
                              !n.read ? 'bg-blue-50/40' : ''
                            }`}
                            onClick={() => markAsRead(n.id)}
                          >
                            <div className="flex items-start gap-2">
                              {getNotificationIcon(n.type)}
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{n.title}</p>
                                <p className="text-xs text-gray-600 line-clamp-2">{n.message}</p>
                              </div>
                              {!n.read && (
                                <span className="h-2 w-2 bg-blue-500 rounded-full mt-1.5 shrink-0" />
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </Card>
                )}
              </div>

              <div className="hidden items-center gap-2 text-sm sm:flex">
                <div className="grid h-8 w-8 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
                  <User className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-700">{user?.username}</p>
                  <p className="text-[10px] text-slate-400">平台管理员</p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => void logout()}>
                <LogOut className="h-4 w-4 mr-1" />
                退出
              </Button>
            </div>
          </header>

          <div className="shrink-0 overflow-x-auto border-b bg-white px-3 py-2 lg:hidden">
            <TabsList className="h-9 w-max justify-start">
              <TabsTrigger value="tasks">审核</TabsTrigger>
              <TabsTrigger value="conversations">会话</TabsTrigger>
              <TabsTrigger value="knowledge">知识</TabsTrigger>
              <TabsTrigger value="agent-config">Agent</TabsTrigger>
              <TabsTrigger value="complaints">投诉</TabsTrigger>
              <TabsTrigger value="metrics">监控</TabsTrigger>
            </TabsList>
          </div>

          <div className="flex-1 overflow-hidden">
            <TabsContent value="tasks" className="m-0 h-full overflow-hidden">
              <div className="grid h-full grid-cols-1 gap-4 overflow-y-auto p-4 xl:grid-cols-[280px_1fr_320px] xl:overflow-hidden">
                <TaskList
                  tasks={tasks || []}
                  isLoading={isLoading}
                  filters={filters}
                  onFilterChange={setFilters}
                  selectedTask={selectedTask}
                  onSelectTask={setSelectedTask}
                />

                <TaskDetail task={selectedTask} />

                <DecisionPanel
                  task={selectedTask}
                  onDecision={(auditLogId, action, comment) => {
                    void handleDecision(auditLogId, action, comment)
                  }}
                  isSubmitting={isSubmitting}
                />
              </div>
            </TabsContent>

            <TabsContent value="conversations" className="m-0 h-full overflow-hidden">
              <div className="h-full p-4">
                <ConversationLogs />
              </div>
            </TabsContent>

            <TabsContent value="performance" className="m-0 h-full overflow-hidden">
              <Performance />
            </TabsContent>

            <TabsContent value="evaluation" className="m-0 h-full overflow-hidden">
              <div className="h-full p-4">
                <EvaluationViewer />
              </div>
            </TabsContent>

            <TabsContent value="knowledge" className="m-0 h-full overflow-hidden">
              <KnowledgeBase />
            </TabsContent>

            <TabsContent value="agent-config" className="m-0 h-full overflow-hidden">
              <AgentConfig />
            </TabsContent>

            <TabsContent value="experiments" className="m-0 h-full overflow-hidden">
              <ExperimentManager />
            </TabsContent>

            <TabsContent value="complaints" className="m-0 h-full overflow-hidden">
              <ComplaintQueue />
            </TabsContent>

            <TabsContent value="feedback" className="m-0 h-full overflow-hidden">
              <FeedbackManager />
            </TabsContent>

            <TabsContent value="analytics-v2" className="m-0 h-full overflow-hidden">
              <AnalyticsV2 />
            </TabsContent>

            <TabsContent value="metrics" className="m-0 h-full overflow-hidden">
              <MetricsPage />
            </TabsContent>
          </div>
        </section>
      </Tabs>

      <NotificationToast
        notifications={notifications}
        onMarkAsRead={markAsRead}
        onMarkAllAsRead={markAllAsRead}
      />
    </div>
  )
}
