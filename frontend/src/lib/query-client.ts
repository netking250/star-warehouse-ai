import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // apiFetch owns bounded safe-read retries; disabling Query retries prevents multiplication.
      retry: false,
    },
    mutations: {
      // Mutations are not retried unless a domain call explicitly opts in through apiFetch.
      retry: false,
    },
  },
})
