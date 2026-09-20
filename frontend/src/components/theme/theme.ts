export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'star-warehouse-theme'

export function resolveTheme(savedTheme: string | null, prefersDark: boolean): Theme {
  if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme
  return prefersDark ? 'dark' : 'light'
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.dataset.theme = theme
  root.style.colorScheme = theme
  const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
  themeColor?.setAttribute('content', theme === 'dark' ? '#10121a' : '#f5f6fa')
}
