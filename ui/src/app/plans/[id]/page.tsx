"use client"

import { use, useState } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  ArrowLeft,
  Play,
  Edit,
  Copy,
  Download,
  FileJson,
  Loader2,
  AlertCircle,
  Globe,
  Variable,
  ChevronRight,
} from "lucide-react"
import type { Plan, Step } from "@/types/api"

function StepCard({ step, index }: { step: Step; index: number }) {
  return (
    <AccordionItem value={step.id} className="border rounded-lg px-4">
      <AccordionTrigger className="hover:no-underline py-4">
        <div className="flex items-center gap-4 flex-1">
          <span className="text-xs font-mono bg-muted px-2 py-1 rounded">
            {index + 1}
          </span>
          <div className="flex-1 text-left">
            <span className="font-medium">{step.id}</span>
            {step.description && (
              <p className="text-sm text-muted-foreground mt-0.5">
                {step.description}
              </p>
            )}
          </div>
          <Badge variant="outline">
            {step.action?.http?.method || step.action?.graphql ? "GraphQL" : "HTTP"}
          </Badge>
        </div>
      </AccordionTrigger>
      <AccordionContent className="pb-4">
        <div className="space-y-4">
          {step.action?.http && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">HTTP Request</h4>
              <div className="bg-muted rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Badge>{step.action.http.method}</Badge>
                  <code className="text-xs flex-1 break-all">
                    {step.action.http.url}
                  </code>
                </div>
                {step.action.http.body !== undefined && step.action.http.body !== null && (
                  <div className="mt-2">
                    <span className="text-xs text-muted-foreground">Body:</span>
                    <pre className="text-xs bg-background rounded p-2 mt-1 overflow-x-auto">
                      {typeof step.action.http.body === 'string'
                        ? step.action.http.body
                        : JSON.stringify(step.action.http.body, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {step.action?.graphql && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">GraphQL</h4>
              <div className="bg-muted rounded-lg p-3">
                <pre className="text-xs overflow-x-auto">
                  {step.action.graphql.query}
                </pre>
              </div>
            </div>
          )}

          {step.assertions && step.assertions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Assertions ({step.assertions.length})</h4>
              <div className="space-y-1">
                {step.assertions.map((assertion, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <ChevronRight className="h-3 w-3 text-muted-foreground" />
                    <code className="text-xs bg-muted px-2 py-1 rounded">
                      {assertion.expression}
                    </code>
                    {assertion.message && (
                      <span className="text-xs text-muted-foreground">
                        — {assertion.message}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {step.extractions && step.extractions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Extractions ({step.extractions.length})</h4>
              <div className="space-y-1">
                {step.extractions.map((ext, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Variable className="h-3 w-3 text-primary" />
                    <code className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                      ${ext.variable}
                    </code>
                    <span className="text-xs text-muted-foreground">from</span>
                    <code className="text-xs bg-muted px-2 py-1 rounded">
                      {ext.from}
                    </code>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step.retry && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Retry Policy</h4>
              <div className="flex gap-4 text-sm text-muted-foreground">
                <span>Max attempts: {step.retry.max_attempts}</span>
                <span>Delay: {step.retry.delay_ms}ms</span>
                {step.retry.backoff && <span>Backoff: {step.retry.backoff}</span>}
              </div>
            </div>
          )}
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}

export default function PlanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const [copiedJson, setCopiedJson] = useState(false)

  const { data: plan, isLoading, error } = useQuery<Plan>({
    queryKey: ["plan", id],
    queryFn: async () => {
      // Mock response until API is ready
      return {
        spec_version: "0.1",
        meta: {
          id: id,
          name: "User Authentication Flow",
          description: "Tests user login, profile access, and logout functionality",
          version: "1.0.0",
          base_url: "https://api.example.com",
        },
        context: {
          base_url: "https://api.example.com",
        },
        steps: [
          {
            id: "login",
            description: "Login with valid credentials",
            action: {
              http: {
                method: "POST",
                url: "/api/auth/login",
                body: { email: "test@example.com", password: "password123" },
              },
            },
            assertions: [
              { expression: "status == 200", message: "Should return 200" },
              { expression: "body.token != null", message: "Should return token" },
            ],
            extractions: [
              { variable: "auth_token", from: "body.token" },
            ],
          },
          {
            id: "get_profile",
            description: "Get user profile with auth token",
            action: {
              http: {
                method: "GET",
                url: "/api/users/me",
                headers: { Authorization: "Bearer ${auth_token}" },
              },
            },
            assertions: [
              { expression: "status == 200" },
              { expression: "body.email != null" },
            ],
            extractions: [
              { variable: "user_id", from: "body.id" },
            ],
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

  if (error || !plan) {
    return (
      <Card className="py-12">
        <div className="flex flex-col items-center justify-center text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
          <h3 className="text-lg font-medium">Error loading plan</h3>
          <p className="text-muted-foreground mb-4">
            {error instanceof Error ? error.message : "Plan not found"}
          </p>
          <Button asChild variant="outline">
            <Link href="/plans">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Plans
            </Link>
          </Button>
        </div>
      </Card>
    )
  }

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(plan, null, 2))
    setCopiedJson(true)
    toast.success("Plan JSON copied to clipboard")
    setTimeout(() => setCopiedJson(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(plan, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${plan.meta?.name || id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link href="/plans">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold">{plan.meta?.name || id}</h1>
          {plan.meta?.description && (
            <p className="text-muted-foreground">{plan.meta.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleCopyJson}>
            <Copy className="h-4 w-4 mr-2" />
            {copiedJson ? "Copied!" : "Copy"}
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="h-4 w-4 mr-2" />
            Download
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href={`/plans/${id}/edit`}>
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Link>
          </Button>
          <Button asChild size="sm">
            <Link href={`/execute?plan=${id}`}>
              <Play className="h-4 w-4 mr-2" />
              Execute
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Version</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-semibold">{plan.meta?.version || "—"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Spec Version</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-semibold">{plan.spec_version}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Steps</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-semibold">{plan.steps.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Base URL</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm font-mono truncate" title={plan.context?.base_url || plan.meta?.base_url}>
              {plan.context?.base_url || plan.meta?.base_url || "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="steps" className="w-full">
        <TabsList>
          <TabsTrigger value="steps">Steps</TabsTrigger>
          <TabsTrigger value="json">JSON</TabsTrigger>
        </TabsList>

        <TabsContent value="steps" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Test Steps</CardTitle>
              <CardDescription>
                {plan.steps.length} steps in this plan
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="multiple" className="space-y-2">
                {plan.steps.map((step, index) => (
                  <StepCard key={step.id} step={step} index={index} />
                ))}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="json" className="mt-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Plan JSON</CardTitle>
                <Button variant="outline" size="sm" onClick={handleCopyJson}>
                  <Copy className="h-4 w-4 mr-2" />
                  Copy
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted rounded-lg p-4 text-xs overflow-x-auto max-h-[600px]">
                {JSON.stringify(plan, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
