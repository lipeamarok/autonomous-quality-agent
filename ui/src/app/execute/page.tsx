"use client"

import { useState, useCallback } from "react"
import Link from "next/link"
import dynamic from "next/dynamic"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useExecute, usePlans } from "@/lib/hooks/queries"
import { useExecutionWebSocket } from "@/lib/hooks/use-websocket"
import {
  Play,
  Square,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  FileJson,
  Upload,
  AlertCircle,
  Settings2,
  ChevronDown,
  Zap,
  RefreshCw,
  Timer,
  Radio,
  Wifi,
  WifiOff,
  Wand2,
} from "lucide-react"
import type { Plan, StepResult, ExecuteResponse, WsEvent } from "@/types/api"

// Dynamically import Monaco Editor to avoid SSR issues
const Editor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.default),
  {
    ssr: false,
    loading: () => (
      <div className="h-[400px] flex items-center justify-center bg-muted rounded-lg border">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    ),
  }
)

function StepResultItem({ step }: { step: StepResult }) {
  const statusIcon = {
    passed: <CheckCircle className="h-4 w-4 text-green-500" />,
    failed: <XCircle className="h-4 w-4 text-red-500" />,
    skipped: <AlertCircle className="h-4 w-4 text-muted-foreground" />,
  }

  return (
    <div className="flex items-start gap-3 py-3 border-b last:border-0">
      <div className="mt-0.5">{statusIcon[step.status]}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{step.step_id}</span>
          {step.attempt > 1 && (
            <Badge variant="outline" className="text-xs">
              Attempt {step.attempt}
            </Badge>
          )}
        </div>
        {step.http_details && (
          <p className="text-xs text-muted-foreground mt-1">
            {step.http_details.method} {step.http_details.url} → {step.http_details.status_code}
          </p>
        )}
        {step.error && (
          <p className="text-xs text-red-500 mt-1">{step.error}</p>
        )}
      </div>
      <div className="text-xs text-muted-foreground flex items-center gap-1">
        <Clock className="h-3 w-3" />
        {step.duration_ms}ms
      </div>
    </div>
  )
}

function ExecutionResults({ result }: { result: ExecuteResponse }) {
  const successRate = result.summary.total_steps > 0
    ? (result.summary.passed / result.summary.total_steps) * 100
    : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Badge
          className={
            result.summary.failed === 0
              ? "bg-green-100 text-green-700"
              : "bg-red-100 text-red-700"
          }
        >
          {result.summary.failed === 0 ? (
            <CheckCircle className="h-3 w-3 mr-1" />
          ) : (
            <XCircle className="h-3 w-3 mr-1" />
          )}
          {result.summary.failed === 0 ? "All Passed" : "Some Failed"}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {result.execution_id}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="text-center p-3 bg-muted/50 rounded-lg">
          <div className="text-2xl font-bold">{result.summary.total_steps}</div>
          <div className="text-xs text-muted-foreground">Total</div>
        </div>
        <div className="text-center p-3 bg-green-50 rounded-lg">
          <div className="text-2xl font-bold text-green-600">{result.summary.passed}</div>
          <div className="text-xs text-muted-foreground">Passed</div>
        </div>
        <div className="text-center p-3 bg-red-50 rounded-lg">
          <div className="text-2xl font-bold text-red-600">{result.summary.failed}</div>
          <div className="text-xs text-muted-foreground">Failed</div>
        </div>
        <div className="text-center p-3 bg-muted/50 rounded-lg">
          <div className="text-2xl font-bold">{(result.summary.duration_ms / 1000).toFixed(2)}s</div>
          <div className="text-xs text-muted-foreground">Duration</div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">Success Rate</span>
          <span className="text-sm text-muted-foreground">{successRate.toFixed(0)}%</span>
        </div>
        <Progress value={successRate} className="h-2" />
      </div>

      <div className="pt-4 border-t">
        <h4 className="text-sm font-medium mb-3">Step Results</h4>
        <ScrollArea className="h-[300px]">
          {result.steps.map((step) => (
            <StepResultItem key={step.step_id} step={step} />
          ))}
        </ScrollArea>
      </div>
    </div>
  )
}

export default function ExecutePage() {
  const [planJson, setPlanJson] = useState("")
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [parallel, setParallel] = useState(false)
  const [timeout, setTimeout] = useState(300)
  const [maxRetries, setMaxRetries] = useState(3)
  const [dryRun, setDryRun] = useState(false)
  const [useStreaming, setUseStreaming] = useState(true)
  const [executionId, setExecutionId] = useState<string | null>(null)
  const [liveSteps, setLiveSteps] = useState<StepResult[]>([])
  const [currentStep, setCurrentStep] = useState<{ id: string; description?: string } | null>(null)
  const [progress, setProgress] = useState({ current: 0, total: 0 })

  const execute = useExecute()
  const { data: plansData } = usePlans()

  // WebSocket for streaming execution
  const handleWsEvent = useCallback((event: WsEvent) => {
    switch (event.event) {
      case "execution_started":
        setProgress({ current: 0, total: event.total_steps })
        toast.info("Execution started", {
          description: `Running ${event.total_steps} steps`,
        })
        break

      case "step_started":
        setCurrentStep({ id: event.step_id, description: event.description })
        setProgress((prev) => ({ ...prev, current: event.step_index }))
        break

      case "step_completed":
        setLiveSteps((prev) => [
          ...prev,
          {
            step_id: event.step_id,
            status: event.status,
            duration_ms: event.duration_ms,
            attempt: event.attempt || 1,
            error: event.error || null,
            http_details: event.http_details,
            assertions_results: [],
          },
        ])
        setCurrentStep(null)
        break

      case "execution_complete":
        toast.success("Execution complete", {
          description: `${event.summary.passed}/${event.summary.total_steps} steps passed`,
        })
        setExecutionId(null)
        break
    }
  }, [])

  const { isConnected, error: wsError } = useExecutionWebSocket(executionId, {
    onEvent: handleWsEvent,
    autoConnect: true,
  })

  const handleExecute = async () => {
    try {
      let plan: Plan | undefined

      if (planJson.trim()) {
        plan = JSON.parse(planJson)
      } else {
        toast.error("No plan provided", {
          description: "Paste a plan JSON or select a saved plan",
        })
        return
      }

      // Reset live state
      setLiveSteps([])
      setCurrentStep(null)
      setProgress({ current: 0, total: 0 })

      const result = await execute.mutateAsync({
        plan,
        parallel,
        timeout,
        max_retries: maxRetries,
        dry_run: dryRun,
      })

      // If streaming is enabled, set execution ID to start WebSocket
      if (useStreaming && result.execution_id && !dryRun) {
        setExecutionId(result.execution_id)
      } else {
        toast.success("Execution complete", {
          description: `${result.summary.passed}/${result.summary.total_steps} steps passed`,
        })
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        toast.error("Invalid JSON", {
          description: "Please check your plan format",
        })
      } else {
        toast.error("Execution failed", {
          description: error instanceof Error ? error.message : "Unknown error",
        })
      }
    }
  }

  const handleStop = useCallback(() => {
    setExecutionId(null)
    setCurrentStep(null)
    toast.info("Execution stopped")
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Execute Plan</h1>
        <p className="text-muted-foreground">
          Run a test plan and view results in real-time
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileJson className="h-5 w-5" />
              Test Plan
            </CardTitle>
            <CardDescription>
              Provide a plan to execute
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="paste" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="paste">Paste JSON</TabsTrigger>
                <TabsTrigger value="select">Select Plan</TabsTrigger>
              </TabsList>

              <TabsContent value="paste" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label htmlFor="plan-json">Plan JSON</Label>
                  <div className="border rounded-lg overflow-hidden">
                    <Editor
                      height="400px"
                      language="json"
                      value={planJson}
                      onChange={(value) => setPlanJson(value || "")}
                      theme="vs-dark"
                      options={{
                        minimap: { enabled: false },
                        fontSize: 13,
                        lineNumbers: "on",
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        tabSize: 2,
                        wordWrap: "on",
                        formatOnPaste: true,
                        folding: true,
                      }}
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="select" className="space-y-4 mt-4">
                {!plansData?.plans || plansData.plans.length === 0 ? (
                  <div className="py-8 text-center text-muted-foreground">
                    <FileJson className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p className="font-medium">No plans available</p>
                    <p className="text-sm mb-4">Generate a plan first to execute it</p>
                    <Button asChild size="sm">
                      <Link href="/generate">
                        <Wand2 className="h-4 w-4 mr-2" />
                        Generate Plan
                      </Link>
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {plansData?.plans.map((plan) => (
                      <div
                        key={plan.id}
                        className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                          selectedPlanId === plan.id
                            ? "border-primary bg-primary/5"
                            : "hover:bg-muted"
                        }`}
                        onClick={() => setSelectedPlanId(plan.id)}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{plan.name}</span>
                          <Badge variant="outline">{plan.step_count} steps</Badge>
                        </div>
                        {plan.description && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {plan.description}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </TabsContent>
            </Tabs>

            {/* Execution Options */}
            <div className="mt-6 p-4 border rounded-lg bg-muted/30">
              <h4 className="text-sm font-medium mb-3">Execution Options</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="dry-run" className="text-sm">
                    Dry Run
                  </Label>
                  <Switch
                    id="dry-run"
                    checked={dryRun}
                    onCheckedChange={setDryRun}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="parallel" className="text-sm">
                    Parallel Execution
                  </Label>
                  <Switch
                    id="parallel"
                    checked={parallel}
                    onCheckedChange={setParallel}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="timeout" className="text-sm">
                    Timeout (seconds)
                  </Label>
                  <Input
                    id="timeout"
                    type="number"
                    min={1}
                    max={3600}
                    value={timeout}
                    onChange={(e) => setTimeout(Number(e.target.value))}
                    className="h-8"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="max-retries" className="text-sm">
                    Max Retries
                  </Label>
                  <Input
                    id="max-retries"
                    type="number"
                    min={0}
                    max={10}
                    value={maxRetries}
                    onChange={(e) => setMaxRetries(Number(e.target.value))}
                    className="h-8"
                  />
                </div>
              </div>
              {dryRun && (
                <p className="text-xs text-muted-foreground mt-2">
                  Dry run mode: Validates plan without executing HTTP requests
                </p>
              )}
              {parallel && (
                <p className="text-xs text-muted-foreground mt-2">
                  Parallel mode: Independent steps will run concurrently
                </p>
              )}

              {/* Streaming Toggle */}
              <div className="mt-4 pt-4 border-t flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label htmlFor="streaming" className="text-sm flex items-center gap-2">
                    {isConnected ? (
                      <Wifi className="h-4 w-4 text-green-500" />
                    ) : (
                      <WifiOff className="h-4 w-4 text-muted-foreground" />
                    )}
                    Live Streaming
                  </Label>
                  {isConnected && (
                    <Badge variant="outline" className="text-xs text-green-600 border-green-300">
                      <Radio className="h-3 w-3 mr-1 animate-pulse" />
                      Connected
                    </Badge>
                  )}
                </div>
                <Switch
                  id="streaming"
                  checked={useStreaming}
                  onCheckedChange={setUseStreaming}
                  disabled={dryRun}
                />
              </div>
            </div>

            <div className="mt-4 flex gap-2">
              <Button
                className="flex-1"
                onClick={handleExecute}
                disabled={execute.isPending || !!executionId}
              >
                {execute.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    {dryRun ? "Validate Plan" : "Execute Plan"}
                  </>
                )}
              </Button>
              {executionId && (
                <Button
                  variant="destructive"
                  onClick={handleStop}
                >
                  <Square className="mr-2 h-4 w-4" />
                  Stop
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg">Results</CardTitle>
                <CardDescription>
                  {executionId ? "Live execution in progress" : "Execution results will appear here"}
                </CardDescription>
              </div>
              {progress.total > 0 && (
                <Badge variant="outline">
                  {progress.current}/{progress.total} steps
                </Badge>
              )}
            </div>
            {progress.total > 0 && (
              <Progress
                value={(progress.current / progress.total) * 100}
                className="mt-2"
              />
            )}
          </CardHeader>
          <CardContent>
            {/* Live streaming view */}
            {executionId && (
              <div className="space-y-4">
                {currentStep && (
                  <div className="p-3 border rounded-lg bg-primary/5 border-primary/30 animate-pulse">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      <span className="font-medium text-sm">{currentStep.id}</span>
                    </div>
                    {currentStep.description && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {currentStep.description}
                      </p>
                    )}
                  </div>
                )}
                {liveSteps.length > 0 && (
                  <ScrollArea className="h-[400px]">
                    <div className="space-y-1">
                      {liveSteps.map((step, idx) => (
                        <StepResultItem key={`${step.step_id}-${idx}`} step={step} />
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </div>
            )}

            {/* Static result view */}
            {!executionId && execute.data ? (
              <ExecutionResults result={execute.data} />
            ) : !executionId && execute.isPending ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Running tests...</p>
              </div>
            ) : !executionId && liveSteps.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Play className="h-12 w-12 mb-4 opacity-50" />
                <p>No execution yet</p>
                <p className="text-sm">Provide a plan and click Execute</p>
              </div>
            )}

            {wsError && (
              <div className="p-3 border border-destructive/50 bg-destructive/10 rounded-lg mt-4">
                <p className="text-sm text-destructive">{wsError}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
