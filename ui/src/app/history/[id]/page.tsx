"use client"

import { use } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { api } from "@/lib/api/client"
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Calendar,
  FileJson,
  RefreshCw,
  Download,
  Loader2,
  ExternalLink,
  Copy,
} from "lucide-react"
import type { StepResult } from "@/types/api"
import { toast } from "sonner"

function StepResultCard({ step, index }: { step: StepResult; index: number }) {
  const statusConfig = {
    passed: {
      icon: <CheckCircle className="h-5 w-5 text-green-500" />,
      badge: "bg-green-100 text-green-700",
      border: "border-l-green-500",
    },
    failed: {
      icon: <XCircle className="h-5 w-5 text-red-500" />,
      badge: "bg-red-100 text-red-700",
      border: "border-l-red-500",
    },
    skipped: {
      icon: <AlertCircle className="h-5 w-5 text-muted-foreground" />,
      badge: "bg-muted text-muted-foreground",
      border: "border-l-muted",
    },
  }

  const config = statusConfig[step.status]

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(step, null, 2))
    toast.success("Step JSON copied to clipboard")
  }

  return (
    <AccordionItem value={step.step_id} className={`border-l-4 ${config.border} pl-4 border-b-0`}>
      <AccordionTrigger className="hover:no-underline py-4">
        <div className="flex items-center gap-4 flex-1">
          <span className="text-xs font-mono text-muted-foreground w-6">
            #{index + 1}
          </span>
          {config.icon}
          <div className="flex-1 text-left">
            <span className="font-medium">{step.step_id}</span>
            {step.http_details && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {step.http_details.method} {step.http_details.url}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {step.attempt > 1 && (
              <Badge variant="outline" className="text-xs">
                <RefreshCw className="h-3 w-3 mr-1" />
                {step.attempt} attempts
              </Badge>
            )}
            <Badge className={config.badge}>
              {step.status}
            </Badge>
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {step.duration_ms}ms
            </span>
          </div>
        </div>
      </AccordionTrigger>
      <AccordionContent className="pb-4">
        <div className="space-y-4 pl-10">
          {step.http_details && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">HTTP Details</h4>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Method:</span>{" "}
                  <Badge variant="outline">{step.http_details.method}</Badge>
                </div>
                <div>
                  <span className="text-muted-foreground">Status:</span>{" "}
                  <Badge
                    variant="outline"
                    className={
                      step.http_details.status_code >= 200 &&
                      step.http_details.status_code < 300
                        ? "border-green-500 text-green-600"
                        : step.http_details.status_code >= 400
                        ? "border-red-500 text-red-600"
                        : ""
                    }
                  >
                    {step.http_details.status_code}
                  </Badge>
                </div>
                <div className="col-span-3">
                  <span className="text-muted-foreground">URL:</span>{" "}
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded break-all">
                    {step.http_details.url}
                  </code>
                </div>
              </div>
            </div>
          )}

          {step.assertions_results && step.assertions_results.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Assertions</h4>
              <div className="space-y-1">
                {step.assertions_results.map((assertion, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-sm"
                  >
                    {assertion.passed ? (
                      <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 text-red-500" />
                    )}
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {assertion.type} {assertion.operator} {JSON.stringify(assertion.expected)}
                    </code>
                    {!assertion.passed && (
                      <span className="text-xs text-red-500">
                        actual: {JSON.stringify(assertion.actual)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {step.extractions && Object.keys(step.extractions).length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Extractions</h4>
              <div className="space-y-1">
                {Object.entries(step.extractions).map(([key, value], i) => (
                  <div key={i} className="text-sm">
                    <code className="bg-primary/10 text-primary px-1.5 py-0.5 rounded text-xs">
                      {key}
                    </code>
                    <span className="text-muted-foreground mx-2">=</span>
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {JSON.stringify(value)}
                    </code>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step.error && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-red-600">Error</h4>
              <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded">
                {step.error}
              </p>
            </div>
          )}

          <div className="flex justify-end">
            <Button variant="ghost" size="sm" onClick={handleCopyJson}>
              <Copy className="h-3.5 w-3.5 mr-1" />
              Copy JSON
            </Button>
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}

export default function ExecutionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)

  const { data, isLoading, error } = useQuery({
    queryKey: ["execution", id],
    queryFn: async () => {
      // Mock response until API is ready
      return {
        execution_id: id,
        plan_id: "plan_001",
        plan_name: "User Authentication Flow",
        status: "passed" as const,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        summary: {
          total_steps: 5,
          passed: 5,
          failed: 0,
          skipped: 0,
          duration_ms: 1234,
        },
        steps: [
          {
            step_id: "login",
            status: "passed" as const,
            attempt: 1,
            duration_ms: 250,
            http_details: {
              method: "POST",
              url: "/api/auth/login",
              status_code: 200,
              latency_ms: 250,
            },
            assertions_results: [
              { type: "status", operator: "==", expected: 200, actual: 200, passed: true },
              { type: "body", operator: "!=", expected: null, actual: "token", passed: true, path: "token" },
            ],
            extractions: {
              auth_token: "eyJhbGc...",
            },
          },
          {
            step_id: "get_profile",
            status: "passed" as const,
            attempt: 1,
            duration_ms: 180,
            http_details: {
              method: "GET",
              url: "/api/users/me",
              status_code: 200,
              latency_ms: 180,
            },
            assertions_results: [
              { type: "status", operator: "==", expected: 200, actual: 200, passed: true },
              { type: "body", operator: "!=", expected: null, actual: "test@example.com", passed: true, path: "email" },
            ],
            extractions: {
              user_id: "usr_123",
            },
          },
        ],
      }
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <Card className="py-12">
        <div className="flex flex-col items-center justify-center text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
          <h3 className="text-lg font-medium">Error loading execution</h3>
          <p className="text-muted-foreground mb-4">
            {error instanceof Error ? error.message : "Execution not found"}
          </p>
          <Button asChild variant="outline">
            <Link href="/history">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to History
            </Link>
          </Button>
        </div>
      </Card>
    )
  }

  const successRate =
    data.summary.total_steps > 0
      ? (data.summary.passed / data.summary.total_steps) * 100
      : 0

  const handleDownloadReport = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `execution-${id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link href="/history">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold">{data.plan_name}</h1>
          <p className="text-muted-foreground font-mono text-sm">{id}</p>
        </div>
        <Badge
          className={
            data.status === "passed"
              ? "bg-green-100 text-green-700"
              : "bg-red-100 text-red-700"
          }
        >
          {data.status === "passed" ? (
            <CheckCircle className="h-3 w-3 mr-1" />
          ) : (
            <XCircle className="h-3 w-3 mr-1" />
          )}
          {data.status === "passed" ? "Passed" : "Failed"}
        </Badge>
        <Button variant="outline" onClick={handleDownloadReport}>
          <Download className="h-4 w-4 mr-2" />
          Download
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Steps</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.summary.total_steps}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Passed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {data.summary.passed}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Failed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {data.summary.failed}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Duration</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(data.summary.duration_ms / 1000).toFixed(2)}s
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Success Rate</CardTitle>
            <span className="text-lg font-semibold">
              {successRate.toFixed(0)}%
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <Progress value={successRate} className="h-3" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Step Results</CardTitle>
          <CardDescription>
            Click on a step to view details
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Accordion type="multiple" className="space-y-2">
            {data.steps.map((step, index) => (
              <StepResultCard key={step.step_id} step={step} index={index} />
            ))}
          </Accordion>
        </CardContent>
      </Card>
    </div>
  )
}
