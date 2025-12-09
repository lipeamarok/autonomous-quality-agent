"use client"

import { useState, useRef } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useGenerate } from "@/lib/hooks/queries"
import {
  Wand2,
  Loader2,
  Upload,
  Link as LinkIcon,
  FileText,
  Play,
  Save,
  Copy,
  CheckCircle,
  FlaskConical,
  Brain,
  Settings2,
  ChevronDown,
} from "lucide-react"
import type { Plan } from "@/types/api"

const AVAILABLE_MODELS = [
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
  { value: "claude-3-opus", label: "Claude 3 Opus" },
  { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
]

const schema = z.object({
  requirement: z.string().optional(),
  swagger_url: z.string().optional(),
  swagger_file: z.any().optional(),
  base_url: z.string().optional(),
  include_negative: z.boolean(),
  include_auth: z.boolean(),
  include_refresh: z.boolean(),
  max_steps: z.number().min(1).max(50),
  model: z.string().optional(),
  llm_mode: z.enum(["real", "mock"]),
})

type FormData = z.infer<typeof schema>

export default function GeneratePage() {
  const generate = useGenerate()
  const [generatedPlan, setGeneratedPlan] = useState<Plan | null>(null)
  const [copied, setCopied] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [swaggerFileName, setSwaggerFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      requirement: "",
      swagger_url: "",
      base_url: "",
      include_negative: false,
      include_auth: false,
      include_refresh: false,
      max_steps: 10,
      model: "gpt-4-turbo",
      llm_mode: "real",
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      const result = await generate.mutateAsync({
        requirement: data.requirement || undefined,
        swagger_url: data.swagger_url || undefined,
        base_url: data.base_url || undefined,
        options: {
          include_negative: data.include_negative,
          include_auth: data.include_auth,
          include_refresh: data.include_refresh,
          max_steps: data.max_steps,
          model: data.model,
          llm_mode: data.llm_mode,
        },
      })

      setGeneratedPlan(result.plan)
      toast.success("Plan generated successfully", {
        description: `Created ${result.plan.steps.length} steps in ${result.metadata.generation_time_ms}ms`,
      })
    } catch (error) {
      toast.error("Generation failed", {
        description: error instanceof Error ? error.message : "Unknown error",
      })
    }
  }

  const handleCopy = async () => {
    if (generatedPlan) {
      await navigator.clipboard.writeText(JSON.stringify(generatedPlan, null, 2))
      setCopied(true)
      toast.success("Copied to clipboard")
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Generate Test Plan</h1>
        <p className="text-muted-foreground">
          Create a test plan from requirements or OpenAPI specification
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Wand2 className="h-5 w-5" />
              Input
            </CardTitle>
            <CardDescription>
              Describe what you want to test or provide an OpenAPI spec
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <Tabs defaultValue="requirement" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="requirement" className="gap-2">
                    <FileText className="h-4 w-4" />
                    Requirement
                  </TabsTrigger>
                  <TabsTrigger value="openapi" className="gap-2">
                    <LinkIcon className="h-4 w-4" />
                    OpenAPI
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="requirement" className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label htmlFor="requirement">Test Requirement</Label>
                    <Textarea
                      id="requirement"
                      placeholder="Describe what you want to test...&#10;&#10;Example: Test the login API with valid and invalid credentials, verify token is returned on success"
                      className="min-h-[150px] resize-none"
                      {...form.register("requirement")}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="openapi" className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label htmlFor="swagger_url">OpenAPI URL</Label>
                    <Input
                      id="swagger_url"
                      type="url"
                      placeholder="https://api.example.com/openapi.json"
                      {...form.register("swagger_url")}
                    />
                  </div>
                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-card px-2 text-muted-foreground">or</span>
                    </div>
                  </div>
                  <div
                    className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".yaml,.yml,.json"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) {
                          setSwaggerFileName(file.name)
                          const reader = new FileReader()
                          reader.onload = (event) => {
                            form.setValue("swagger_file", event.target?.result)
                          }
                          reader.readAsText(file)
                        }
                      }}
                    />
                    <Upload className="h-8 w-8 mx-auto text-muted-foreground" />
                    {swaggerFileName ? (
                      <p className="mt-2 text-sm font-medium text-primary">
                        {swaggerFileName}
                      </p>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">
                        Click to upload OpenAPI file (.yaml, .json)
                      </p>
                    )}
                  </div>
                </TabsContent>
              </Tabs>

              <div className="space-y-2">
                <Label htmlFor="base_url">Base URL</Label>
                <Input
                  id="base_url"
                  type="url"
                  placeholder="https://api.example.com"
                  {...form.register("base_url")}
                />
                <p className="text-xs text-muted-foreground">
                  The base URL for API requests
                </p>
              </div>

              {/* LLM Mode Toggle - Top Priority */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border">
                <div className="flex items-center gap-2">
                  <FlaskConical className="h-4 w-4 text-primary" />
                  <div className="space-y-0.5">
                    <Label htmlFor="llm_mode">Mock Mode</Label>
                    <p className="text-xs text-muted-foreground">
                      Use mock responses (no API calls)
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={form.watch("llm_mode") === "mock" ? "default" : "outline"}
                    className="text-xs"
                  >
                    {form.watch("llm_mode") === "mock" ? "Mock" : "Real"}
                  </Badge>
                  <Switch
                    id="llm_mode"
                    checked={form.watch("llm_mode") === "mock"}
                    onCheckedChange={(v) => form.setValue("llm_mode", v ? "mock" : "real")}
                  />
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t">
                <h4 className="text-sm font-medium">Options</h4>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="include_negative">Negative Cases</Label>
                    <p className="text-xs text-muted-foreground">
                      Include error scenarios
                    </p>
                  </div>
                  <Switch
                    id="include_negative"
                    checked={form.watch("include_negative")}
                    onCheckedChange={(v) => form.setValue("include_negative", v)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="include_auth">Auth Tests</Label>
                    <p className="text-xs text-muted-foreground">
                      Include authentication flows
                    </p>
                  </div>
                  <Switch
                    id="include_auth"
                    checked={form.watch("include_auth")}
                    onCheckedChange={(v) => form.setValue("include_auth", v)}
                  />
                </div>

                {/* Show refresh token option when auth is enabled */}
                {form.watch("include_auth") && (
                  <div className="flex items-center justify-between pl-4 border-l-2 border-muted">
                    <div className="space-y-0.5">
                      <Label htmlFor="include_refresh">Refresh Token</Label>
                      <p className="text-xs text-muted-foreground">
                        Include token refresh flow
                      </p>
                    </div>
                    <Switch
                      id="include_refresh"
                      checked={form.watch("include_refresh")}
                      onCheckedChange={(v) => form.setValue("include_refresh", v)}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="max_steps">Max Steps</Label>
                  <Input
                    id="max_steps"
                    type="number"
                    min={1}
                    max={50}
                    className="w-24"
                    {...form.register("max_steps", { valueAsNumber: true })}
                  />
                </div>
              </div>

              {/* Advanced Options */}
              <div className="pt-4 border-t">
                <button
                  type="button"
                  className="flex items-center justify-between w-full text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  <div className="flex items-center gap-2">
                    <Settings2 className="h-4 w-4" />
                    Advanced Options
                  </div>
                  <ChevronDown className={`h-4 w-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`} />
                </button>

                {showAdvanced && (
                  <div className="mt-4 space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="model">LLM Model</Label>
                      <Select
                        value={form.watch("model")}
                        onValueChange={(v) => form.setValue("model", v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select model" />
                        </SelectTrigger>
                        <SelectContent>
                          {AVAILABLE_MODELS.map((model) => (
                            <SelectItem key={model.value} value={model.value}>
                              <div className="flex items-center gap-2">
                                <Brain className="h-4 w-4" />
                                {model.label}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        AI model used for plan generation
                      </p>
                    </div>
                  </div>
                )}
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={generate.isPending}
              >
                {generate.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Wand2 className="mr-2 h-4 w-4" />
                    Generate Plan
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg">Generated Plan</CardTitle>
                <CardDescription>
                  {generatedPlan
                    ? `${generatedPlan.steps.length} steps generated`
                    : "Your plan will appear here"}
                </CardDescription>
              </div>
              {generatedPlan && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleCopy}>
                    {copied ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                  <Button variant="outline" size="sm">
                    <Save className="h-4 w-4" />
                  </Button>
                  <Button size="sm">
                    <Play className="h-4 w-4 mr-1" />
                    Execute
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {generatedPlan ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  {generatedPlan.meta?.id && (
                    <Badge variant="outline">{generatedPlan.meta.id}</Badge>
                  )}
                  {(generatedPlan.config?.base_url || generatedPlan.context?.base_url) && (
                    <Badge>{generatedPlan.config?.base_url || generatedPlan.context?.base_url}</Badge>
                  )}
                </div>
                <div className="bg-muted rounded-lg overflow-hidden">
                  <pre className="p-4 overflow-auto max-h-[500px] text-xs">
                    {JSON.stringify(generatedPlan, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Wand2 className="h-12 w-12 mb-4 opacity-50" />
                <p>No plan generated yet</p>
                <p className="text-sm">Fill in the form and click Generate</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
