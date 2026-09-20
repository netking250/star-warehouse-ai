import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OpeningExperience } from './OpeningExperience'
import { OPENING_SESSION_KEY, shouldShowOpening } from './opening'

function installMotionPreference(reduced: boolean): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? reduced : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

describe('OpeningExperience', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    window.sessionStorage.clear()
    installMotionPreference(false)
  })

  afterEach(async () => {
    await act(() => Promise.resolve(vi.runOnlyPendingTimers()))
    cleanup()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('renders once, leaves application controls usable, and completes deterministically', async () => {
    render(
      <>
        <button type="button">Application action</button>
        <OpeningExperience />
      </>
    )

    const opening = screen.getByTestId('opening-experience')
    expect(opening).toHaveAttribute('aria-hidden', 'true')
    expect(opening).toHaveClass('pointer-events-none')

    const action = screen.getByRole('button', { name: 'Application action' })
    action.focus()
    expect(action).toHaveFocus()

    await act(() => Promise.resolve(vi.advanceTimersByTime(2300)))
    expect(screen.queryByTestId('opening-experience')).not.toBeInTheDocument()
    expect(window.sessionStorage.getItem(OPENING_SESSION_KEY)).toBe('true')
  })

  it('does not replay after the session marker is set', () => {
    window.sessionStorage.setItem(OPENING_SESSION_KEY, 'true')

    render(<OpeningExperience />)

    expect(screen.queryByTestId('opening-experience')).not.toBeInTheDocument()
    expect(shouldShowOpening(window.sessionStorage)).toBe(false)
  })

  it('uses the short deterministic path for reduced motion', async () => {
    installMotionPreference(true)
    render(<OpeningExperience />)

    expect(screen.getByTestId('opening-experience')).toBeInTheDocument()
    await act(() => Promise.resolve(vi.advanceTimersByTime(180)))
    expect(screen.queryByTestId('opening-experience')).not.toBeInTheDocument()
  })
})
