"use client"

import { useState } from "react"
import Link from "next/link"
import { formatDistanceToNow, format } from "date-fns"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useHistory } from "@/lib/hooks/queries"
import {
  CheckCircle,
  XCircle,
  Search,
  ArrowRight,
  Clock,
  RefreshCw,
} from "lucide-react"
import type { HistoryRecord } from "@/types/api"

function StatusBadge({ status }: { status: string }) {
  if (status === "passed") {
    return (
      <Badge className="gap-1 bg-green-100 text-green-700 hover:bg-green-100">
        <CheckCircle className="h-3 w-3" />
        Passed
      </Badge>
    )
  }
  return (
    <Badge className="gap-1 bg-red-100 text-red-700 hover:bg-red-100">
      <XCircle className="h-3 w-3" />
      Failed
    </Badge>
  )
}

function ExecutionRow({ record }: { record: HistoryRecord }) {
  const status = record.status || (record.summary.failed > 0 ? "failed" : "passed")
  const successRate = record.summary.total_steps > 0
    ? ((record.summary.passed / record.summary.total_steps) * 100).toFixed(0)
    : "0"

  return (
    <TableRow>
      <TableCell>
        <StatusBadge status={status} />
      </TableCell>
      <TableCell className="font-medium">{record.plan_name}</TableCell>
      <TableCell className="font-mono text-xs text-muted-foreground">
        {record.execution_id}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1 text-sm">
          <span className="text-green-600 font-medium">{record.summary.passed}</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-red-600 font-medium">{record.summary.failed}</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">{record.summary.total_steps}</span>
        </div>
      </TableCell>
      <TableCell className="text-right">
        {successRate}%
      </TableCell>
      <TableCell className="text-right">
        {(record.summary.duration_ms / 1000).toFixed(2)}s
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1 text-muted-foreground text-sm">
          <Clock className="h-3 w-3" />
          {formatDistanceToNow(new Date(record.timestamp), { addSuffix: true })}
        </div>
      </TableCell>
      <TableCell>
        <Link href={`/history/${record.execution_id}`}>
          <Button variant="ghost" size="sm" className="gap-1">
            Details
            <ArrowRight className="h-3 w-3" />
          </Button>
        </Link>
      </TableCell>
    </TableRow>
  )
}

export default function HistoryPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const { data, isLoading, refetch, isRefetching } = useHistory({ limit: 50 })

  const filteredRecords = data?.records.filter((record) => {
    const status = record.status || (record.summary.failed > 0 ? "failed" : "passed")
    const matchesStatus = statusFilter === "all" || status === statusFilter
    const matchesSearch = record.plan_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      record.execution_id.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesStatus && matchesSearch
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Execution History</h1>
          <p className="text-muted-foreground">
            View past test executions and results
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isRefetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by plan name or ID..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="passed">Passed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 py-4">
                  <Skeleton className="h-6 w-20" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </div>
          ) : filteredRecords?.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <p>No executions found</p>
              <p className="text-sm">
                {searchQuery || statusFilter !== "all"
                  ? "Try adjusting your filters"
                  : "Run your first test plan to see results here"}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Status</TableHead>
                  <TableHead>Plan Name</TableHead>
                  <TableHead>Execution ID</TableHead>
                  <TableHead title="Passed / Failed / Total">Steps (P/F/T)</TableHead>
                  <TableHead className="text-right" title="Success rate percentage">Success</TableHead>
                  <TableHead className="text-right" title="Total execution duration">Duration</TableHead>
                  <TableHead title="Time since execution">Time</TableHead>
                  <TableHead className="w-[100px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRecords?.map((record) => (
                  <ExecutionRow key={record.execution_id} record={record} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
