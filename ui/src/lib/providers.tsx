"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState, type ReactNode } from "react"
import { ThemeProvider } from "./hooks/use-theme"
import { SettingsProvider } from "./hooks/use-settings"
import { ErrorBoundary } from "@/components/layout/error-boundary"
import { Toaster } from "sonner"

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  )

  return (
    <ThemeProvider>
      <SettingsProvider>
        <QueryClientProvider client={queryClient}>
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
          <Toaster position="top-right" richColors />
          <ReactQueryDevtools initialIsOpen={false} />
        </QueryClientProvider>
      </SettingsProvider>
    </ThemeProvider>
  )
}
