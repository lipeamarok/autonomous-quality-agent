import { Loader2 } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface PageLoaderProps {
  text?: string
  className?: string
}

/**
 * Full-page loading spinner for page transitions
 */
export function PageLoader({ text = "Loading...", className }: PageLoaderProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-24", className)}>
      <Loader2 className="h-10 w-10 animate-spin text-primary mb-4" />
      <p className="text-muted-foreground">{text}</p>
    </div>
  )
}

interface SpinnerProps {
  size?: "sm" | "md" | "lg"
  className?: string
}

const sizeClasses = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-10 w-10",
}

/**
 * Inline loading spinner
 */
export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <Loader2 className={cn("animate-spin text-primary", sizeClasses[size], className)} />
  )
}

/**
 * Card skeleton for loading list items
 */
export function CardSkeleton() {
  return (
    <div className="p-4 border rounded-lg space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-1/3" />
        <Skeleton className="h-5 w-16" />
      </div>
      <Skeleton className="h-4 w-2/3" />
      <div className="flex gap-2">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-20" />
      </div>
    </div>
  )
}

/**
 * Table skeleton for loading data tables
 */
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex gap-4 p-3 bg-muted/50 rounded-lg">
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/4" />
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 p-3 border-b">
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      ))}
    </div>
  )
}

/**
 * Stats card skeleton
 */
export function StatsCardSkeleton() {
  return (
    <div className="p-6 border rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-8 rounded-full" />
      </div>
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-32 mt-2" />
    </div>
  )
}

/**
 * Dashboard skeleton
 */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatsCardSkeleton key={i} />
        ))}
      </div>
      
      {/* Two columns */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="border rounded-lg p-4">
          <Skeleton className="h-6 w-40 mb-4" />
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        </div>
        <div className="border rounded-lg p-4">
          <Skeleton className="h-6 w-32 mb-4" />
          <div className="space-y-3">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Plan detail skeleton
 */
export function PlanDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-8 w-64 mb-2" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-10 w-24" />
        </div>
      </div>
      
      <div className="border rounded-lg p-4 space-y-4">
        <Skeleton className="h-6 w-24" />
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 p-3 border-b">
              <Skeleton className="h-8 w-8 rounded-full" />
              <div className="flex-1">
                <Skeleton className="h-4 w-1/3 mb-2" />
                <Skeleton className="h-3 w-2/3" />
              </div>
              <Skeleton className="h-6 w-16" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
