import { useEffect, useMemo, useState } from 'react'
import { applyTheme, resolveTheme, THEME_STORAGE_KEY, type Theme } from './theme'
import { ThemeContext, type ThemeContextValue } from './useTheme'

function getSystemPreference(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

function getSavedTheme(): string | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY)
  } catch {
    return null
  }
}

function getInitialTheme(): Theme {
  if (typeof document !== 'undefined') {
    const documentTheme = document.documentElement.dataset.theme
    if (documentTheme === 'light' || documentTheme === 'dark') return documentTheme
  }
  return resolveTheme(getSavedTheme(), getSystemPreference())
}

export function ThemeProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (event: MediaQueryListEvent): void => {
      if (getSavedTheme() === null) setThemeState(event.matches ? 'dark' : 'light')
    }
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme: (nextTheme) => {
        try {
          window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
        } catch {
          // The in-memory preference still works when browser storage is unavailable.
        }
        setThemeState(nextTheme)
      },
      toggleTheme: () => {
        const nextTheme = theme === 'dark' ? 'light' : 'dark'
        try {
          window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
        } catch {
          // The in-memory preference still works when browser storage is unavailable.
        }
        setThemeState(nextTheme)
      },
    }),
    [theme]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
