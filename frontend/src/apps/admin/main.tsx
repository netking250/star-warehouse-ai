import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import '../../globals.css'
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
        <App />
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
