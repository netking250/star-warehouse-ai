export const OPENING_SESSION_KEY = 'star-warehouse-opening-seen'

export function shouldShowOpening(storage: Storage | null): boolean {
  if (!storage) return true
  try {
    return storage.getItem(OPENING_SESSION_KEY) !== 'true'
  } catch {
    return true
  }
}
