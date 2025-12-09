"use client"

import { Component, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { AlertTriangle, RefreshCw, Home, Bug } from "lucide-react"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    this.setState({ errorInfo })
    
    // Log error to console in development
    console.error("ErrorBoundary caught an error:", error, errorInfo)
    
    // TODO: Send to telemetry/logging service in production
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  handleReload = (): void => {
    window.location.reload()
  }

  handleGoHome = (): void => {
    window.location.href = "/"
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-[400px] flex items-center justify-center p-6">
          <Card className="max-w-lg w-full">
            <CardHeader className="text-center">
              <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center">
                <AlertTriangle className="h-6 w-6 text-destructive" />
              </div>
              <CardTitle className="text-xl">Something went wrong</CardTitle>
              <CardDescription>
                An unexpected error occurred. You can try refreshing the page or going back to the dashboard.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {this.state.error && (
                <div className="p-3 bg-muted rounded-lg">
                  <div className="flex items-center gap-2 text-sm font-medium text-destructive mb-1">
                    <Bug className="h-4 w-4" />
                    Error Details
                  </div>
                  <pre className="text-xs text-muted-foreground overflow-auto max-h-32 font-mono">
                    {this.state.error.message}
                  </pre>
                </div>
              )}
              
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={this.handleReset}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Try Again
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={this.handleReload}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Reload Page
                </Button>
                <Button
                  className="flex-1"
                  onClick={this.handleGoHome}
                >
                  <Home className="mr-2 h-4 w-4" />
                  Go Home
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}

// Hook-friendly wrapper for functional components
export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode
): React.FC<P> {
  return function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    )
  }
}
