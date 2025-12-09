"use client"

import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { useHistory } from "@/lib/hooks/queries"
import {
  CheckCircle,
  XCircle,
  ArrowRight,
  Clock,
} from "lucide-react"
import type { HistoryRecord } from "@/types/api"

function StatusBadge({ status }: { status: string }) {
  if (status === "passed") {
    return (
      <Badge variant="outline" className="gap-1 text-green-600 border-green-200 bg-green-50">
        <CheckCircle className="h-3 w-3" />
        Passed
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-red-600 border-red-200 bg-red-50">
      <XCircle className="h-3 w-3" />
      Failed
    </Badge>
  )
}

function ExecutionRow({ record }: { record: HistoryRecord }) {
  const status = record.status || (record.summary.failed > 0 ? "failed" : "passed")

  return (
    <div className="flex items-center justify-between py-3 border-b last:border-0">
      <div className="flex items-center gap-4">
        <StatusBadge status={status} />
        <div>
          <p className="text-sm font-medium">{record.plan_name}</p>
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDistanceToNow(new Date(record.timestamp), { addSuffix: true })}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right text-sm">
          <span className="text-green-600">{record.summary.passed}</span>
          {" / "}
          <span className="text-red-600">{record.summary.failed}</span>
          {" / "}
          <span className="text-muted-foreground">{record.summary.total_steps}</span>
        </div>
        <Link href={`/history/${record.execution_id}`}>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    </div>
  )
}

export function RecentExecutions() {
  const { data, isLoading } = useHistory({ limit: 5 })

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium">Recent Executions</CardTitle>
        <Link href="/history">
          <Button variant="ghost" size="sm" className="gap-1">
            View all
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-4">
                  <Skeleton className="h-5 w-16" />
                  <div>
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-24 mt-1" />
                  </div>
                </div>
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        ) : data?.records.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            <p>No executions yet</p>
            <p className="text-sm">Run your first test plan to see results here</p>
          </div>
        ) : (
          <div>
            {data?.records.map((record) => (
              <ExecutionRow key={record.execution_id} record={record} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
