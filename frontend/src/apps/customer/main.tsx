import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import '../../globals.css'
import { queryClient } from '@/lib/query-client'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { OpeningExperience } from '@/components/shell/OpeningExperience'
import { ThemeProvider } from '@/components/theme/ThemeProvider'
import { initWebVitals } from '@/utils/webVitalsReporter'

initWebVitals({ samplingRate: 0.1 })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <OpeningExperience />
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
