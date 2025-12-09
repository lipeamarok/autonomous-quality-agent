// API Types for AQA

// ============ UTDL Types ============
export interface Plan {
  spec_version: string
  meta?: PlanMeta
  config?: PlanConfig
  context?: PlanContext
  steps: Step[]
}

export interface PlanMeta {
  id?: string
  name: string
  description?: string
  version?: string
  tags?: string[]
  created_at?: string
  base_url?: string
}

export interface PlanConfig {
  base_url?: string
  timeout_ms?: number
  global_headers?: Record<string, string>
  variables?: Record<string, unknown>
}

export interface PlanContext {
  base_url?: string
  variables?: Record<string, unknown>
}

export interface Step {
  id: string
  description?: string
  action?: StepAction
  params?: Record<string, unknown>
  assertions?: Assertion[]
  extractions?: Extraction[]
  extract?: Extraction[]
  depends_on?: string[]
  recovery_policy?: RecoveryPolicy
  retry?: RetryPolicy
}

export interface StepAction {
  http?: HttpAction
  graphql?: GraphqlAction
  wait?: WaitAction
}

export interface HttpAction {
  method: string
  url: string
  headers?: Record<string, string>
  body?: unknown
  query?: Record<string, string>
}

export interface GraphqlAction {
  query: string
  variables?: Record<string, unknown>
  operation_name?: string
}

export interface WaitAction {
  duration_ms: number
}

export interface Assertion {
  expression: string
  message?: string
  type?: string
  source?: string
  path?: string
  operator?: string
  value?: unknown
}

export interface Extraction {
  variable: string
  from: string
  source?: string
  path?: string
  target?: string
  regex?: string
}

export interface RecoveryPolicy {
  strategy: "fail_fast" | "retry" | "ignore"
  max_attempts?: number
  backoff_ms?: number
}

export interface RetryPolicy {
  max_attempts: number
  delay_ms: number
  backoff?: string
}

// ============ API Response Types ============
export interface HealthResponse {
  status: string
  version: string
  timestamp?: string
  runner_available?: boolean
  brain_available?: boolean
  components?: {
    brain: string
    runner: string
    storage: string
    llm?: string
  }
}

// Generate
export interface GenerateRequest {
  requirement?: string
  swagger_url?: string
  swagger_content?: unknown
  base_url?: string
  options?: GenerateOptions
}

export interface GenerateOptions {
  include_negative?: boolean
  include_auth?: boolean
  include_refresh?: boolean
  all_auth_schemes?: boolean
  auth_scheme?: string
  max_steps?: number
  model?: string
  llm_mode?: "real" | "mock"
}

export interface GenerateResponse {
  success: boolean
  plan: Plan
  metadata: {
    generation_time_ms: number
    model_used: string
    tokens_used?: number
    llm_mode?: string
    cached?: boolean
  }
}

// Validate
export interface ValidateRequest {
  plan: Plan
  mode?: "default" | "strict"
}

export interface ValidateResponse {
  success: boolean
  is_valid: boolean
  error_count: number
  warning_count: number
  errors: string[]
  warnings: string[]
}

// Execute
export interface ExecuteRequest {
  plan?: Plan
  plan_id?: string
  context?: Record<string, unknown>
  dry_run?: boolean
  parallel?: boolean
  timeout?: number
  max_retries?: number
}

export interface ExecuteResponse {
  success: boolean
  execution_id: string
  plan_id?: string
  plan_name?: string
  summary: ExecutionSummary
  steps: StepResult[]
}

export interface ExecutionSummary {
  total_steps: number
  passed: number
  failed: number
  skipped: number
  duration_ms: number
  assertions_passed?: number
  assertions_failed?: number
  success_rate?: number
}

export interface StepResult {
  step_id: string
  status: "passed" | "failed" | "skipped"
  duration_ms: number
  attempt: number
  error?: string | null
  http_details?: HttpDetails | null
  assertions_results?: AssertionResult[]
  extractions?: Record<string, unknown>
}

export interface HttpDetails {
  method: string
  url: string
  status_code: number
  latency_ms: number
}

export interface AssertionResult {
  type: string
  operator: string
  expected: unknown
  actual: unknown
  passed: boolean
  path?: string
}

// History
export interface HistoryRecord {
  execution_id: string
  plan_id: string
  plan_name: string
  timestamp: string
  summary: ExecutionSummary
  status?: string
}

export interface HistoryResponse {
  success: boolean
  total: number
  page?: number
  per_page?: number
  records: HistoryRecord[]
}

export interface HistoryStats {
  total_executions: number
  success_rate: number
  avg_duration_ms: number
  executions_today: number
  executions_this_week?: number
  execution_trend?: TrendPoint[]
}

export interface TrendPoint {
  date: string
  total: number
  passed: number
  failed: number
}

export interface HistoryStatsResponse {
  success: boolean
  stats: HistoryStats
}

// Plans
export interface PlanSummary {
  id: string
  name: string
  description?: string
  tags?: string[]
  version?: string
  step_count: number
  created_at?: string
  updated_at?: string
  last_run_status?: "passed" | "failed" | null
  last_run_at?: string
}

export interface PlanListItem {
  id: string
  name: string
  description?: string
  tags?: string[]
  created_at: string
  updated_at?: string
  version?: number
  step_count: number
  last_execution?: {
    execution_id: string
    timestamp: string
    status: string
  }
}

export interface PlansResponse {
  success: boolean
  total: number
  plans: PlanSummary[]
}

// WebSocket Events
export interface WsExecutionStarted {
  event: "execution_started"
  execution_id: string
  plan_id: string
  plan_name: string
  total_steps: number
  timestamp: string
}

export interface WsStepStarted {
  event: "step_started"
  step_id: string
  description?: string
  step_index: number
  total_steps: number
  timestamp: string
}

export interface WsStepCompleted {
  event: "step_completed"
  step_id: string
  status: "passed" | "failed" | "skipped"
  duration_ms: number
  attempt?: number
  error?: string
  http_details?: HttpDetails
  timestamp: string
}

export interface WsExecutionComplete {
  event: "execution_complete"
  execution_id: string
  status: string
  summary: ExecutionSummary
  timestamp: string
}

export type WsEvent =
  | WsExecutionStarted
  | WsStepStarted
  | WsStepCompleted
  | WsExecutionComplete
