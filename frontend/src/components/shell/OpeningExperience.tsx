import { useEffect, useState } from 'react'
import { BrandMark } from '@/components/brand/StarWarehouseLogo'
import { OPENING_SESSION_KEY, shouldShowOpening } from './opening'

const OPENING_DURATION_MS = 2300
const REDUCED_MOTION_DURATION_MS = 180

let activeOpening = false

function claimOpening(): boolean {
  if (activeOpening) return true
  const storage = typeof window === 'undefined' ? null : window.sessionStorage
  if (!shouldShowOpening(storage)) return false
  activeOpening = true
  try {
    storage?.setItem(OPENING_SESSION_KEY, 'true')
  } catch {
    // A deterministic timer still dismisses the experience when storage is unavailable.
  }
  return true
}

/** Present the session-scoped brand opening without taking focus or delaying application state. */
export function OpeningExperience(): React.ReactElement | null {
  const [visible, setVisible] = useState(claimOpening)

  useEffect(() => {
    if (!visible) return
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const timer = window.setTimeout(
      () => {
        activeOpening = false
        setVisible(false)
      },
      reducedMotion ? REDUCED_MOTION_DURATION_MS : OPENING_DURATION_MS
    )
    return () => window.clearTimeout(timer)
  }, [visible])

  if (!visible) return null

  return (
    <div
      aria-hidden="true"
      data-testid="opening-experience"
      className="opening-experience pointer-events-none fixed inset-0 z-[100] grid place-items-center overflow-hidden"
    >
      <div className="opening-stars absolute inset-0" />
      <div className="opening-trail absolute left-[-35%] top-1/2 h-px w-[52%]" />
      <div className="opening-lockup relative flex flex-col items-center text-center">
        <BrandMark className="opening-mark h-20 w-20" />
        <p className="opening-title mt-7 text-xl font-semibold tracking-[0.26em] text-white sm:text-2xl">
          STAR WAREHOUSE AI
        </p>
        <p className="opening-subtitle mt-3 text-[10px] font-medium uppercase tracking-[0.24em] text-white/48 sm:text-xs">
          Enterprise AI Service Platform
        </p>
      </div>
    </div>
  )
}
