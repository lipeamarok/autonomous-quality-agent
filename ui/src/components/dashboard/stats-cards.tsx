"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useHistoryStats } from "@/lib/hooks/queries"
import { Activity, CheckCircle, Clock, TrendingUp } from "lucide-react"

export function StatsCards() {
  const { data, isLoading } = useHistoryStats()

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-4" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-3 w-32 mt-1" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const stats = data?.stats

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Total Executions
          </CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {stats?.total_executions ?? 0}
          </div>
          <p className="text-xs text-muted-foreground">
            {stats?.executions_today ?? 0} today
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Success Rate
          </CardTitle>
          <CheckCircle className="h-4 w-4 text-green-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {((stats?.success_rate ?? 0) * 100).toFixed(1)}%
          </div>
          <p className="text-xs text-muted-foreground">
            All time average
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Avg Duration
          </CardTitle>
          <Clock className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {((stats?.avg_duration_ms ?? 0) / 1000).toFixed(2)}s
          </div>
          <p className="text-xs text-muted-foreground">
            Per execution
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            This Week
          </CardTitle>
          <TrendingUp className="h-4 w-4 text-primary" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {stats?.executions_this_week ?? stats?.executions_today ?? 0}
          </div>
          <p className="text-xs text-muted-foreground">
            Executions
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
