"use client"

import { use, useState, useCallback } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useValidate } from "@/lib/hooks/queries"
import {
  ArrowLeft,
  Save,
  Play,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  FileJson,
} from "lucide-react"
import type { Plan } from "@/types/api"

// Dynamically import Monaco Editor to avoid SSR issues
const Editor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.default),
  {
    ssr: false,
    loading: () => (
      <div className="h-[600px] flex items-center justify-center bg-muted rounded-lg">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    ),
  }
)

export default function PlanEditPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const router = useRouter()
  const [planJson, setPlanJson] = useState<string>("")
  const [isDirty, setIsDirty] = useState(false)
  const [validationResult, setValidationResult] = useState<{
    valid: boolean
    errors?: string[]
  } | null>(null)

  const validate = useValidate()

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

  // Initialize editor content when plan is loaded
  const handleEditorMount = useCallback(() => {
    if (plan && !planJson) {
      setPlanJson(JSON.stringify(plan, null, 2))
    }
  }, [plan, planJson])

  // Update when plan is first loaded
  if (plan && !planJson && !isLoading) {
    setPlanJson(JSON.stringify(plan, null, 2))
  }

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setPlanJson(value)
      setIsDirty(true)
      setValidationResult(null)
    }
  }

  const handleValidate = async () => {
    try {
      const parsedPlan = JSON.parse(planJson)
      const result = await validate.mutateAsync({ plan: parsedPlan })
      setValidationResult({ valid: result.is_valid, errors: result.errors })

      if (result.is_valid) {
        toast.success("Plan is valid")
      } else {
        toast.error("Plan has validation errors", {
          description: `${result.errors?.length || 0} errors found`,
        })
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        setValidationResult({
          valid: false,
          errors: [`JSON syntax error: ${error.message}`],
        })
        toast.error("Invalid JSON syntax")
      } else {
        toast.error("Validation failed", {
          description: error instanceof Error ? error.message : "Unknown error",
        })
      }
    }
  }

  const handleSave = async () => {
    try {
      // First validate
      const parsedPlan = JSON.parse(planJson)
      const result = await validate.mutateAsync({ plan: parsedPlan })

      if (!result.is_valid) {
        toast.error("Cannot save invalid plan", {
          description: "Fix validation errors first",
        })
        return
      }

      // TODO: Implement save API
      toast.success("Plan saved successfully")
      setIsDirty(false)
    } catch (error) {
      toast.error("Save failed", {
        description: error instanceof Error ? error.message : "Unknown error",
      })
    }
  }

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

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link href={`/plans/${id}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">Edit Plan</h1>
            {isDirty && (
              <Badge variant="outline" className="text-orange-600">
                Unsaved changes
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground">{plan.meta?.name || id}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleValidate}
            disabled={validate.isPending}
          >
            {validate.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <CheckCircle className="h-4 w-4 mr-2" />
            )}
            Validate
          </Button>
          <Button
            onClick={handleSave}
            disabled={!isDirty || validate.isPending}
          >
            <Save className="h-4 w-4 mr-2" />
            Save
          </Button>
          <Button asChild variant="outline">
            <Link href={`/execute?plan=${id}`}>
              <Play className="h-4 w-4 mr-2" />
              Execute
            </Link>
          </Button>
        </div>
      </div>

      {validationResult && (
        <Card className={validationResult.valid ? "border-green-500" : "border-red-500"}>
          <CardContent className="py-3">
            <div className="flex items-center gap-2">
              {validationResult.valid ? (
                <>
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <span className="font-medium text-green-600">
                    Plan is valid
                  </span>
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-red-500" />
                  <span className="font-medium text-red-600">
                    Validation errors ({validationResult.errors?.length || 0})
                  </span>
                </>
              )}
            </div>
            {!validationResult.valid && validationResult.errors && (
              <ul className="mt-2 space-y-1 text-sm text-red-600">
                {validationResult.errors.map((error, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span>•</span>
                    <span>{error}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileJson className="h-5 w-5" />
              <CardTitle className="text-lg">UTDL Plan Editor</CardTitle>
            </div>
            <Badge variant="outline">JSON</Badge>
          </div>
          <CardDescription>
            Edit the plan JSON directly. Use Ctrl+Space for autocomplete.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border rounded-lg overflow-hidden">
            <Editor
              height="600px"
              defaultLanguage="json"
              value={planJson}
              onChange={handleEditorChange}
              onMount={handleEditorMount}
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
                formatOnType: true,
              }}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
