import { BrowserRouter, HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/query-client'
import { Login } from './pages/Login'
import { Overview } from './pages/Overview'
import { Operations } from './pages/Operations'
import { Security } from './pages/Security'
import { Compliance } from './pages/Compliance'
import { KnowledgeBase } from './pages/KnowledgeBase'
import { AgentConfig } from './pages/AgentConfig'
import { Feedback } from './pages/Feedback'
import { MetricsPage } from './pages/MetricsPage'
import { AdminLayout } from './components/AdminLayout'
import { CapabilityRoute, SessionRoute } from './components/RouteGuards'
import { CONSOLE_OPERATIONS_CAPABILITIES, CONSOLE_OVERVIEW_CAPABILITIES } from '@/lib/authorization'

const Router = import.meta.env.DEV ? HashRouter : BrowserRouter

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router basename={import.meta.env.DEV ? undefined : '/admin'}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<SessionRoute />}>
            <Route element={<AdminLayout />}>
              <Route
                path="/"
                element={
                  <CapabilityRoute capabilities={CONSOLE_OVERVIEW_CAPABILITIES}>
                    <Overview />
                  </CapabilityRoute>
                }
              />
              <Route
                path="/operations"
                element={
                  <CapabilityRoute capabilities={CONSOLE_OPERATIONS_CAPABILITIES}>
                    <Operations />
                  </CapabilityRoute>
                }
              />
              <Route
                path="/ai"
                element={
                  <CapabilityRoute capabilities={['operations.read']}>
                    <AgentConfig />
                  </CapabilityRoute>
                }
              />
              <Route
                path="/security"
                element={
                  <CapabilityRoute capabilities={['identity.read']}>
                    <Security />
                  </CapabilityRoute>
                }
              />
              <Route
                path="/compliance"
                element={
                  <CapabilityRoute capabilities={['compliance.read']}>
                    <Compliance />
                  </CapabilityRoute>
                }
              />
              <Route
                path="/knowledge"
                element={
                  <CapabilityRoute capabilities={['knowledge.read']}>
                    <KnowledgeBase />
                  </CapabilityRoute>
                }
              />
              <Route
                path="/feedback"
                element={
                  <CapabilityRoute capabilities={['operations.read']}>
                    <Feedback />
                  </CapabilityRoute>
                }
              />
              <Route
                path="/metrics"
                element={
                  <CapabilityRoute capabilities={['operations.read']}>
                    <MetricsPage />
                  </CapabilityRoute>
                }
              />
            </Route>
          </Route>
          <Route path="/agent-config" element={<Navigate to="/ai" replace />} />
          <Route path="/dashboard" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </QueryClientProvider>
  )
}

export default App
