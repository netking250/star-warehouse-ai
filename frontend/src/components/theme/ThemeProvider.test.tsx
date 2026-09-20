import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeProvider } from './ThemeProvider'
import { resolveTheme, THEME_STORAGE_KEY } from './theme'
import { ThemeToggle } from './ThemeToggle'
import { useTheme } from './useTheme'

function installMatchMedia(prefersDark: boolean): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)' ? prefersDark : false,
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

function ThemeValue(): React.ReactElement {
  const { theme } = useTheme()
  return <output>{theme}</output>
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.classList.remove('dark')
    delete document.documentElement.dataset.theme
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('uses the system preference when no saved preference exists', () => {
    installMatchMedia(true)

    render(
      <ThemeProvider>
        <ThemeValue />
      </ThemeProvider>
    )

    expect(screen.getByText('dark')).toBeInTheDocument()
    expect(document.documentElement).toHaveClass('dark')
  })

  it('prefers a saved theme over the system preference', () => {
    installMatchMedia(true)
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light')

    render(
      <ThemeProvider>
        <ThemeValue />
      </ThemeProvider>
    )

    expect(screen.getByText('light')).toBeInTheDocument()
    expect(document.documentElement).not.toHaveClass('dark')
  })

  it('exposes an accessible toggle and persists a manual choice', () => {
    installMatchMedia(false)

    render(
      <ThemeProvider>
        <ThemeToggle />
        <ThemeValue />
      </ThemeProvider>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))

    expect(screen.getByText('dark')).toBeInTheDocument()
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('resolves invalid saved values through the system fallback', () => {
    expect(resolveTheme('unexpected', false)).toBe('light')
    expect(resolveTheme('unexpected', true)).toBe('dark')
  })
})
