# Interface Reference Document — AQA Web UI

> **Objetivo**: Guia completo para implementação da interface web do Autonomous Quality Agent (AQA), incluindo arquitetura, stack tecnológico, componentes, e integração com a API REST existente.

**Versão:** 1.0.0 (Contrato Congelado)
**Última atualização:** 2024-12-08
**Status:** ✅ FROZEN — Contrato de Interface para UI

> ⚠️ **AVISO**: Este documento está **congelado como v1.0.0**. Qualquer alteração na API ou nos contratos de dados deve:
> 1. Incrementar a versão do documento
> 2. Manter retrocompatibilidade ou documentar breaking changes
> 3. Atualizar o `openapi.json` correspondente

---

## 📋 Pontos de Atenção para Implementação

Estes pontos **NÃO bloqueiam** o início da UI, mas devem ser considerados:

| # | Ponto | Tratamento na UI |
|---|-------|------------------|
| 1 | Campos opcionais podem vir vazios | Usar optional chaining e defaults |
| 2 | Dois modos de execução (REST/WebSocket) | REST para planos pequenos, WS para longos, fallback gracioso |
| 3 | Workspace Init depende de filesystem | Modo desktop: custom path. Modo SaaS: path fixo |
| 4 | IDs de execução são numéricos | Tratar como `string \| number` |
| 5 | Telemetria OTEL não é MVP | Placeholder para fase futura |

---

## 🚀 Quick Start — Resumo Executivo

### Stack Tecnológico Definido

| Camada | Tecnologia | Versão | Propósito |
|--------|------------|--------|-----------|
| **Framework** | Next.js | 15.x (App Router) | SSR, Routing, API Routes |
| **UI Library** | React | 19.x | Componentes reativos |
| **Styling** | TailwindCSS | 4.x | Utility-first CSS |
| **Components** | shadcn/ui | latest | Componentes acessíveis e customizáveis |
| **State/Data** | TanStack Query | 5.x | Server state, caching, mutations |
| **Editor** | Monaco Editor | latest | Editor de código (UTDL/JSON) |
| **Icons** | Lucide React | latest | Ícones consistentes |
| **Forms** | React Hook Form + Zod | latest | Validação de formulários |
| **Charts** | Recharts | 2.x | Visualização de métricas |
| **WebSocket** | Native + React hooks | - | Execução real-time |

### Fases de Implementação

| Fase | Escopo | Páginas/Features | Prioridade |
|------|--------|------------------|------------|
| **1 - MVP** | Core funcional | Dashboard, Generate, Execute, History | P0 |
| **2 - Editor** | Edição avançada | Plan Editor (Monaco), Validation | P1 |
| **3 - Analytics** | Métricas e insights | Reports, Charts, Trends | P2 |
| **4 - Enterprise** | Multi-tenant, Auth | Teams, RBAC, SSO | P3 |

### Estrutura de Diretórios (UI)

```
ui/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── .env.local.example
├── components.json              # shadcn/ui config
│
├── app/                         # Next.js App Router
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Dashboard (home)
│   ├── globals.css             # Global styles
│   │
│   ├── generate/
│   │   └── page.tsx            # Geração de planos
│   │
│   ├── plans/
│   │   ├── page.tsx            # Lista de planos
│   │   └── [id]/
│   │       ├── page.tsx        # Detalhes do plano
│   │       └── edit/
│   │           └── page.tsx    # Editor Monaco
│   │
│   ├── execute/
│   │   └── page.tsx            # Execução de planos
│   │
│   ├── history/
│   │   ├── page.tsx            # Lista de execuções
│   │   └── [id]/
│   │       └── page.tsx        # Detalhes da execução
│   │
│   └── settings/
│       └── page.tsx            # Configurações
│
├── components/
│   ├── ui/                     # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── tabs.tsx
│   │   ├── toast.tsx
│   │   └── ...
│   │
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   ├── nav-item.tsx
│   │   └── theme-toggle.tsx
│   │
│   ├── dashboard/
│   │   ├── stats-cards.tsx
│   │   ├── recent-executions.tsx
│   │   └── quick-actions.tsx
│   │
│   ├── generate/
│   │   ├── generate-form.tsx
│   │   ├── swagger-upload.tsx
│   │   ├── requirement-input.tsx
│   │   └── generation-options.tsx
│   │
│   ├── plans/
│   │   ├── plan-card.tsx
│   │   ├── plan-list.tsx
│   │   ├── plan-viewer.tsx
│   │   └── step-item.tsx
│   │
│   ├── editor/
│   │   ├── monaco-editor.tsx
│   │   ├── json-schema-validator.tsx
│   │   └── editor-toolbar.tsx
│   │
│   ├── execute/
│   │   ├── execution-panel.tsx
│   │   ├── step-progress.tsx
│   │   ├── live-logs.tsx
│   │   └── result-summary.tsx
│   │
│   └── history/
│       ├── execution-table.tsx
│       ├── execution-details.tsx
│       └── step-result-card.tsx
│
├── lib/
│   ├── api/
│   │   ├── client.ts           # Axios/fetch wrapper
│   │   ├── endpoints.ts        # API endpoints
│   │   └── types.ts            # TypeScript types from API
│   │
│   ├── hooks/
│   │   ├── use-generate.ts     # TanStack Query hooks
│   │   ├── use-execute.ts
│   │   ├── use-plans.ts
│   │   ├── use-history.ts
│   │   └── use-websocket.ts    # WebSocket hook
│   │
│   ├── utils/
│   │   ├── cn.ts               # className utility
│   │   ├── format.ts           # Formatters
│   │   └── validators.ts       # Zod schemas
│   │
│   └── store/
│       └── app-store.ts        # Zustand (se necessário)
│
├── public/
│   ├── logo.svg
│   └── favicon.ico
│
└── types/
    ├── api.d.ts                # API response types
    ├── utdl.d.ts               # UTDL schema types
    └── index.d.ts
```

---

## 📋 Checklist de Implementação

### Fase 1 — MVP (Semana 1-2)

#### Setup Inicial
- [ ] Criar projeto Next.js 15 com TypeScript
- [ ] Configurar TailwindCSS 4
- [ ] Instalar e configurar shadcn/ui
- [ ] Configurar TanStack Query provider
- [ ] Criar estrutura de diretórios
- [ ] Configurar ESLint + Prettier
- [ ] Criar .env.local com API_URL

#### Layout Base
- [ ] Implementar Sidebar com navegação
- [ ] Implementar Header com breadcrumbs
- [ ] Implementar Theme Toggle (dark/light)
- [ ] Criar loading states globais
- [ ] Criar error boundaries

#### Dashboard (/)
- [ ] Cards de estatísticas (execuções, taxa sucesso, etc.)
- [ ] Lista de execuções recentes
- [ ] Quick actions (Generate, Execute)
- [ ] Integrar com GET /api/v1/history/stats

#### Geração (/generate)
- [ ] Form de upload Swagger (file + URL)
- [ ] Textarea para requisitos
- [ ] Opções de geração (toggles)
- [ ] Preview do plano gerado
- [ ] Ações: Salvar, Executar, Editar
- [ ] Integrar com POST /api/v1/generate

#### Execução (/execute)
- [ ] Seletor de plano (dropdown ou upload)
- [ ] Painel de progresso em tempo real
- [ ] WebSocket para streaming de steps
- [ ] Visualização de resultados
- [ ] Integrar com POST /api/v1/execute
- [ ] Integrar com WebSocket /ws/execute

#### Histórico (/history)
- [ ] Tabela paginada de execuções
- [ ] Filtros (status, data, plano)
- [ ] Detalhes expandíveis
- [ ] Link para execução completa
- [ ] Integrar com GET /api/v1/history

### Fase 2 — Editor (Semana 3)

#### Editor de Planos (/plans/[id]/edit)
- [ ] Integrar Monaco Editor
- [ ] Syntax highlighting para JSON
- [ ] Schema validation inline
- [ ] Autocomplete para UTDL
- [ ] Toolbar (save, validate, format)
- [ ] Split view (code + preview)

#### Validação em Tempo Real
- [ ] Debounced validation
- [ ] Error markers no editor
- [ ] Panel de erros clicáveis
- [ ] Integrar com POST /api/v1/validate

### Fase 3 — Analytics (Semana 4)

#### Reports e Charts
- [ ] Gráfico de taxa de sucesso (Recharts)
- [ ] Gráfico de duração média
- [ ] Heatmap de falhas por step
- [ ] Export para PDF/CSV

---

## 🎨 Design System

### Cores (TailwindCSS + CSS Variables)

```css
/* globals.css - Theme colors via CSS variables para dark/light mode */
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --card: 0 0% 100%;
  --card-foreground: 222.2 84% 4.9%;
  --popover: 0 0% 100%;
  --popover-foreground: 222.2 84% 4.9%;
  --primary: 221.2 83.2% 53.3%;      /* Blue - ações principais */
  --primary-foreground: 210 40% 98%;
  --secondary: 210 40% 96.1%;
  --secondary-foreground: 222.2 47.4% 11.2%;
  --muted: 210 40% 96.1%;
  --muted-foreground: 215.4 16.3% 46.9%;
  --accent: 210 40% 96.1%;
  --accent-foreground: 222.2 47.4% 11.2%;
  --destructive: 0 84.2% 60.2%;      /* Red - erros, falhas */
  --destructive-foreground: 210 40% 98%;
  --success: 142.1 76.2% 36.3%;      /* Green - sucesso */
  --success-foreground: 210 40% 98%;
  --warning: 38 92% 50%;             /* Amber - warnings */
  --warning-foreground: 210 40% 98%;
  --border: 214.3 31.8% 91.4%;
  --input: 214.3 31.8% 91.4%;
  --ring: 221.2 83.2% 53.3%;
  --radius: 0.5rem;
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  /* ... dark mode variants */
}
```

### Cores Semânticas para Status

| Status | Cor | Classe TailwindCSS | Uso |
|--------|-----|-------------------|-----|
| **Passed** | Verde | `text-success bg-success/10` | Steps aprovados |
| **Failed** | Vermelho | `text-destructive bg-destructive/10` | Steps falhos |
| **Skipped** | Cinza | `text-muted-foreground bg-muted` | Steps pulados |
| **Running** | Azul | `text-primary bg-primary/10` | Em execução |
| **Pending** | Amarelo | `text-warning bg-warning/10` | Aguardando |

### Tipografia

```typescript
// tailwind.config.ts
const config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
}
```

| Elemento | Classe | Uso |
|----------|--------|-----|
| Heading 1 | `text-3xl font-bold` | Títulos de página |
| Heading 2 | `text-2xl font-semibold` | Seções |
| Heading 3 | `text-xl font-medium` | Subseções |
| Body | `text-base` | Texto padrão |
| Small | `text-sm text-muted-foreground` | Descrições |
| Mono | `font-mono text-sm` | Código, IDs |

### Componentes Base (shadcn/ui)

Componentes necessários a instalar:

```bash
npx shadcn@latest add button card dialog dropdown-menu input label \
  select separator sheet skeleton table tabs textarea toast tooltip \
  badge progress scroll-area command popover calendar avatar
```

### Ícones (Lucide React)

```bash
npm install lucide-react
```

| Ação | Ícone | Import |
|------|-------|--------|
| Generate | `Wand2` | `import { Wand2 } from 'lucide-react'` |
| Execute/Run | `Play` | `import { Play } from 'lucide-react'` |
| Stop | `Square` | `import { Square } from 'lucide-react'` |
| Validate | `CheckCircle2` | `import { CheckCircle2 } from 'lucide-react'` |
| Edit | `Pencil` | `import { Pencil } from 'lucide-react'` |
| Delete | `Trash2` | `import { Trash2 } from 'lucide-react'` |
| History | `History` | `import { History } from 'lucide-react'` |
| Settings | `Settings` | `import { Settings } from 'lucide-react'` |
| Plan | `FileJson` | `import { FileJson } from 'lucide-react'` |
| Dashboard | `LayoutDashboard` | `import { LayoutDashboard } from 'lucide-react'` |
| Success | `CheckCircle` | `import { CheckCircle } from 'lucide-react'` |
| Error | `XCircle` | `import { XCircle } from 'lucide-react'` |
| Warning | `AlertTriangle` | `import { AlertTriangle } from 'lucide-react'` |
| Info | `Info` | `import { Info } from 'lucide-react'` |
| Loading | `Loader2` | `import { Loader2 } from 'lucide-react'` |

---

## 🔧 Setup Detalhado

### Passo 1: Criar Projeto Next.js

```bash
# Criar projeto Next.js 15 com TypeScript
npx create-next-app@latest ui --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"

cd ui

# Estrutura criada:
# ui/
# ├── src/
# │   └── app/
# │       ├── layout.tsx
# │       ├── page.tsx
# │       └── globals.css
# ├── public/
# ├── next.config.ts
# ├── tailwind.config.ts
# ├── tsconfig.json
# └── package.json
```

### Passo 2: Configurar shadcn/ui

```bash
# Inicializar shadcn/ui
npx shadcn@latest init

# Responder as perguntas:
# - Style: Default
# - Base color: Slate
# - CSS variables: Yes
# - React Server Components: Yes
# - Components directory: src/components
# - Utilities: src/lib/utils

# Instalar componentes base
npx shadcn@latest add button card input label select textarea \
  dialog sheet tabs toast badge progress table skeleton \
  dropdown-menu command popover scroll-area separator avatar tooltip
```

### Passo 3: Instalar Dependências Adicionais

```bash
# TanStack Query para data fetching
npm install @tanstack/react-query @tanstack/react-query-devtools

# Monaco Editor para editor de código
npm install @monaco-editor/react

# React Hook Form + Zod para formulários
npm install react-hook-form @hookform/resolvers zod

# Recharts para gráficos
npm install recharts

# Ícones
npm install lucide-react

# Date utilities
npm install date-fns

# Class variance authority (já vem com shadcn)
npm install class-variance-authority clsx tailwind-merge
```

### Passo 4: Configurar Variáveis de Ambiente

```bash
# ui/.env.local.example
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_WS_URL=ws://localhost:8080
```

### Passo 5: Configurar TanStack Query Provider

```typescript
// src/lib/providers.tsx
'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minuto
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
```

```typescript
// src/app/layout.tsx
import { Providers } from '@/lib/providers'
import { Toaster } from '@/components/ui/toaster'
import './globals.css'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body>
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}
```

---

## 🌐 API Client e Hooks

### API Client Base

```typescript
// src/lib/api/client.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      error.code || 'UNKNOWN',
      error.message || 'An error occurred',
      error.details
    )
  }
  return response.json()
}

export const api = {
  get: async <T>(path: string): Promise<T> => {
    const response = await fetch(`${API_URL}${path}`)
    return handleResponse<T>(response)
  },

  post: async <T>(path: string, body?: unknown): Promise<T> => {
    const response = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  delete: async <T>(path: string): Promise<T> => {
    const response = await fetch(`${API_URL}${path}`, { method: 'DELETE' })
    return handleResponse<T>(response)
  },
}
```

### Types (TypeScript)

```typescript
// src/types/api.ts

// ============ UTDL Types ============
export interface Plan {
  spec_version: string
  meta: PlanMeta
  config: PlanConfig
  steps: Step[]
}

export interface PlanMeta {
  id: string
  name: string
  description?: string
  tags?: string[]
  created_at?: string
}

export interface PlanConfig {
  base_url: string
  timeout_ms?: number
  global_headers?: Record<string, string>
  variables?: Record<string, unknown>
}

export interface Step {
  id: string
  description?: string
  action: string
  params: Record<string, unknown>
  assertions?: Assertion[]
  extract?: Extraction[]
  depends_on?: string[]
  recovery_policy?: RecoveryPolicy
}

export interface Assertion {
  type: string
  source?: string
  path?: string
  operator: string
  value: unknown
}

export interface Extraction {
  source: string
  path: string
  target: string
  regex?: string
}

export interface RecoveryPolicy {
  strategy: 'fail_fast' | 'retry' | 'ignore'
  max_attempts?: number
  backoff_ms?: number
}

// ============ API Response Types ============
export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: ApiErrorDetail
}

export interface ApiErrorDetail {
  code: string
  message: string
  details?: unknown
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
  max_steps?: number
  model?: string
}

export interface GenerateResponse {
  success: boolean
  plan: Plan
  metadata: {
    generation_time_ms: number
    model_used: string
    tokens_used?: number
  }
}

// Validate
export interface ValidateRequest {
  plan: Plan
  mode?: 'default' | 'strict'
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
}

export interface ExecuteResponse {
  success: boolean
  execution_id: string
  summary: ExecutionSummary
  steps: StepResult[]
}

export interface ExecutionSummary {
  total_steps: number
  passed: number
  failed: number
  skipped: number
  duration_ms: number
}

export interface StepResult {
  step_id: string
  status: 'passed' | 'failed' | 'skipped'
  duration_ms: number
  attempt: number
  error?: string
  http_details?: HttpDetails
}

export interface HttpDetails {
  method: string
  url: string
  status_code: number
  latency_ms: number
}

// History
export interface HistoryRecord {
  execution_id: string
  plan_id: string
  plan_name: string
  timestamp: string
  summary: ExecutionSummary
}

export interface HistoryResponse {
  success: boolean
  total: number
  records: HistoryRecord[]
}

export interface HistoryStatsResponse {
  success: boolean
  stats: {
    total_executions: number
    success_rate: number
    avg_duration_ms: number
    executions_today: number
  }
}

// WebSocket Events
export interface WsStepStarted {
  event: 'step_started'
  step_id: string
  description?: string
}

export interface WsStepCompleted {
  event: 'step_completed'
  step_id: string
  status: 'passed' | 'failed' | 'skipped'
  duration_ms: number
}

export interface WsExecutionComplete {
  event: 'execution_complete'
  result: ExecuteResponse
}

export type WsEvent = WsStepStarted | WsStepCompleted | WsExecutionComplete
```

### TanStack Query Hooks

```typescript
// src/lib/hooks/use-generate.ts
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api/client'
import type { GenerateRequest, GenerateResponse } from '@/types/api'

export function useGenerate() {
  return useMutation({
    mutationFn: (data: GenerateRequest) =>
      api.post<GenerateResponse>('/api/v1/generate', data),
  })
}
```

```typescript
// src/lib/hooks/use-execute.ts
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api/client'
import type { ExecuteRequest, ExecuteResponse } from '@/types/api'

export function useExecute() {
  return useMutation({
    mutationFn: (data: ExecuteRequest) =>
      api.post<ExecuteResponse>('/api/v1/execute', data),
  })
}
```

```typescript
// src/lib/hooks/use-history.ts
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api/client'
import type { HistoryResponse, HistoryStatsResponse } from '@/types/api'

export function useHistory(limit = 20) {
  return useQuery({
    queryKey: ['history', limit],
    queryFn: () => api.get<HistoryResponse>(`/api/v1/history?limit=${limit}`),
  })
}

export function useHistoryStats() {
  return useQuery({
    queryKey: ['history', 'stats'],
    queryFn: () => api.get<HistoryStatsResponse>('/api/v1/history/stats'),
  })
}

export function useExecutionDetails(executionId: string) {
  return useQuery({
    queryKey: ['history', executionId],
    queryFn: () => api.get<HistoryResponse>(`/api/v1/history/${executionId}`),
    enabled: !!executionId,
  })
}
```

```typescript
// src/lib/hooks/use-websocket.ts
import { useEffect, useRef, useState, useCallback } from 'react'
import type { WsEvent } from '@/types/api'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8080'

export function useExecutionWebSocket(executionId: string | null) {
  const ws = useRef<WebSocket | null>(null)
  const [events, setEvents] = useState<WsEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)

  const connect = useCallback(() => {
    if (!executionId) return

    ws.current = new WebSocket(`${WS_URL}/ws/execute/${executionId}`)

    ws.current.onopen = () => setIsConnected(true)
    ws.current.onclose = () => setIsConnected(false)
    ws.current.onerror = () => setIsConnected(false)

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data) as WsEvent
      setEvents((prev) => [...prev, data])
    }
  }, [executionId])

  const disconnect = useCallback(() => {
    ws.current?.close()
    ws.current = null
    setEvents([])
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { events, isConnected, disconnect }
}
```

---

## 📄 Componentes Principais

### Layout - Sidebar

```typescript
// src/components/layout/sidebar.tsx
'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Wand2,
  FileJson,
  Play,
  History,
  Settings,
} from 'lucide-react'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/generate', label: 'Generate', icon: Wand2 },
  { href: '/plans', label: 'Plans', icon: FileJson },
  { href: '/execute', label: 'Execute', icon: Play },
  { href: '/history', label: 'History', icon: History },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-64 border-r bg-card h-screen sticky top-0">
      <div className="p-6">
        <h1 className="text-xl font-bold">AQA</h1>
        <p className="text-sm text-muted-foreground">
          Autonomous Quality Agent
        </p>
      </div>

      <nav className="px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground'
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
```

### Dashboard - Stats Cards

```typescript
// src/components/dashboard/stats-cards.tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useHistoryStats } from '@/lib/hooks/use-history'
import { CheckCircle, XCircle, Clock, Activity } from 'lucide-react'

export function StatsCards() {
  const { data, isLoading } = useHistoryStats()

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const stats = data?.stats

  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium">Total Executions</CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats?.total_executions ?? 0}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
          <CheckCircle className="h-4 w-4 text-success" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {((stats?.success_rate ?? 0) * 100).toFixed(1)}%
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium">Avg Duration</CardTitle>
          <Clock className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {((stats?.avg_duration_ms ?? 0) / 1000).toFixed(2)}s
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium">Today</CardTitle>
          <Activity className="h-4 w-4 text-primary" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats?.executions_today ?? 0}</div>
        </CardContent>
      </Card>
    </div>
  )
}
```

### Generate Form

```typescript
// src/components/generate/generate-form.tsx
'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { useGenerate } from '@/lib/hooks/use-generate'
import { useToast } from '@/components/ui/use-toast'
import { Wand2, Loader2 } from 'lucide-react'

const schema = z.object({
  requirement: z.string().optional(),
  swagger_url: z.string().url().optional().or(z.literal('')),
  base_url: z.string().url().optional().or(z.literal('')),
  include_negative: z.boolean().default(false),
  include_auth: z.boolean().default(false),
  max_steps: z.number().min(1).max(50).default(10),
})

type FormData = z.infer<typeof schema>

export function GenerateForm() {
  const { toast } = useToast()
  const generate = useGenerate()
  const [generatedPlan, setGeneratedPlan] = useState<unknown>(null)

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      requirement: '',
      swagger_url: '',
      base_url: '',
      include_negative: false,
      include_auth: false,
      max_steps: 10,
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
          max_steps: data.max_steps,
        },
      })

      setGeneratedPlan(result.plan)
      toast({
        title: 'Plan Generated!',
        description: `Created ${result.plan.steps.length} steps in ${result.metadata.generation_time_ms}ms`,
      })
    } catch (error) {
      toast({
        title: 'Generation Failed',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      })
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5" />
            Generate Test Plan
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="requirement">Requirement (optional)</Label>
              <Textarea
                id="requirement"
                placeholder="Describe what you want to test..."
                {...form.register('requirement')}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="swagger_url">OpenAPI URL (optional)</Label>
              <Input
                id="swagger_url"
                type="url"
                placeholder="https://api.example.com/openapi.json"
                {...form.register('swagger_url')}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="base_url">Base URL</Label>
              <Input
                id="base_url"
                type="url"
                placeholder="https://api.example.com"
                {...form.register('base_url')}
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="include_negative">Include Negative Cases</Label>
              <Switch
                id="include_negative"
                checked={form.watch('include_negative')}
                onCheckedChange={(v) => form.setValue('include_negative', v)}
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="include_auth">Include Auth Tests</Label>
              <Switch
                id="include_auth"
                checked={form.watch('include_auth')}
                onCheckedChange={(v) => form.setValue('include_auth', v)}
              />
            </div>

            <Button type="submit" className="w-full" disabled={generate.isPending}>
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

      {generatedPlan && (
        <Card>
          <CardHeader>
            <CardTitle>Generated Plan</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-muted p-4 rounded-lg overflow-auto max-h-96 text-sm">
              {JSON.stringify(generatedPlan, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
```

---

## 🔗 Integração com API Existente

A UI se conecta diretamente à API REST implementada em `brain/src/api/`. Abaixo está o mapeamento completo:

### Endpoints e Componentes

| Endpoint | Método | Componente UI | Hook |
|----------|--------|---------------|------|
| `/health` | GET | StatusIndicator | `useHealth()` |
| `/api/v1/generate` | POST | GenerateForm | `useGenerate()` |
| `/api/v1/validate` | POST | PlanValidator | `useValidate()` |
| `/api/v1/execute` | POST | ExecutionPanel | `useExecute()` |
| `/api/v1/history` | GET | HistoryTable | `useHistory()` |
| `/api/v1/history/stats` | GET | StatsCards | `useHistoryStats()` |
| `/api/v1/history/{id}` | GET | ExecutionDetails | `useExecutionDetails()` |
| `/api/v1/plans` | GET | PlanList | `usePlans()` |
| `/api/v1/plans/{id}` | GET | PlanViewer | `usePlan()` |
| `/ws/execute/{id}` | WS | LiveExecution | `useExecutionWebSocket()` |

---

## 🗂️ Índice - Referência Técnica (Legado)

As seções a seguir contêm a documentação técnica detalhada do sistema, útil para referência durante a implementação.

### Parte I — Arquitetura e Integração
1. [Visão Geral da Arquitetura de Integração](#1-visão-geral-da-arquitetura-de-integração)
2. [Pontos de Entrada Principais](#2-pontos-de-entrada-principais)
3. [Configurações e Toggles](#3-configurações-e-toggles)
4. [Fluxos de Ação do Usuário](#4-fluxos-de-ação-do-usuário)
5. [Dados para Visualização](#5-dados-para-visualização)
6. [Mapeamento CLI → UI](#6-mapeamento-cli--ui)
7. [APIs Internas Expostas](#7-apis-internas-expostas)
8. [Estados e Feedbacks](#8-estados-e-feedbacks)
9. [Recomendações para Implementação](#9-recomendações-para-implementação)

### Parte II — Segurança e Infraestrutura
10. [Segurança da API](#10-segurança-da-api)
11. [Job Engine e Background Tasks](#11-job-engine-e-background-tasks)
12. [Métricas e Observabilidade (OTEL)](#12-métricas-e-observabilidade-otel)

### Parte III — Editor e Execução
13. [Editor de Planos (Features Avançadas)](#13-editor-de-planos-features-avançadas)
14. [Execução Real-Time (WebSocket Avançado)](#14-execução-real-time-websocket-avançado)
15. [Histórico de Execução (Avançado)](#15-histórico-de-execução-avançado)
16. [Diff e Versionamento de Planos](#16-diff-e-versionamento-de-planos)

### Parte IV — Extensibilidade Futura
17. [Módulos Futuros (Placeholders)](#17-módulos-futuros-placeholders)
18. [Testabilidade da UI](#18-testabilidade-da-ui)

### Parte V — Referência
19. [Glossário Oficial](#19-glossário-oficial)
20. [Mapa de Estados Globais da UI](#20-mapa-de-estados-globais-da-ui)
21. [Casos de Erro Críticos e Recuperação](#21-casos-de-erro-críticos-e-recuperação)
22. [Exemplos UTDL para Implementação UI](#22-exemplos-utdl-para-implementação-ui)
23. [Checklist de Implementação UI](#23-checklist-de-implementação-ui)

---

## 1. Visão Geral da Arquitetura de Integração

### 1.1 Arquitetura Atual (CLI)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USUÁRIO                                         │
│                         (Terminal/PowerShell)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLI (Click + Rich)                                 │
│  aqa init | generate | validate | run | explain | history | demo | show     │
│  aqa plan | planversion (list | versions | diff | save | show | rollback)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BRAIN (Python Core)                                 │
│  Config │ Generator │ Validator │ Cache │ Storage │ LLM Providers           │
│  PlanVersionStore │ PlanCache │ ExecutionHistory                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RUNNER (Rust Binary)                                │
│                       Execução de alta performance                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Arquitetura Proposta (UI)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USUÁRIO                                         │
│                         (Interface Gráfica)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          UI LAYER (Web/Desktop)                              │
│  Dashboard │ Editor │ Visualizador │ Configurações │ Histórico              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      API LAYER (REST/WebSocket)                              │
│  Expõe funções do Brain como endpoints HTTP ou WebSocket                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BRAIN (Python Core)                                 │
│  [Sem alterações - mesmas classes e funções]                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pontos de Entrada Principais

### 2.1 Inicialização do Workspace

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Comando** | `aqa init [--force] [--swagger URL]` | Botão "Novo Projeto" ou Wizard |
| **Arquivo fonte** | `brain/src/cli/commands/init_cmd.py` | - |
| **Função core** | `init()` | Mesma função via API |
| **Parâmetros** | `directory`, `force`, `swagger`, `base_url` | Formulário com campos |
| **Output** | Cria `.aqa/config.yaml`, `.aqa/plans/`, `.aqa/reports/` | Feedback visual + navegação |

**Código de integração:**
```python
# brain/src/cli/commands/init_cmd.py
# Função a ser exposta via API:

def init_workspace(
    directory: str = ".",
    force: bool = False,
    swagger: str | None = None,
    base_url: str | None = None,
) -> dict:
    """
    Retorna: {"success": bool, "path": str, "files_created": list}
    """
```

**Componente UI sugerido:**
- Modal/Wizard com 3 passos:
  1. Selecionar diretório
  2. Importar OpenAPI (opcional)
  3. Confirmar configuração inicial

---

### 2.2 Geração de Planos de Teste

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Comando** | `aqa generate --swagger FILE --output FILE` | Área de input + botão "Gerar" |
| **Arquivo fonte** | `brain/src/cli/commands/generate_cmd.py` | - |
| **Função core** | `UTDLGenerator.generate()` | Mesma função via API |
| **Input 1** | `--swagger FILE` (OpenAPI) | Upload de arquivo ou URL |
| **Input 2** | `--requirement TEXT` | Text area livre |
| **Input 3** | `--interactive` | Formulário guiado |

**Código de integração:**
```python
# brain/src/generator/llm.py
class UTDLGenerator:
    def generate(
        self,
        requirements: str,
        base_url: str,
        max_steps: int | None = None,
    ) -> Plan:
        """
        Retorna: Plan (objeto Pydantic serializável para JSON)
        """
```

**Parâmetros expostos para UI:**

| Parâmetro | Tipo | UI Component | Default |
|-----------|------|--------------|---------|
| `swagger` | file/url | File picker + URL input | - |
| `requirement` | text | Textarea (multiline) | - |
| `base_url` | url | Input URL com validação | Config workspace |
| `model` | enum | Dropdown | `gpt-5.1` |
| `llm_mode` | enum | **Toggle: Mock/Real** | `real` |
| `include_negative` | bool | **Toggle/Checkbox** | `false` |
| `include_auth` | bool | **Toggle/Checkbox** | `false` |
| `include_refresh` | bool | **Toggle/Checkbox** | `false` |
| `auth_scheme` | enum | Dropdown (se auth=true) | primário |
| `max_steps` | int | Number input | ilimitado |

---

### 2.3 Validação de Planos

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Comando** | `aqa validate plan.json [--strict]` | Validação automática + indicadores |
| **Arquivo fonte** | `brain/src/cli/commands/validate_cmd.py` | - |
| **Função core** | `UTDLValidator.validate()` | Mesma função via API |

**Código de integração:**
```python
# brain/src/validator/utdl_validator.py
class UTDLValidator:
    def validate(self, data: dict) -> ValidationResult:
        """
        Retorna:
        ValidationResult {
            is_valid: bool
            errors: list[str]
            warnings: list[str]
            plan: Plan | None
        }
        """
```

**Componente UI sugerido:**
- Validação em tempo real no editor de planos
- Ícone de status: ✅ válido | ⚠️ warnings | ❌ erros
- Painel lateral com lista de issues clicáveis

---

### 2.4 Execução de Planos

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Comando** | `aqa run plan.json [--parallel] [--timeout N]` | Botão "Executar" + painel de progresso |
| **Arquivo fonte** | `brain/src/cli/commands/run_cmd.py` | - |
| **Função core** | `run_plan()` | Mesma função via API |

**Código de integração:**
```python
# brain/src/runner/execute.py
def run_plan(
    plan: Plan,
    runner_path: str | None = None,
    timeout_seconds: int = 300,
    parallel: bool = False,
    max_retries: int = 3,
) -> RunnerResult:
    """
    Retorna:
    RunnerResult {
        plan_id: str
        plan_name: str
        total_steps: int
        passed: int
        failed: int
        skipped: int
        total_duration_ms: float
        steps: list[StepResult]
        raw_report: dict
    }
    """
```

**Parâmetros expostos para UI:**

| Parâmetro | Tipo | UI Component | Default |
|-----------|------|--------------|---------|
| `parallel` | bool | **Toggle: Sequencial/Paralelo** | `false` |
| `timeout` | int | Slider ou input (segundos) | `300` |
| `max_steps` | int | Number input | ilimitado |
| `max_retries` | int | Number input | `3` |

**Eventos para WebSocket (execução em tempo real):**

| Evento | Payload | UI Action |
|--------|---------|-----------|
| `step_started` | `{step_id, description}` | Highlight step, spinner |
| `step_completed` | `{step_id, status, duration_ms}` | Update status icon |
| `step_failed` | `{step_id, error, assertions}` | Mostrar erro inline |
| `execution_complete` | `RunnerResult` | Mostrar resumo final |

---

### 2.5 Histórico de Execuções

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Comando** | `aqa history [--limit N] [--status X]` | Tabela/Timeline navegável |
| **Arquivo fonte** | `brain/src/cli/commands/history_cmd.py` | - |
| **Função core** | `ExecutionHistory.get_recent()` | Mesma função via API |

**Código de integração:**
```python
# brain/src/cache.py
class ExecutionHistory:
    def get_recent(self, limit: int = 10) -> list[ExecutionRecord]:
        """Lista últimas N execuções"""

    def get_by_status(self, status: str, limit: int = 10) -> list[ExecutionRecord]:
        """Filtra por status: success | failure | error"""

    def get_by_id(self, execution_id: str) -> ExecutionRecord | None:
        """Detalhes de uma execução específica"""

    def get_stats(self) -> dict:
        """Estatísticas agregadas"""
```

**Dados disponíveis para visualização:**

| Campo | Tipo | Uso na UI |
|-------|------|-----------|
| `id` | str | Link para detalhes |
| `timestamp` | ISO8601 | Data/hora formatada |
| `plan_file` | str | Nome do plano |
| `status` | enum | Badge colorido |
| `duration_ms` | int | Duração formatada |
| `total_steps` | int | Progresso |
| `passed_steps` | int | Barra verde |
| `failed_steps` | int | Barra vermelha |
| `runner_report` | dict | Expandir detalhes |

---

## 3. Configurações e Toggles

### 3.1 Toggle: Modo LLM (Mock/Real)

Este é o toggle mais importante para desenvolvimento e testes.

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Flag** | `--llm-mode mock` ou `--llm-mode real` | **Toggle Switch** |
| **Env var** | `AQA_LLM_MODE=mock` | Persistido em config |
| **Arquivo fonte** | `brain/src/llm/providers.py` | - |

**Código de integração:**
```python
# brain/src/llm/providers.py
def get_llm_provider(
    mode: str | None = None,  # "mock" | "real" | None (auto-detect)
) -> BaseLLMProvider:
    """
    Ordem de prioridade:
    1. Parâmetro `mode` (explícito)
    2. Variável AQA_LLM_MODE
    3. Auto-detect baseado em API keys
    """
```

**UI Component:**
```
┌─────────────────────────────────────────┐
│  LLM Mode                               │
│  ┌─────────┐ ┌─────────┐                │
│  │  Mock   │ │  Real   │  ← Toggle      │
│  └─────────┘ └─────────┘                │
│                                         │
│  ⚠️ Mock: Respostas simuladas (grátis)  │
│  💰 Real: Usa API (custo por chamada)   │
└─────────────────────────────────────────┘
```

**Estados visuais:**
- **Mock ativo**: Badge "MOCK" visível, cor diferente no header
- **Real ativo**: Indicador de consumo de API, badge do provider (OpenAI/Grok)

---

### 3.2 Toggle: Execução Paralela

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Flag** | `--parallel` | **Toggle Switch** |
| **Default** | `false` (sequencial) | - |
| **Arquivo fonte** | `brain/src/cli/commands/run_cmd.py` | - |

**UI Component:**
```
┌─────────────────────────────────────────┐
│  Modo de Execução                       │
│  ○ Sequencial (step-by-step)            │
│  ● Paralelo (máx. performance)          │
└─────────────────────────────────────────┘
```

---

### 3.3 Toggle: Cache de Planos

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Config** | `cache_enabled: true` em BrainConfig | **Toggle Switch** + Settings |
| **Env var** | `BRAIN_CACHE_ENABLED=true` | - |
| **Arquivo fonte** | `brain/src/cache.py` | - |

**Código de integração:**
```python
# brain/src/cache.py
class PlanCache:
    def get_stats(self) -> CacheStats:
        """
        Retorna:
        CacheStats {
            enabled: bool
            entries: int
            expired_entries: int
            cache_dir: str
            size_bytes: int
            compressed_entries: int
        }
        """

    def clear(self) -> int:
        """Limpa cache, retorna número de entries removidas"""
```

**UI Component:**
```
┌─────────────────────────────────────────┐
│  Cache de Planos           [ON/OFF]     │
│  ─────────────────────────────────────  │
│  📁 Localização: ~/.aqa/cache           │
│  📊 Entries: 42 (3.2 MB)                │
│  ⏰ TTL: 30 dias                        │
│                                         │
│  [Limpar Cache]  [Ver Entries]          │
└─────────────────────────────────────────┘
```

---

### 3.4 Toggle: Histórico de Execuções

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Config** | `history_enabled: true` | **Toggle Switch** |
| **Env var** | `BRAIN_HISTORY_ENABLED=true` | - |

---

### 3.5 Toggle: Validação Estrita

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Flag** | `--strict` | **Toggle Switch** |
| **Efeito** | Warnings viram erros | - |

---

### 3.6 Toggle: Normalização Automática

| Aspecto | CLI Atual | UI Proposta |
|---------|-----------|-------------|
| **Flag** | `--normalize` | **Toggle (sempre on por padrão na UI)** |
| **Efeito** | Converte `tests→steps`, `status→status_code` | - |
| **Arquivo fonte** | `brain/src/adapter/format_adapter.py` | - |

---

### 3.7 Configurações do LLM (Painel de Settings)

**Código de integração:**
```python
# brain/src/config.py
class BrainConfig(BaseModel):
    # Campos editáveis via UI
    model: str = "gpt-5.1"
    llm_provider: str = "openai"
    llm_fallback_enabled: bool = True
    temperature: float = 0.2  # 0.0 - 2.0
    max_llm_retries: int = 3  # 1 - 10
```

**UI Component - Painel de Configurações LLM:**
```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️ Configurações do LLM                                    │
│  ───────────────────────────────────────────────────────── │
│                                                             │
│  Provedor Primário    [OpenAI ▼]                           │
│  Modelo              [gpt-5.1 ▼]                           │
│                                                             │
│  Fallback Automático  [ON]                                  │
│  └─ Provedor fallback: xAI (Grok)                          │
│                                                             │
│  Temperatura          [────●────] 0.2                       │
│  └─ 0.0 = Determinístico  2.0 = Criativo                   │
│                                                             │
│  Max Retries (correção) [3]                                 │
│                                                             │
│  API Keys:                                                  │
│  ├─ OPENAI_API_KEY    [••••••••] ✅ Configurada            │
│  └─ XAI_API_KEY       [        ] ⚠️ Não configurada        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.8 Configurações de Execução (Painel de Settings)

```python
# brain/src/config.py
class BrainConfig(BaseModel):
    timeout_seconds: int = 300
    max_steps: int | None = None
    max_retries: int = 3
```

**UI Component:**
```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️ Configurações de Execução                               │
│  ───────────────────────────────────────────────────────── │
│                                                             │
│  Timeout Global       [──────●────────] 300s               │
│  Max Steps           [     ] (vazio = ilimitado)           │
│  Retries por Step    [3]                                    │
│                                                             │
│  Modo Execução:                                             │
│  ○ Sequencial (mais seguro)                                │
│  ● Paralelo (mais rápido)                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Fluxos de Ação do Usuário

### 4.1 Fluxo: Primeiro Uso (Onboarding)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Welcome    │ ──▶ │ Criar        │ ──▶ │ Importar     │ ──▶ │ Configurar   │
│   Screen     │     │ Workspace    │     │ OpenAPI      │     │ API Keys     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                       │
                                                                       ▼
                     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
                     │   Pronto!    │ ◀── │ Gerar Demo   │ ◀── │ Testar       │
                     │   Dashboard  │     │ Plan         │     │ Conexão      │
                     └──────────────┘     └──────────────┘     └──────────────┘
```

**Funções chamadas:**
1. `init_workspace()` - Cria estrutura `.aqa/`
2. `parse_openapi()` - Valida e parseia spec
3. `get_llm_provider().is_available()` - Verifica API keys
4. Demo plan (mock mode) - Mostra funcionamento

---

### 4.2 Fluxo: Gerar e Executar Teste

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Upload      │ ──▶ │  Preview     │ ──▶ │  Configurar  │ ──▶ │  Gerar       │
│  OpenAPI     │     │  Endpoints   │     │  Opções      │     │  Plano       │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                       │
                                                                       ▼
                     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
                     │   Salvar     │ ◀── │  Ver         │ ◀── │  Validar     │
                     │   Plano      │     │  Resultado   │     │  Plano       │
                     └──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
                     │  Executar    │ ──▶ │  Progresso   │ ──▶ │  Relatório   │
                     │  Plano       │     │  Real-time   │     │  Final       │
                     └──────────────┘     └──────────────┘     └──────────────┘
```

**Funções chamadas por etapa:**

| Etapa | Função | Arquivo |
|-------|--------|---------|
| Upload OpenAPI | `parse_openapi(file_or_url)` | `ingestion/swagger.py` |
| Preview Endpoints | `spec_to_requirement_text(spec)` | `ingestion/swagger.py` |
| Detectar Auth | `detect_security(spec)` | `ingestion/security.py` |
| Gerar Plano | `UTDLGenerator.generate()` | `generator/llm.py` |
| Validar Plano | `UTDLValidator.validate()` | `validator/utdl_validator.py` |
| Executar | `run_plan(plan)` | `runner/execute.py` |
| Salvar Histórico | `ExecutionHistory.add()` | `cache.py` |

---

### 4.3 Fluxo: Editar Plano Existente

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Selecionar  │ ──▶ │  Editor      │ ──▶ │  Validação   │ ──▶ │  Salvar      │
│  Plano       │     │  Visual      │     │  Real-time   │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

**Componentes do Editor Visual:**

| Área | Funcionalidade |
|------|----------------|
| **Tree View** | Lista de steps com drag-and-drop para reordenar |
| **Step Editor** | Formulário para editar params, assertions, extract |
| **JSON View** | Editor raw com syntax highlighting |
| **Validation Panel** | Erros/warnings em tempo real |
| **Preview** | Visualização do fluxo (DAG) |

---

## 5. Dados para Visualização

### 5.1 Dashboard Principal

**Dados disponíveis:**

```python
# Fonte: ExecutionHistory.get_stats()
{
    "total_executions": 156,
    "success_rate": 87.5,  # percentual
    "avg_duration_ms": 4523,
    "last_execution": "2024-12-05T14:30:00Z",
    "by_status": {
        "success": 137,
        "failure": 15,
        "error": 4
    },
    "trends": {
        "last_7_days": [12, 15, 8, 22, 18, 14, 20],
        "success_rate_trend": [85, 88, 82, 90, 87, 89, 87]
    }
}
```

**Widgets sugeridos:**
- Card: Total de execuções
- Card: Taxa de sucesso (com gráfico sparkline)
- Card: Última execução (tempo relativo)
- Gráfico de linha: Execuções por dia
- Gráfico de pizza: Distribuição por status

---

### 5.2 Visualização de Plano (DAG)

**Dados disponíveis:**
```python
# Fonte: Plan.steps com depends_on
{
    "nodes": [
        {"id": "step_1", "label": "Health Check", "type": "http_request"},
        {"id": "step_2", "label": "Login", "type": "http_request"},
        {"id": "step_3", "label": "Get User", "type": "http_request"},
    ],
    "edges": [
        {"from": "step_1", "to": "step_2"},
        {"from": "step_2", "to": "step_3"},
    ]
}
```

**Biblioteca sugerida:** vis.js, react-flow, mermaid

---

### 5.3 Visualização de Execução em Tempo Real

**Eventos WebSocket:**
```json
// step_started
{"event": "step_started", "step_id": "login", "timestamp": "2024-12-05T14:30:00Z"}

// step_progress (para steps longos)
{"event": "step_progress", "step_id": "login", "message": "Aguardando resposta..."}

// step_completed
{
    "event": "step_completed",
    "step_id": "login",
    "status": "passed",
    "duration_ms": 245,
    "extractions": {"token": "eyJ..."}
}

// step_failed
{
    "event": "step_failed",
    "step_id": "get_user",
    "status": "failed",
    "error": "Assertion failed: status_code expected 200, got 401",
    "duration_ms": 120
}

// execution_complete
{
    "event": "execution_complete",
    "summary": {
        "total": 5,
        "passed": 4,
        "failed": 1,
        "skipped": 0,
        "duration_ms": 1523
    }
}
```

---

### 5.4 Relatório de Execução

**Dados disponíveis (RunnerResult):**
```python
{
    "plan_id": "abc-123",
    "plan_name": "Login Flow Test",
    "total_steps": 5,
    "passed": 4,
    "failed": 1,
    "skipped": 0,
    "total_duration_ms": 1523,
    "steps": [
        {
            "step_id": "health_check",
            "status": "passed",
            "duration_ms": 120,
            "error": None
        },
        {
            "step_id": "login",
            "status": "passed",
            "duration_ms": 450,
            "error": None,
            "extractions": {"token": "eyJ..."}
        },
        {
            "step_id": "get_user",
            "status": "failed",
            "duration_ms": 230,
            "error": "Assertion failed: status_code expected 200, got 401",
            "request": {"method": "GET", "url": "https://..."},
            "response": {"status": 401, "body": {...}}
        }
    ]
}
```

---

## 6. Mapeamento CLI → UI

### 6.1 Tabela Completa de Comandos

| Comando CLI | UI Equivalente | Componente | Prioridade |
|-------------|---------------|------------|------------|
| `aqa init` | Botão "Novo Projeto" + Wizard | Modal | P0 |
| `aqa generate --swagger` | Upload + "Gerar Testes" | Form + Button | P0 |
| `aqa generate --requirement` | Textarea + "Gerar" | Form + Button | P0 |
| `aqa generate -i` (interativo) | Wizard step-by-step | Multi-step Form | P1 |
| `aqa validate` | Automático no editor | Real-time validation | P0 |
| `aqa run` | Botão "Executar" | Button + Progress | P0 |
| `aqa run --parallel` | Toggle "Modo Paralelo" | Switch | P1 |
| `aqa explain` | Painel "Explicação" | Sidebar | P2 |
| `aqa history` | Aba "Histórico" | Table/Timeline | P1 |
| `aqa history stats` | Dashboard widgets | Cards + Charts | P1 |
| `aqa demo` | "Executar Demo" | Button | P2 |
| `aqa show` | Visualizador de plano | Tree + DAG | P1 |
| `aqa show --diff` | Comparador lado-a-lado | Split view | P3 |

---

### 6.2 Tabela de Flags → Toggles/Inputs

| Flag CLI | Tipo | UI Component | Localização |
|----------|------|--------------|-------------|
| `--llm-mode mock/real` | enum | **Toggle Switch** | Header/Toolbar |
| `--swagger FILE` | file | File Picker | Generate Form |
| `--requirement TEXT` | text | Textarea | Generate Form |
| `--base-url URL` | url | Input URL | Generate Form |
| `--model MODEL` | enum | Dropdown | Settings ou Form |
| `--output FILE` | file | Save Dialog | Generate Form |
| `--include-negative` | bool | Checkbox | Generate Options |
| `--include-auth` | bool | Checkbox | Generate Options |
| `--auth-scheme NAME` | enum | Dropdown | Generate Options |
| `--include-refresh` | bool | Checkbox | Generate Options |
| `--max-steps N` | int | Number Input | Generate/Run Options |
| `--parallel` | bool | Toggle | Run Options |
| `--timeout N` | int | Slider/Input | Run Options |
| `--max-retries N` | int | Number Input | Run Options |
| `--strict` | bool | Toggle | Validate Options |
| `--normalize` | bool | Toggle (default on) | Hidden/Advanced |
| `--verbose` | bool | Toggle | Settings |
| `--quiet` | bool | Toggle | Settings |
| `--json` | bool | N/A (sempre JSON na API) | N/A |

---

## 7. APIs Internas Expostas

### 7.1 Proposta de Endpoints REST

> **Importante**: Todos os endpoints usam versionamento `/api/v1/` para garantir compatibilidade futura.

```yaml
# Workspace
POST   /api/v1/workspace/init
GET    /api/v1/workspace/config
PUT    /api/v1/workspace/config

# Plans
POST   /api/v1/plans/generate          # Gera plano (async, retorna job_id)
POST   /api/v1/plans/validate          # Valida plano
GET    /api/v1/plans                   # Lista planos salvos
GET    /api/v1/plans/{id}              # Detalhes de um plano
PUT    /api/v1/plans/{id}              # Atualiza plano
DELETE /api/v1/plans/{id}              # Remove plano
GET    /api/v1/plans/{id}/explain      # Explicação do plano
GET    /api/v1/plans/{id}/diff/{other_id}  # Diff entre dois planos
POST   /api/v1/plans/{id}/snapshot     # Cria snapshot manual
GET    /api/v1/plans/{id}/snapshots    # Lista snapshots

# Execution
POST   /api/v1/execute                 # Executa plano (async, retorna job_id)
GET    /api/v1/execute/{job_id}        # Status da execução
GET    /api/v1/execute/{job_id}/logs   # Logs estruturados da execução
DELETE /api/v1/execute/{job_id}        # Cancela execução

# History
GET    /api/v1/history                 # Lista execuções (com filtros)
GET    /api/v1/history/{id}            # Detalhes de execução
GET    /api/v1/history/{id}/export     # Exporta relatório (json/html/md)
GET    /api/v1/history/stats           # Estatísticas

# LLM
GET    /api/v1/llm/status              # Status dos providers
PUT    /api/v1/llm/mode                # Alterna mock/real

# Cache
GET    /api/v1/cache/stats             # Estatísticas do cache
DELETE /api/v1/cache                   # Limpa cache

# OpenAPI
POST   /api/v1/openapi/parse           # Parseia spec
POST   /api/v1/openapi/security        # Detecta segurança

# Jobs (gerenciamento de background tasks)
GET    /api/v1/jobs                    # Lista jobs ativos
GET    /api/v1/jobs/{job_id}           # Status de um job
DELETE /api/v1/jobs/{job_id}           # Cancela job

# Data Generation (futuro)
POST   /api/v1/data/generate           # Gera massa de dados
POST   /api/v1/data/sql                # Gera dados SQL
```

---

### 7.2 Proposta de WebSocket Events

```yaml
# Execução em tempo real
ws://localhost:8080/ws/v1/execute/{job_id}

# Eventos recebidos:
- step_started: {step_id, description, timestamp}
- step_progress: {step_id, message, timestamp}
- step_completed: {step_id, status, duration_ms, extractions, trace_id}
- step_failed: {step_id, error, request, response, trace_id}
- execution_complete: {summary, trace_id}
- execution_error: {error, code}
- heartbeat: {timestamp, job_id}  # A cada 5s durante execução

# Reconexão
# Se o cliente perder conexão e reconectar:
# - Enviar header X-Last-Event-Id
# - API reenvia eventos perdidos desde esse ID
```

---

### 7.3 Classes Python a Expor

| Classe | Métodos Principais | Uso na UI |
|--------|-------------------|-----------|
| `BrainConfig` | `from_env()`, `for_testing()` | Settings panel |
| `UTDLGenerator` | `generate()` | Generate button |
| `UTDLValidator` | `validate()` | Real-time validation |
| `PlanCache` | `get()`, `store()`, `clear()`, `get_stats()` | Cache management |
| `ExecutionHistory` | `get_recent()`, `get_stats()`, `get_by_id()` | History panel |
| `SmartFormatAdapter` | `normalize()`, `load_and_normalize()` | Import plans |
| `parse_openapi()` | - | Upload OpenAPI |
| `detect_security()` | - | Auth detection |
| `run_plan()` | - | Execute button |
| `get_llm_provider()` | - | Mode toggle |

---

## 8. Estados e Feedbacks

### 8.1 Estados de Loading

| Operação | Duração Típica | Feedback |
|----------|---------------|----------|
| Parse OpenAPI | 100-500ms | Spinner + "Analisando spec..." |
| Generate Plan (mock) | 50-100ms | Spinner |
| Generate Plan (real) | 3-15s | Progress bar + "Gerando com {model}..." |
| Validate Plan | 10-50ms | Inline (tempo real) |
| Execute Plan | 1-60s | Step-by-step progress |

---

### 8.2 Estados de Erro

| Código | Mensagem | Ação Sugerida |
|--------|----------|---------------|
| `NO_API_KEY` | API key não configurada | Link para Settings |
| `INVALID_OPENAPI` | Spec OpenAPI inválida | Mostrar erros de validação |
| `LLM_TIMEOUT` | Timeout na geração | Retry ou usar Mock |
| `RUNNER_NOT_FOUND` | Runner não compilado | Instruções de build |
| `VALIDATION_FAILED` | Plano inválido | Lista de erros clicáveis |
| `EXECUTION_TIMEOUT` | Timeout de execução | Sugerir aumentar timeout |

---

### 8.3 Notificações

| Tipo | Exemplo | Duração |
|------|---------|---------|
| Success | "Plano gerado com sucesso!" | 3s auto-dismiss |
| Warning | "Usando modo Mock (grátis)" | Persistente |
| Error | "Falha na execução: 3 steps falharam" | Persistente até dismiss |
| Info | "Cache utilizado - 0 chamadas LLM" | 5s auto-dismiss |

---

## 9. Recomendações para Implementação

### 9.1 Arquitetura Sugerida

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                        │
│  React/Vue/Svelte + TailwindCSS                                             │
│  - Dashboard                                                                 │
│  - Plan Editor (Monaco Editor for JSON)                                     │
│  - Execution Viewer (Real-time updates via WebSocket)                       │
│  - History Table                                                            │
│  - Settings Panel                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                       │
│  FastAPI + WebSocket support                                                 │
│  - REST endpoints para CRUD                                                  │
│  - WebSocket para execução real-time                                        │
│  - Background tasks para geração                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Direct import
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Brain Core (existente)                             │
│  Nenhuma alteração necessária - apenas importar classes                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 9.2 Priorização de Features (MVP UI)

| Prioridade | Feature | Justificativa |
|------------|---------|---------------|
| **P0** | Toggle Mock/Real | Essencial para onboarding |
| **P0** | Upload OpenAPI + Generate | Core flow |
| **P0** | Executar Plano | Core flow |
| **P0** | Ver Resultado | Core flow |
| **P1** | Editor de Plano Visual | Produtividade |
| **P1** | Histórico de Execuções | Auditoria |
| **P1** | Settings Panel | Customização |
| **P2** | Dashboard com métricas | Insights |
| **P2** | DAG Visualization | Entendimento |
| **P3** | Diff entre planos | Advanced |
| **P3** | Comparação de execuções | Advanced |

---

### 9.3 Variáveis de Ambiente para UI

```bash
# Configuração da API Layer
AQA_API_HOST=0.0.0.0
AQA_API_PORT=8080
AQA_API_CORS_ORIGINS=http://localhost:3000

# Configuração do Frontend
AQA_UI_API_URL=http://localhost:8080
AQA_UI_WS_URL=ws://localhost:8080

# Persistidas do Brain (usadas pela API)
AQA_LLM_MODE=real
OPENAI_API_KEY=sk-...
XAI_API_KEY=xai-...
```

---

### 9.4 Estrutura de Diretórios (Implementada)

```
autonomous-quality-agent/
├── brain/
│   ├── src/
│   │   ├── api/                  # ✅ IMPLEMENTADO - API Layer
│   │   │   ├── __init__.py       # Exports: create_app, APIConfig
│   │   │   ├── app.py            # FastAPI app factory
│   │   │   ├── config.py         # APIConfig dataclass
│   │   │   ├── deps.py           # Dependency injection
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── health.py     # GET /health
│   │   │   │   ├── generate.py   # POST /api/v1/generate
│   │   │   │   ├── validate.py   # POST /api/v1/validate
│   │   │   │   ├── execute.py    # POST /api/v1/execute
│   │   │   │   ├── history.py    # GET /api/v1/history
│   │   │   │   └── workspace.py  # POST /api/v1/workspace/*
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── common.py     # ErrorDetail, SuccessResponse
│   │   │   │   ├── generate.py   # GenerateRequest/Response
│   │   │   │   ├── validate.py   # ValidateRequest/Response
│   │   │   │   ├── execute.py    # ExecuteRequest/Response
│   │   │   │   ├── history.py    # HistoryRecordSchema
│   │   │   │   └── workspace.py  # WorkspaceInitRequest
│   │   │   └── websocket/
│   │   │       ├── __init__.py
│   │   │       └── execute_stream.py  # WS /ws/execute
│   │   └── cli/
│   │       └── commands/
│   │           └── serve_cmd.py  # ✅ CLI: aqa serve
│   └── tests/
│       └── test_api.py           # ✅ Testes da API
├── runner/                       # Existente - Rust binary
├── ui/                           # FUTURO - Frontend
│   ├── package.json
│   └── src/
└── docs/
    └── interface.md              # Este documento
```

---

### 9.5 API REST Implementada

A API REST foi implementada em `brain/src/api/` usando FastAPI. Esta seção documenta todos os endpoints disponíveis.

#### Iniciar o Servidor

```bash
# Via CLI (recomendado)
aqa serve --host 0.0.0.0 --port 8080

# Via módulo Python
python -m uvicorn src.api:create_app --factory --host 0.0.0.0 --port 8080 --reload
```

#### Base URLs

| Ambiente | URL Base | Documentação |
|----------|----------|--------------|
| Local | `http://localhost:8080` | `http://localhost:8080/docs` |
| Docker | `http://aqa-api:8080` | `http://aqa-api:8080/docs` |

---

#### Endpoint: GET /health

Verifica o status de saúde da API e seus componentes.

**Request:**
```http
GET /health HTTP/1.1
Host: localhost:8080
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-12-06T10:30:00Z",
  "components": {
    "brain": "ok",
    "runner": "ok",
    "storage": "ok"
  }
}
```

---

#### Endpoint: POST /api/v1/generate

Gera um plano de teste UTDL a partir de um requisito ou especificação OpenAPI.

**Request:**
```http
POST /api/v1/generate HTTP/1.1
Host: localhost:8080
Content-Type: application/json

{
  "requirement": "Testar endpoint de login com credenciais válidas e inválidas",
  "swagger_url": "https://api.example.com/openapi.json",
  "swagger_content": null,
  "base_url": "https://api.example.com",
  "options": {
    "include_negative": true,
    "include_auth": true,
    "max_steps": 10
  }
}
```

**Parâmetros:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `requirement` | string | ❌ | Requisito em texto livre |
| `swagger_url` | string | ❌ | URL da especificação OpenAPI |
| `swagger_content` | object | ❌ | Conteúdo OpenAPI inline |
| `base_url` | string | ❌ | URL base da API alvo |
| `options.include_negative` | bool | ❌ | Incluir casos negativos |
| `options.include_auth` | bool | ❌ | Incluir testes de autenticação |
| `options.max_steps` | int | ❌ | Limite de steps no plano |

> **Nota:** Pelo menos um de `requirement`, `swagger_url` ou `swagger_content` deve ser fornecido.

**Response (200 OK):**
```json
{
  "success": true,
  "plan": {
    "spec_version": "0.1",
    "meta": {
      "name": "Login Tests",
      "id": "plan-abc123",
      "description": "Testes de autenticação"
    },
    "config": {
      "base_url": "https://api.example.com"
    },
    "steps": [...]
  },
  "stats": {
    "generation_time_ms": 3500,
    "model_used": "gpt-4o",
    "tokens_used": 1250
  }
}
```

**Erros:**

| Código | Descrição |
|--------|-----------|
| 400 (E6002) | Nenhuma fonte de entrada fornecida |
| 500 (E6101) | Erro na geração do plano |

---

#### Endpoint: POST /api/v1/validate

Valida um plano UTDL e retorna erros/warnings.

**Request:**
```http
POST /api/v1/validate HTTP/1.1
Host: localhost:8080
Content-Type: application/json

{
  "plan": {
    "spec_version": "0.1",
    "meta": {"name": "Test Plan", "id": "test-001"},
    "config": {"base_url": "https://api.example.com"},
    "steps": []
  },
  "mode": "strict"
}
```

**Parâmetros:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `plan` | object | ✅ | Plano UTDL a validar |
| `mode` | string | ❌ | Modo de validação: `default`, `strict` |

**Response (200 OK):**
```json
{
  "success": true,
  "is_valid": true,
  "error_count": 0,
  "warning_count": 1,
  "errors": [],
  "warnings": ["Plano sem steps"]
}
```

---

#### Endpoint: POST /api/v1/execute

Executa um plano de teste.

**Request:**
```http
POST /api/v1/execute HTTP/1.1
Host: localhost:8080
Content-Type: application/json

{
  "plan": {
    "spec_version": "0.1",
    "meta": {"name": "Test", "id": "test-001"},
    "config": {"base_url": "https://httpbin.org"},
    "steps": [
      {
        "id": "get_ip",
        "action": "http_request",
        "params": {"method": "GET", "path": "/ip"},
        "assertions": [{"type": "status_code", "operator": "eq", "value": 200}]
      }
    ]
  },
  "dry_run": false,
  "context": {
    "auth_token": "Bearer xxx"
  }
}
```

**Parâmetros:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `plan` | object | ❌* | Plano UTDL inline |
| `plan_file` | string | ❌* | Caminho para arquivo de plano |
| `requirement` | string | ❌* | Requisito para gerar e executar |
| `swagger` | string | ❌* | OpenAPI para gerar e executar |
| `dry_run` | bool | ❌ | Apenas validar, não executar |
| `context` | object | ❌ | Variáveis de contexto |

> **Nota:** *Pelo menos uma fonte de plano deve ser fornecida.

**Response (200 OK):**
```json
{
  "success": true,
  "execution_id": "exec-xyz789",
  "summary": {
    "total_steps": 5,
    "passed": 4,
    "failed": 1,
    "skipped": 0,
    "duration_ms": 1250
  },
  "steps": [
    {
      "id": "get_ip",
      "status": "passed",
      "duration_ms": 150,
      "response": {"status_code": 200}
    }
  ]
}
```

**Erros:**

| Código | Descrição |
|--------|-----------|
| 400 (E6002) | Nenhuma fonte de plano fornecida |
| 400 (E6004) | Plano inválido |

---

#### Endpoint: GET /api/v1/history

Lista o histórico de execuções.

**Request:**
```http
GET /api/v1/history?limit=20&plan_id=test-001 HTTP/1.1
Host: localhost:8080
```

**Query Parameters:**

| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `limit` | int | 20 | Quantidade de registros |
| `plan_id` | string | - | Filtrar por plano |

**Response (200 OK):**
```json
{
  "success": true,
  "total": 42,
  "records": [
    {
      "execution_id": "exec-xyz789",
      "plan_id": "test-001",
      "plan_name": "Login Tests",
      "timestamp": "2024-12-06T10:30:00Z",
      "summary": {
        "total_steps": 5,
        "passed": 5,
        "failed": 0
      }
    }
  ]
}
```

---

#### Endpoint: GET /api/v1/history/{execution_id}

Obtém detalhes de uma execução específica.

**Request:**
```http
GET /api/v1/history/exec-xyz789 HTTP/1.1
Host: localhost:8080
```

**Response (200 OK):**
```json
{
  "success": true,
  "record": {
    "execution_id": "exec-xyz789",
    "plan_id": "test-001",
    "plan_name": "Login Tests",
    "timestamp": "2024-12-06T10:30:00Z",
    "duration_ms": 1250,
    "summary": {...},
    "steps": [...]
  }
}
```

---

#### Endpoint: GET /api/v1/history/stats

Obtém estatísticas agregadas do histórico.

**Request:**
```http
GET /api/v1/history/stats HTTP/1.1
Host: localhost:8080
```

**Response (200 OK):**
```json
{
  "success": true,
  "stats": {
    "total_executions": 42,
    "total_steps_run": 210,
    "pass_rate": 0.95,
    "avg_duration_ms": 1100
  }
}
```

---

#### Endpoint: POST /api/v1/workspace/init

Inicializa um novo workspace AQA.

**Request:**
```http
POST /api/v1/workspace/init HTTP/1.1
Host: localhost:8080
Content-Type: application/json

{
  "directory": "/path/to/project",
  "force": false,
  "swagger_url": "https://api.example.com/openapi.json"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "workspace_path": "/path/to/project/.aqa",
  "files_created": [
    ".aqa/config.yaml",
    ".aqa/plans/",
    ".aqa/reports/"
  ]
}
```

---

#### Endpoint: GET /api/v1/workspace/status

Obtém status do workspace atual.

**Request:**
```http
GET /api/v1/workspace/status HTTP/1.1
Host: localhost:8080
```

**Response (200 OK):**
```json
{
  "success": true,
  "initialized": true,
  "path": "/path/to/project/.aqa",
  "config": {
    "base_url": "https://api.example.com",
    "llm_mode": "real"
  }
}
```

---

#### Endpoint: GET /api/v1/plans

Lista todos os planos versionados.

**Request:**
```http
GET /api/v1/plans HTTP/1.1
Host: localhost:8080
```

**Response (200 OK):**
```json
{
  "success": true,
  "plans": [
    {
      "name": "my-api-tests",
      "current_version": 3,
      "total_versions": 3,
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

---

#### Endpoint: GET /api/v1/plans/{plan_name}

Obtém a versão atual de um plano.

**Request:**
```http
GET /api/v1/plans/my-api-tests HTTP/1.1
Host: localhost:8080
```

**Query Parameters:**
- `version` (opcional): Número da versão específica

**Response (200 OK):**
```json
{
  "success": true,
  "plan_name": "my-api-tests",
  "version": 3,
  "created_at": "2024-01-15T10:30:00Z",
  "source": "llm",
  "description": "Added auth steps",
  "plan": {...}
}
```

---

#### Endpoint: GET /api/v1/plans/{plan_name}/versions

Lista todas as versões de um plano.

**Request:**
```http
GET /api/v1/plans/my-api-tests/versions HTTP/1.1
Host: localhost:8080
```

**Response (200 OK):**
```json
{
  "success": true,
  "plan_name": "my-api-tests",
  "versions": [
    {
      "version": 1,
      "created_at": "2024-01-10T08:00:00Z",
      "source": "llm",
      "description": "Initial version",
      "llm_provider": "openai",
      "llm_model": "gpt-4"
    },
    {
      "version": 2,
      "created_at": "2024-01-12T14:00:00Z",
      "source": "manual",
      "description": "Fixed assertions"
    }
  ],
  "total": 2
}
```

---

#### Endpoint: GET /api/v1/plans/{plan_name}/diff

Compara duas versões de um plano.

**Request:**
```http
GET /api/v1/plans/my-api-tests/diff?version_a=1&version_b=2 HTTP/1.1
Host: localhost:8080
```

**Query Parameters:**
- `version_a` (obrigatório): Versão base
- `version_b` (opcional): Versão a comparar (default: atual)

**Response (200 OK):**
```json
{
  "success": true,
  "plan_name": "my-api-tests",
  "version_a": 1,
  "version_b": 2,
  "has_changes": true,
  "summary": "+1 steps, ~2 modified",
  "steps_added": ["step-auth"],
  "steps_removed": [],
  "steps_modified": [
    {
      "id": "step-1",
      "field": "step",
      "before": {"url": "/old"},
      "after": {"url": "/new"}
    }
  ],
  "config_changes": [],
  "meta_changes": []
}
```

---

#### Endpoint: POST /api/v1/plans/{plan_name}/versions/{version}/restore

Restaura uma versão anterior, criando nova versão.

**Request:**
```http
POST /api/v1/plans/my-api-tests/versions/1/restore HTTP/1.1
Host: localhost:8080
Content-Type: application/json

{
  "description": "Rollback to v1 after regression"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "plan_name": "my-api-tests",
  "restored_from": 1,
  "new_version": 4,
  "created_at": "2024-01-16T09:00:00Z"
}
```

---

#### WebSocket: /ws/execute

Executa plano com streaming de resultados em tempo real.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8080/ws/execute');

ws.onopen = () => {
  ws.send(JSON.stringify({
    plan: {...},
    context: {}
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: 'step_start', 'step_complete', 'execution_complete', 'error'
};
```

**Mensagens Recebidas:**

| type | Descrição | Payload |
|------|-----------|---------|
| `step_start` | Início de step | `{step_id, step_index}` |
| `step_complete` | Step finalizado | `{step_id, status, duration_ms, response}` |
| `execution_complete` | Execução finalizada | `{summary, total_duration_ms}` |
| `error` | Erro na execução | `{code, message}` |

**Exemplo de Mensagem:**
```json
{
  "type": "step_complete",
  "step_id": "get_ip",
  "step_index": 0,
  "status": "passed",
  "duration_ms": 150,
  "response": {
    "status_code": 200,
    "body": {"origin": "1.2.3.4"}
  }
}
```

---

### 9.6 Códigos de Erro da API

| Código | HTTP | Descrição |
|--------|------|-----------|
| E6001 | 400 | Request body inválido |
| E6002 | 400 | Parâmetro obrigatório ausente |
| E6003 | 404 | Recurso não encontrado |
| E6004 | 400 | Validação do plano falhou |
| E6101 | 500 | Erro na geração LLM |
| E6102 | 500 | Erro na execução do runner |
| E6103 | 500 | Erro de storage/persistência |

---

### 9.7 Roadmap da API REST

Esta seção documenta o status de implementação e itens planejados para versões futuras.

#### Status Atual (v0.5.0)

| Fase | Funcionalidade | Status |
|------|----------------|--------|
| **Fase 1 (MVP)** | Health check | ✅ Implementado |
| | Generate plan | ✅ Implementado |
| | Validate plan | ✅ Implementado |
| | Execute plan | ✅ Implementado |
| | History list | ✅ Implementado |
| | Workspace init | ✅ Implementado |
| **Fase 2** | WebSocket streaming | ✅ Implementado |
| | History details | ✅ Implementado |
| | History stats | ✅ Implementado |
| | Workspace status | ✅ Implementado |
| **Fase 3** | Plan Versioning API | ✅ Implementado (v0.5.1) |
| | Plans CRUD | ✅ Implementado (v0.5.1) |

#### Planejado para v1.0.0

| Funcionalidade | Endpoint/Recurso | Descrição | Prioridade |
|----------------|------------------|-----------|------------|
| **Autenticação API Key** | Header `X-API-Key` | Proteção de endpoints com chave | P0 |
| **Autenticação JWT** | Header `Authorization: Bearer` | Para SaaS/multi-tenant | P1 |
| **Rate Limiting** | Middleware | Limite de requisições por IP/Key | P0 |
| **Upload OpenAPI** | `POST /api/v1/openapi/upload` | Upload multipart de arquivo | P2 |

#### Endpoints de Plan Versioning (Implementado v0.5.1)

| Endpoint | Descrição |
|----------|-----------|
| `GET /api/v1/plans` | Lista todos os planos versionados |
| `GET /api/v1/plans/{name}` | Obtém versão atual de um plano |
| `GET /api/v1/plans/{name}/versions` | Lista versões de um plano |
| `GET /api/v1/plans/{name}/versions/{v}` | Obtém versão específica |
| `GET /api/v1/plans/{name}/diff` | Compara versões |
| `POST /api/v1/plans/{name}/versions/{v}/restore` | Restaura versão anterior |

#### Planejado para v2.0.0+

| Funcionalidade | Descrição |
|----------------|-----------|
| Mobile Testing | Endpoints para emulador Android |
| Web UI Testing | Endpoints para Playwright/Puppeteer |
| Data Generation | Geração de dados de teste via Faker |
| Multi-user | Autenticação com múltiplos usuários |
| Métricas OTEL | Telemetria e observabilidade |

---

## PARTE II — Segurança e Infraestrutura

---

### 10. Segurança da API

#### 10.1 Modos de Autenticação

A API suporta três modos de autenticação, configuráveis via variável de ambiente `AQA_AUTH_MODE`:

| Modo | Uso | Configuração |
|------|-----|--------------|
| **NoAuth** | Desenvolvimento local, desktop app | `AQA_AUTH_MODE=none` |
| **API Key** | CLI, integrações, desktop | `AQA_AUTH_MODE=apikey` |
| **JWT** | SaaS, multi-tenant, cloud | `AQA_AUTH_MODE=jwt` |

##### 10.1.1 Modo NoAuth (Padrão Local)

```python
# Sem autenticação - apenas para localhost
AQA_AUTH_MODE=none
AQA_API_ALLOWED_HOSTS=127.0.0.1,localhost
```

##### 10.1.2 Modo API Key

```python
# Header obrigatório em todas as requests
X-AQA-API-Key: aqa_sk_xxxxxxxxxxxxx

# Geração de API Keys
POST /api/v1/auth/keys
{
    "name": "CLI Integration",
    "expires_in_days": 365,
    "scopes": ["plans:read", "plans:write", "execute"]
}

# Response
{
    "key": "aqa_sk_xxxxxxxxxxxxx",
    "id": "key_123",
    "expires_at": "2025-12-05T00:00:00Z"
}
```

##### 10.1.3 Modo JWT (Futuro - SaaS)

```python
# Header obrigatório
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Endpoints de autenticação
POST /api/v1/auth/login       # Obtém token
POST /api/v1/auth/refresh     # Renova token
POST /api/v1/auth/logout      # Invalida token
```

---

#### 10.2 Rate Limiting

```yaml
# Configuração via ambiente
AQA_RATE_LIMIT_ENABLED=true
AQA_RATE_LIMIT_REQUESTS_PER_MINUTE=60
AQA_RATE_LIMIT_BURST=10

# Headers de resposta
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1701792000

# Response quando excedido (429 Too Many Requests)
{
    "error": "rate_limit_exceeded",
    "message": "Too many requests. Retry after 30 seconds.",
    "retry_after": 30
}
```

**Limites por operação:**

| Operação | Limite/min | Justificativa |
|----------|-----------|---------------|
| `POST /generate` | 10 | Alto custo LLM |
| `POST /execute` | 30 | Recursos de execução |
| `GET /*` | 120 | Leitura barata |
| `DELETE /*` | 20 | Operações destrutivas |

---

#### 10.3 CORS (Cross-Origin Resource Sharing)

```python
# Configuração via ambiente
AQA_CORS_ORIGINS=http://localhost:3000,https://app.aqa.dev
AQA_CORS_ALLOW_CREDENTIALS=true
AQA_CORS_MAX_AGE=3600

# FastAPI config
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

#### 10.4 Segurança de Segredos

```yaml
# Variáveis sensíveis NUNCA são logadas ou expostas
# A API mascara automaticamente:
- OPENAI_API_KEY → "sk-...xxxx"
- XAI_API_KEY → "xai-...xxxx"
- Tokens em headers → "Bearer ...xxxx"
- Senhas em bodies → "****"

# Endpoint seguro para verificar status (sem expor valores)
GET /api/v1/secrets/status
{
    "OPENAI_API_KEY": {"configured": true, "masked": "sk-...7f3a"},
    "XAI_API_KEY": {"configured": false, "masked": null}
}
```

---

### 11. Job Engine e Background Tasks

#### 11.1 Arquitetura de Jobs

Operações longas (geração, execução) são processadas de forma assíncrona.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │ ──▶ │   API       │ ──▶ │  Job Queue  │
│   (UI)      │     │   Layer     │     │  (Memory)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │                   │                   ▼
       │                   │            ┌─────────────┐
       │                   │            │   Worker    │
       │                   │            │  (Thread)   │
       │◀──────────────────┼────────────┤             │
       │    WebSocket      │            └─────────────┘
       │    Events         │
```

#### 11.2 Ciclo de Vida de um Job

```python
# Estados possíveis
class JobStatus(Enum):
    PENDING = "pending"       # Na fila, aguardando
    RUNNING = "running"       # Em execução
    COMPLETED = "completed"   # Finalizado com sucesso
    FAILED = "failed"         # Finalizado com erro
    CANCELLED = "cancelled"   # Cancelado pelo usuário
    TIMEOUT = "timeout"       # Excedeu tempo limite
```

**Diagrama de estados:**
```
     ┌─────────┐
     │ PENDING │
     └────┬────┘
          │ Worker picks up
          ▼
     ┌─────────┐
     │ RUNNING │──────────┬──────────┬──────────┐
     └────┬────┘          │          │          │
          │               │          │          │
     Success         Failure    Cancelled    Timeout
          │               │          │          │
          ▼               ▼          ▼          ▼
   ┌───────────┐   ┌────────┐  ┌───────────┐ ┌─────────┐
   │ COMPLETED │   │ FAILED │  │ CANCELLED │ │ TIMEOUT │
   └───────────┘   └────────┘  └───────────┘ └─────────┘
```

#### 11.3 Implementação (FastAPI)

```python
# Job Engine usando ThreadPoolExecutor (MVP)
# Para produção, considerar Celery/RQ

from concurrent.futures import ThreadPoolExecutor
from fastapi import BackgroundTasks
import asyncio

class JobEngine:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: dict[str, Job] = {}

    async def submit(self, job_type: str, fn: Callable, *args) -> str:
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, type=job_type, status=JobStatus.PENDING)
        self.jobs[job_id] = job

        # Executa em thread separada
        loop = asyncio.get_event_loop()
        loop.run_in_executor(self.executor, self._run_job, job, fn, args)

        return job_id

    def _run_job(self, job: Job, fn: Callable, args: tuple):
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        try:
            result = fn(*args)
            job.status = JobStatus.COMPLETED
            job.result = result
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
        finally:
            job.completed_at = datetime.utcnow()
```

#### 11.4 API de Jobs

```yaml
# Submeter job
POST /api/v1/execute
{
    "plan_id": "abc-123",
    "parallel": true
}
# Response: 202 Accepted
{
    "job_id": "job_xyz789",
    "status": "pending",
    "created_at": "2024-12-05T14:30:00Z"
}

# Consultar status
GET /api/v1/jobs/{job_id}
{
    "job_id": "job_xyz789",
    "type": "execution",
    "status": "running",
    "progress": {
        "current_step": 3,
        "total_steps": 10,
        "current_step_id": "login"
    },
    "started_at": "2024-12-05T14:30:01Z",
    "elapsed_ms": 4523
}

# Cancelar job
DELETE /api/v1/jobs/{job_id}
# Response: 200 OK
{
    "job_id": "job_xyz789",
    "status": "cancelled"
}
```

#### 11.5 Escalabilidade Futura

| Fase | Engine | Uso |
|------|--------|-----|
| **MVP** | `ThreadPoolExecutor` | Até 10 jobs simultâneos, single instance |
| **v1.1** | `Celery + Redis` | Múltiplos workers, fila persistente |
| **v2.0** | `Kubernetes Jobs` | Auto-scaling, cloud-native |

---

### 12. Métricas e Observabilidade (OTEL)

#### 12.1 OpenTelemetry Integration

O Runner já suporta OTEL. A API Layer estende isso:

```python
# Variáveis de ambiente
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=aqa-api
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production

# Cada execução gera um trace
{
    "trace_id": "abc123def456...",
    "span_id": "span_001",
    "operation": "execute_plan",
    "duration_ms": 4523,
    "steps": [
        {"span_id": "span_002", "step_id": "login", "duration_ms": 450},
        {"span_id": "span_003", "step_id": "get_user", "duration_ms": 230}
    ]
}
```

#### 12.2 Trace IDs na UI

```yaml
# Cada execução retorna trace_id
GET /api/v1/history/{id}
{
    "execution_id": "exec_123",
    "trace_id": "abc123def456...",
    "trace_url": "https://grafana.example.com/trace/abc123def456",
    ...
}
```

**Componente UI:**
```
┌─────────────────────────────────────────────────────────────┐
│  Execução: exec_123                                         │
│  ───────────────────────────────────────────────────────── │
│                                                             │
│  🔗 Trace ID: abc123def456...  [📋 Copiar] [🔍 Ver no OTEL] │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 12.3 Logs Estruturados

```python
# Formato JSON para todos os logs da API
{
    "timestamp": "2024-12-05T14:30:00.123Z",
    "level": "INFO",
    "service": "aqa-api",
    "trace_id": "abc123...",
    "span_id": "span_001",
    "action": "step_executed",
    "plan_id": "plan_123",
    "step_id": "login",
    "duration_ms": 450,
    "status": "passed",
    "metadata": {
        "method": "POST",
        "path": "/auth/login",
        "status_code": 200
    }
}
```

#### 12.4 Métricas Prometheus

```python
# Métricas expostas em /metrics
aqa_plans_generated_total{provider="openai", model="gpt-5.1"} 156
aqa_executions_total{status="success"} 137
aqa_executions_total{status="failure"} 15
aqa_execution_duration_seconds_bucket{le="1.0"} 45
aqa_execution_duration_seconds_bucket{le="5.0"} 120
aqa_execution_duration_seconds_bucket{le="30.0"} 150
aqa_llm_tokens_used_total{provider="openai"} 245000
aqa_cache_hits_total 89
aqa_cache_misses_total 67
```

---

## PARTE III — Editor e Execução

---

### 13. Editor de Planos (Features Avançadas)

#### 13.1 Undo/Redo

```typescript
// Stack de operações
interface EditorState {
    undoStack: PlanSnapshot[];
    redoStack: PlanSnapshot[];
    currentPlan: Plan;
    maxHistorySize: number; // default: 50
}

// Operações
function undo(): void;    // Ctrl+Z
function redo(): void;    // Ctrl+Y / Ctrl+Shift+Z
function canUndo(): boolean;
function canRedo(): boolean;
```

**UI Component:**
```
┌─────────────────────────────────────────────────────────────┐
│  [↶ Undo] [↷ Redo]                    Alterações: 5 de 50   │
└─────────────────────────────────────────────────────────────┘
```

#### 13.2 Snapshots Automáticos

```python
# API para snapshots
POST /api/v1/plans/{id}/snapshot
{
    "trigger": "manual" | "auto" | "before_llm_update",
    "description": "Antes de adicionar casos negativos"
}

GET /api/v1/plans/{id}/snapshots
{
    "snapshots": [
        {
            "id": "snap_001",
            "created_at": "2024-12-05T14:30:00Z",
            "trigger": "auto",
            "description": "Auto-save",
            "size_bytes": 4523
        }
    ]
}

POST /api/v1/plans/{id}/restore/{snapshot_id}
# Restaura plano para estado do snapshot
```

**Configuração:**
```yaml
# Auto-snapshot a cada N modificações
AQA_EDITOR_AUTO_SNAPSHOT_INTERVAL=10

# Máximo de snapshots por plano
AQA_EDITOR_MAX_SNAPSHOTS=20

# Expiração de snapshots (dias)
AQA_EDITOR_SNAPSHOT_TTL_DAYS=7
```

#### 13.3 Modo Somente Leitura

```typescript
// Estados do editor
type EditorMode =
    | "edit"           // Edição livre
    | "readonly"       // Visualização apenas
    | "review"         // Review de mudanças do LLM
    | "locked";        // Bloqueado (execução em andamento)

// Ao receber plano do LLM
interface LLMUpdateReview {
    originalPlan: Plan;
    updatedPlan: Plan;
    diff: PlanDiff;
    mode: "review";  // Força review antes de aceitar
}
```

**UI Component (Review Mode):**
```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ O LLM gerou alterações no plano                        │
│  ───────────────────────────────────────────────────────── │
│                                                             │
│  [Ver Diff]  [Aceitar Todas]  [Rejeitar]  [Revisar Uma a Uma]│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 13.4 Validação em Tempo Real

```typescript
// Debounced validation (300ms após última digitação)
const validateDebounced = debounce(async (plan: Plan) => {
    const result = await api.post('/api/v1/plans/validate', plan);
    setValidationState(result);
}, 300);

// Estado de validação
interface ValidationState {
    isValid: boolean;
    errors: ValidationError[];
    warnings: ValidationWarning[];
    lastValidated: Date;
}
```

---

### 14. Execução Real-Time (WebSocket Avançado)

#### 14.1 Heartbeat

Durante execuções longas, a API envia heartbeats para confirmar que está ativa:

```json
// A cada 5 segundos durante execução
{
    "event": "heartbeat",
    "payload": {
        "job_id": "job_xyz789",
        "timestamp": "2024-12-05T14:30:05Z",
        "elapsed_ms": 5000,
        "status": "running",
        "current_step": "step_3"
    }
}
```

**Detecção de travamento na UI:**
```typescript
const HEARTBEAT_TIMEOUT_MS = 15000; // 3x o intervalo

useEffect(() => {
    const timeout = setTimeout(() => {
        if (lastHeartbeat && Date.now() - lastHeartbeat > HEARTBEAT_TIMEOUT_MS) {
            setExecutionState('stalled');
            showWarning('Execução pode ter travado. Verificando...');
        }
    }, HEARTBEAT_TIMEOUT_MS);
    return () => clearTimeout(timeout);
}, [lastHeartbeat]);
```

#### 14.2 Reconexão Automática

```typescript
// Cliente WebSocket com reconexão
class ResilientWebSocket {
    private lastEventId: string | null = null;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;

    connect(jobId: string) {
        const headers = this.lastEventId
            ? { 'X-Last-Event-Id': this.lastEventId }
            : {};

        this.ws = new WebSocket(
            `ws://api/ws/v1/execute/${jobId}`,
            { headers }
        );

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.lastEventId = data.event_id;
            this.handleEvent(data);
        };

        this.ws.onclose = () => {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => {
                    this.reconnectAttempts++;
                    this.connect(jobId);
                }, this.getBackoffDelay());
            }
        };
    }

    private getBackoffDelay(): number {
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s
        return Math.min(1000 * Math.pow(2, this.reconnectAttempts), 16000);
    }
}
```

#### 14.3 Replay de Eventos Perdidos

```python
# Servidor mantém buffer de eventos por job
class EventBuffer:
    def __init__(self, max_events: int = 1000):
        self.events: dict[str, list[Event]] = {}

    def get_events_since(self, job_id: str, last_event_id: str) -> list[Event]:
        """Retorna eventos após o último recebido pelo cliente."""
        events = self.events.get(job_id, [])
        if not last_event_id:
            return events

        # Encontra posição do último evento
        for i, event in enumerate(events):
            if event.id == last_event_id:
                return events[i + 1:]

        # Se não encontrou, retorna todos
        return events
```

---

### 15. Histórico de Execução (Avançado)

#### 15.1 Filtragem Avançada

```yaml
# Query parameters suportados
GET /api/v1/history?
    status=success,failure          # Múltiplos status
    &plan_id=plan_123               # Plano específico
    &step_id=login                  # Step específico
    &endpoint=/api/users            # Endpoint testado
    &min_duration_ms=1000           # Duração mínima
    &max_duration_ms=5000           # Duração máxima
    &from=2024-12-01T00:00:00Z      # Data início
    &to=2024-12-05T23:59:59Z        # Data fim
    &has_error=true                 # Apenas com erros
    &sort=-created_at               # Ordenação (- = desc)
    &page=1                         # Paginação
    &limit=20
```

**UI Component - Filtros:**
```
┌─────────────────────────────────────────────────────────────┐
│  🔍 Filtros                                    [Limpar]     │
│  ───────────────────────────────────────────────────────── │
│                                                             │
│  Status:  [✓] Sucesso  [✓] Falha  [ ] Erro                 │
│                                                             │
│  Período: [01/12/2024] até [05/12/2024]                    │
│                                                             │
│  Duração: [    0 ms] até [ 5000 ms]                        │
│                                                             │
│  Plano:   [Todos ▼]     Endpoint: [________]               │
│                                                             │
│  Step:    [________]    [🔍 Buscar]                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 15.2 Exportação de Relatórios

```yaml
# Endpoint de exportação
GET /api/v1/history/{id}/export?format=json|html|md|pdf

# Parâmetros opcionais
&include_request_bodies=true
&include_response_bodies=true
&include_headers=true
&include_traces=true
```

**Formatos suportados:**

| Formato | Content-Type | Uso |
|---------|--------------|-----|
| JSON | `application/json` | Programático, CI/CD |
| HTML | `text/html` | Relatório visual offline |
| Markdown | `text/markdown` | Documentação, Git |
| PDF | `application/pdf` | Auditoria, stakeholders |

**Template HTML:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>AQA Execution Report - {{ execution.id }}</title>
    <style>/* Estilos inline para portabilidade */</style>
</head>
<body>
    <header>
        <h1>{{ plan.name }}</h1>
        <p>Executado em: {{ execution.timestamp }}</p>
        <p>Duração: {{ execution.duration_ms }}ms</p>
    </header>

    <section class="summary">
        <div class="stat passed">✅ {{ execution.passed }} passed</div>
        <div class="stat failed">❌ {{ execution.failed }} failed</div>
        <div class="stat skipped">⏭️ {{ execution.skipped }} skipped</div>
    </section>

    <section class="steps">
        {% for step in execution.steps %}
        <article class="step {{ step.status }}">
            <h3>{{ step.id }}: {{ step.description }}</h3>
            <!-- Detalhes do step -->
        </article>
        {% endfor %}
    </section>
</body>
</html>
```

---

### 16. Diff e Versionamento de Planos

Esta seção documenta o sistema completo de versionamento de planos implementado, incluindo
armazenamento versionado, comparação (diff), e operações de rollback.

#### 16.1 Visão Geral da Arquitetura de Versionamento

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PLAN VERSION STORE                                  │
│                    ~/.aqa/plans/{plan_name}/                                 │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  v1.json.gz │  │  v2.json.gz │  │  v3.json.gz │  │  v4.json.gz │        │
│  │  (initial)  │  │  (parent:1) │  │  (parent:2) │  │  (parent:2) │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                             │
│  index.json: { "latest": 4, "versions": [1,2,3,4], "branches": {...} }     │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 16.2 Modelo de Dados (Implementado)

```python
# brain/src/cache.py

@dataclass
class PlanVersion:
    """Representa uma versão específica de um plano."""
    version: int                          # Número da versão (auto-incremento)
    plan_hash: str                        # Hash SHA-256 do conteúdo
    plan: dict[str, Any]                  # Conteúdo do plano
    created_at: str                       # ISO 8601 timestamp
    metadata: dict[str, Any]              # Metadados para auditoria
    parent_version: int | None = None     # Versão anterior (para branching)

@dataclass
class PlanDiff:
    """Resultado da comparação entre duas versões."""
    version_a: int
    version_b: int
    added_lines: list[str]                # Linhas adicionadas
    removed_lines: list[str]              # Linhas removidas
    changed_paths: list[str]              # Paths JSON que mudaram

    @property
    def has_changes(self) -> bool:
        return bool(self.added_lines or self.removed_lines)

    @property
    def summary(self) -> str:
        parts = []
        if self.added_lines:
            parts.append(f"+{len(self.added_lines)} linhas")
        if self.removed_lines:
            parts.append(f"-{len(self.removed_lines)} linhas")
        return ", ".join(parts) or "Sem alterações"
```

#### 16.3 API do PlanVersionStore

```python
# brain/src/cache.py

class PlanVersionStore:
    """Armazena versões de planos com suporte a diff e rollback."""

    def __init__(self, plans_dir: str | None = None):
        """
        Args:
            plans_dir: Diretório para armazenar planos. Default: ~/.aqa/plans
        """

    @classmethod
    def global_store(cls) -> "PlanVersionStore":
        """Retorna instância singleton do store."""

    def save(
        self,
        plan_name: str,
        plan: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> PlanVersion:
        """
        Salva nova versão de um plano.

        Args:
            plan_name: Identificador único do plano
            plan: Conteúdo do plano (dict serializável)
            metadata: Metadados opcionais (modelo LLM, contexto, etc.)

        Returns:
            PlanVersion com número de versão atribuído

        Metadata sugerido para UI:
            - llm_model: str - Modelo usado na geração
            - llm_provider: str - Provider (openai, grok, mock)
            - swagger_hash: str - Hash do OpenAPI de origem
            - user_id: str - Identificador do usuário
            - description: str - Descrição da mudança
            - tags: list[str] - Tags para categorização
        """

    def get(
        self,
        plan_name: str,
        version: int | None = None,
    ) -> PlanVersion | None:
        """
        Obtém versão específica ou latest de um plano.

        Args:
            plan_name: Identificador do plano
            version: Número da versão (None = latest)

        Returns:
            PlanVersion ou None se não existir
        """

    def list_versions(self, plan_name: str) -> list[PlanVersion]:
        """Lista todas as versões de um plano, ordenadas por data."""

    def list_plans(self) -> list[str]:
        """Lista todos os nomes de planos armazenados."""

    def diff(
        self,
        plan_name: str,
        version_a: int,
        version_b: int,
    ) -> PlanDiff | None:
        """
        Compara duas versões de um plano.

        Args:
            plan_name: Identificador do plano
            version_a: Primeira versão (geralmente a mais antiga)
            version_b: Segunda versão (geralmente a mais nova)

        Returns:
            PlanDiff com linhas adicionadas/removidas ou None se versões não existem
        """

    def rollback(
        self,
        plan_name: str,
        to_version: int,
        metadata: dict[str, Any] | None = None,
    ) -> PlanVersion | None:
        """
        Cria nova versão restaurando conteúdo de versão anterior.

        Args:
            plan_name: Identificador do plano
            to_version: Versão a ser restaurada
            metadata: Metadados opcionais (inclui rollback_from automaticamente)

        Returns:
            Nova PlanVersion ou None se versão não existe

        Nota: O rollback NÃO apaga versões, apenas cria nova versão
        com o conteúdo da versão especificada.
        """
```

#### 16.4 Comandos CLI Implementados

| Comando | Descrição | UI Equivalente |
|---------|-----------|----------------|
| `aqa planversion list` | Lista todos os planos versionados | Grid/tabela de planos |
| `aqa planversion versions <plan>` | Lista versões de um plano | Timeline de versões |
| `aqa planversion show <plan> [--version N]` | Mostra conteúdo do plano | Editor readonly |
| `aqa planversion diff <plan> <v1> <v2>` | Compara duas versões | Split view com highlight |
| `aqa planversion save <file> --name <plan>` | Salva plano como nova versão | Botão "Salvar Versão" |
| `aqa planversion rollback <plan> --to-version N` | Restaura versão anterior | Botão "Restaurar" |

**Exemplos de uso:**

```bash
# Listar planos
$ aqa planversion list
╭─────────────────────────────────────────────────────────────────╮
│                     📋 Planos Versionados                        │
├─────────────────────────────────────────────────────────────────┤
│  Nome          │ Versões │ Última Atualização │ Modelo LLM      │
├─────────────────────────────────────────────────────────────────┤
│  api-tests     │ 5       │ 2024-12-05 14:30   │ gpt-4           │
│  auth-flow     │ 3       │ 2024-12-04 10:15   │ grok-beta       │
│  smoke-tests   │ 1       │ 2024-12-03 09:00   │ mock            │
╰─────────────────────────────────────────────────────────────────╯

# Comparar versões
$ aqa planversion diff api-tests 1 2
╭─────────────────────────────────────────────────────────────────╮
│  📊 Diff: api-tests                                              │
│  v1 → v2                                                         │
├─────────────────────────────────────────────────────────────────┤
│  - "timeout": 5000                                               │
│  + "timeout": 10000                                              │
│                                                                  │
│  + "steps": [                                                    │
│  +   { "id": "new-step", "action": "http_request" }             │
│  + ]                                                             │
╰─────────────────────────────────────────────────────────────────╯

# Rollback para versão anterior
$ aqa planversion rollback api-tests --to-version 1
✅ Plano 'api-tests' restaurado para v1 (nova versão: v6)
```

#### 16.5 Endpoints REST para UI

```yaml
# Planos versionados
GET    /api/v1/plans                     # Lista todos os planos
GET    /api/v1/plans/{name}              # Obtém última versão
GET    /api/v1/plans/{name}/versions     # Lista versões de um plano
GET    /api/v1/plans/{name}/versions/{v} # Obtém versão específica
POST   /api/v1/plans/{name}              # Salva nova versão
GET    /api/v1/plans/{name}/diff         # ?v1=1&v2=2 - Compara versões
POST   /api/v1/plans/{name}/rollback     # Body: { "to_version": 3 }
DELETE /api/v1/plans/{name}              # Remove plano (todas versões)
DELETE /api/v1/plans/{name}/versions/{v} # Remove versão específica
```

**Request/Response Examples:**

```json
// POST /api/v1/plans/my-api-tests
// Request:
{
    "plan": {
        "name": "my-api-tests",
        "steps": [...]
    },
    "metadata": {
        "llm_model": "gpt-4",
        "llm_provider": "openai",
        "description": "Added new endpoints",
        "tags": ["api", "smoke"]
    }
}

// Response:
{
    "version": 3,
    "plan_hash": "sha256:abc123...",
    "created_at": "2024-12-05T14:30:00Z",
    "parent_version": 2
}
```

```json
// GET /api/v1/plans/my-api-tests/diff?v1=1&v2=2
// Response:
{
    "version_a": 1,
    "version_b": 2,
    "has_changes": true,
    "summary": "+5 linhas, -2 linhas",
    "added_lines": [
        "  \"timeout\": 10000,",
        "  { \"id\": \"new-step\" }"
    ],
    "removed_lines": [
        "  \"timeout\": 5000,"
    ]
}
```

#### 16.6 UI de Diff Visual (Atualizado)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📊 Comparação de Planos: api-tests                                         │
│  v1 (2024-12-01) ←→ v3 (2024-12-05)                                        │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  📈 Resumo: +5 linhas, -2 linhas, 3 paths modificados                      │
│                                                                             │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │ VERSÃO 1                    │  │ VERSÃO 3                    │          │
│  │ 📅 2024-12-01 10:00         │  │ 📅 2024-12-05 14:30         │          │
│  │ 🤖 gpt-3.5-turbo            │  │ 🤖 gpt-4                    │          │
│  │                             │  │                             │          │
│  │ {                           │  │ {                           │          │
│  │   "name": "api-tests",      │  │   "name": "api-tests",      │          │
│  │ - "timeout": 5000,          │  │ + "timeout": 10000,  ← MUDOU│          │
│  │   "steps": [                │  │   "steps": [                │          │
│  │     { "id": "login" },      │  │     { "id": "login" },      │          │
│  │ -   { "id": "old-step" }    │  │ +   { "id": "new-step" }    │          │
│  │   ]                         │  │ +   { "id": "extra-step" }  │          │
│  │ }                           │  │   ]                         │          │
│  │                             │  │ }                           │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Metadados da Versão 3:                                          │       │
│  │ • Modelo: gpt-4 (openai)                                        │       │
│  │ • Descrição: "Added extra validation step"                      │       │
│  │ • Tags: api, smoke, validation                                  │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  [🔄 Restaurar v1]  [✅ Manter v3]  [📝 Merge Manual]  [📥 Exportar Diff]  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 16.7 Componentes UI Sugeridos

**1. Timeline de Versões:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📜 Histórico de Versões: api-tests                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  v5 ●─────────────────────────────────────────────────────────● (atual)    │
│      │ 2024-12-05 14:30 │ gpt-4 │ "Final adjustments"                      │
│      │                                                                      │
│  v4 ●─────────────────────────────────────────────────────────●            │
│      │ 2024-12-04 16:00 │ gpt-4 │ "Added error handling steps"             │
│      │                                                                      │
│  v3 ●─────────────────────────────────────────────────────────● ← rollback │
│      │ 2024-12-03 11:00 │ grok │ "Rollback from v1"                        │
│      │                                                                      │
│  v2 ●─────────────────────────────────────────────────────────●            │
│      │ 2024-12-02 09:00 │ gpt-3.5 │ "Added auth flow"                      │
│      │                                                                      │
│  v1 ●─────────────────────────────────────────────────────────● (inicial)  │
│      │ 2024-12-01 10:00 │ mock │ "Initial plan"                            │
│                                                                             │
│  [Comparar Selecionados]  [Restaurar Versão]  [Exportar Histórico]         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**2. Card de Plano na Lista:**
```
┌─────────────────────────────────────────────────────────────┐
│  📋 api-tests                                      v5 ▼     │
│  ────────────────────────────────────────────────────────── │
│  🕐 Última atualização: há 2 horas                          │
│  🤖 Modelo: gpt-4 (openai)                                  │
│  📊 5 versões │ 12 steps │ 45 assertions                    │
│                                                             │
│  Tags: [api] [smoke] [validation]                           │
│                                                             │
│  [▶️ Executar]  [✏️ Editar]  [📜 Histórico]  [🔄 Diff]     │
└─────────────────────────────────────────────────────────────┘
```

#### 16.8 Integração com Cache LLM

O sistema de versionamento integra-se com o cache de respostas LLM:

```python
# brain/src/cache.py

class PlanCache:
    """Cache de respostas LLM indexado por hash."""

    def get_cache_key(
        self,
        requirement: str,
        provider: str,
        model: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        """
        Gera hash único para cache baseado em:
        - Texto do requirement normalizado
        - Provider (openai, grok, mock)
        - Modelo (gpt-4, grok-beta, etc.)
        - Opções adicionais (temperature, etc.)

        Isso garante determinismo: mesmos inputs = mesmo cache hit.
        """

    def get(self, key: str) -> dict | None:
        """Obtém resposta cacheada se existir e não expirada."""

    def set(self, key: str, value: dict, ttl: int | None = None) -> None:
        """Armazena resposta no cache com TTL opcional."""
```

**Fluxo de Geração com Cache:**

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  UI: Gerar      │     │   PlanCache     │     │  LLM Provider   │
│  Plano          │────▶│   (hit/miss)    │────▶│  (se miss)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │                       │
         │                      │ cache hit             │
         │◀─────────────────────┘                       │
         │                                              │
         │                      │ cache miss            │
         │                      │◀──────────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐     ┌─────────────────┐
│  PlanVersion    │◀────│   Salvar        │
│  Store          │     │   Versão        │
└─────────────────┘     └─────────────────┘
```

#### 16.9 Eventos WebSocket para Versionamento

```typescript
// Eventos que a UI deve escutar

interface PlanVersionEvent {
    type: 'plan_version_created' | 'plan_version_rollback' | 'plan_deleted';
    plan_name: string;
    version?: number;
    timestamp: string;
    metadata?: Record<string, any>;
}

// Exemplo de uso
ws.onmessage = (event) => {
    const data: PlanVersionEvent = JSON.parse(event.data);

    switch (data.type) {
        case 'plan_version_created':
            // Atualizar lista de versões
            refreshVersionList(data.plan_name);
            showToast(`Nova versão v${data.version} criada`);
            break;

        case 'plan_version_rollback':
            // Highlight na timeline
            highlightRollback(data.plan_name, data.version);
            showToast(`Plano restaurado para v${data.metadata?.to_version}`);
            break;

        case 'plan_deleted':
            // Remover da lista
            removePlanFromList(data.plan_name);
            break;
    }
};
```

#### 16.10 Casos de Uso de Versionamento

| Cenário | Trigger | Ação Backend | Ação UI |
|---------|---------|--------------|---------|
| LLM gera novo plano | `aqa generate` | `PlanVersionStore.save()` | Criar card, notificação |
| Usuário edita plano | Botão "Salvar" | `PlanVersionStore.save()` | Increment version badge |
| Comparar versões | Seleção de 2 versões | `PlanVersionStore.diff()` | Split view com cores |
| Restaurar versão | Botão "Restaurar" | `PlanVersionStore.rollback()` | Atualizar timeline |
| Exportar histórico | Botão "Exportar" | Serializar todas versões | Download JSON/CSV |
| Limpar versões antigas | Settings | Bulk delete versões < N | Atualizar contagem |

---

## PARTE IV — Extensibilidade Futura

---

### 17. Módulos Futuros (Placeholders)

#### 17.1 Mobile Testing (Android Emulator)

> **Status**: Placeholder para v2.0+

```yaml
# Endpoints futuros
POST   /api/v1/mobile/emulator/start
POST   /api/v1/mobile/emulator/stop
GET    /api/v1/mobile/emulator/devices
GET    /api/v1/mobile/emulator/{device_id}/screenshot
POST   /api/v1/mobile/execute

# WebSocket para sessão mobile
WS     /ws/v1/mobile/{session_id}
```

**Novos tipos de step no DAG:**
```json
{
    "id": "mobile_login",
    "action": "mobile_tap",
    "params": {
        "selector": "id:login_button",
        "device_id": "emulator-5554"
    }
}
```

| Action | Descrição |
|--------|-----------|
| `mobile_tap` | Toque em elemento |
| `mobile_fill` | Preenche campo de texto |
| `mobile_swipe` | Desliza na direção |
| `mobile_assert` | Verifica elemento visível |
| `mobile_screenshot` | Captura tela |

#### 17.2 Web UI Testing (Playwright/Puppeteer)

> **Status**: Placeholder para v2.0+

```yaml
# Endpoints futuros
POST   /api/v1/web/browser/start
POST   /api/v1/web/browser/stop
POST   /api/v1/web/execute
GET    /api/v1/web/{session_id}/screenshot

# WebSocket para sessão browser
WS     /ws/v1/web/{session_id}
```

**Novos tipos de step:**
```json
{
    "id": "ui_login",
    "action": "ui_fill",
    "params": {
        "selector": "#username",
        "value": "{{username}}"
    }
}
```

| Action | Descrição |
|--------|-----------|
| `ui_navigate` | Navega para URL |
| `ui_click` | Clica em elemento |
| `ui_fill` | Preenche input |
| `ui_select` | Seleciona em dropdown |
| `ui_assert` | Verifica elemento |
| `ui_screenshot` | Captura página |
| `ui_wait` | Aguarda elemento |

#### 17.3 Data Generation

> **Status**: Placeholder para v1.2+

```yaml
# Endpoints futuros
POST   /api/v1/data/generate
{
    "schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "faker": "name"},
            "email": {"type": "string", "faker": "email"},
            "age": {"type": "integer", "min": 18, "max": 65}
        }
    },
    "count": 100
}

POST   /api/v1/data/sql
{
    "table": "users",
    "columns": ["id", "name", "email"],
    "count": 100,
    "dialect": "postgresql"
}
```

#### 17.4 Performance Testing

> **Status**: Placeholder para v2.0+

```yaml
# Endpoints futuros
POST   /api/v1/performance/run
{
    "plan_id": "plan_123",
    "config": {
        "virtual_users": 100,
        "ramp_up_seconds": 30,
        "duration_seconds": 300,
        "think_time_ms": 1000
    }
}

GET    /api/v1/performance/{run_id}/metrics
# Retorna: RPS, latency percentiles, errors, etc.
```

---

### 18. Testabilidade da UI

#### 18.1 Testes E2E (End-to-End)

**Framework recomendado:** Playwright

```typescript
// tests/e2e/generate-plan.spec.ts
import { test, expect } from '@playwright/test';

test('should generate plan from OpenAPI', async ({ page }) => {
    await page.goto('/');

    // Upload OpenAPI
    await page.setInputFiles('[data-testid="openapi-upload"]', 'fixtures/petstore.yaml');

    // Wait for preview
    await expect(page.locator('[data-testid="endpoints-preview"]')).toBeVisible();

    // Configure options
    await page.click('[data-testid="include-negative"]');
    await page.click('[data-testid="include-auth"]');

    // Generate
    await page.click('[data-testid="generate-button"]');

    // Wait for completion
    await expect(page.locator('[data-testid="plan-editor"]')).toBeVisible({ timeout: 30000 });

    // Verify plan structure
    const planJson = await page.locator('[data-testid="plan-json"]').textContent();
    const plan = JSON.parse(planJson);
    expect(plan.steps.length).toBeGreaterThan(0);
});
```

#### 18.2 Testes de Componentes

**Framework recomendado:** Vitest + Testing Library

```typescript
// tests/components/PlanEditor.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { PlanEditor } from '@/components/PlanEditor';

describe('PlanEditor', () => {
    it('should show validation errors in real-time', async () => {
        const invalidPlan = { spec_version: "0.1", steps: [] };

        render(<PlanEditor plan={invalidPlan} />);

        await screen.findByText(/Plano deve ter pelo menos 1 step/);
        expect(screen.getByTestId('validation-status')).toHaveClass('error');
    });

    it('should support undo/redo', async () => {
        const plan = createValidPlan();
        render(<PlanEditor plan={plan} />);

        // Make a change
        fireEvent.change(screen.getByTestId('step-0-id'), { target: { value: 'new_id' } });

        // Undo
        fireEvent.click(screen.getByTestId('undo-button'));
        expect(screen.getByTestId('step-0-id')).toHaveValue(plan.steps[0].id);

        // Redo
        fireEvent.click(screen.getByTestId('redo-button'));
        expect(screen.getByTestId('step-0-id')).toHaveValue('new_id');
    });
});
```

#### 18.3 Testes de Integração API → Brain

```python
# tests/integration/test_api_brain.py
import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_generate_plan_integration():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload OpenAPI spec
        with open("fixtures/petstore.yaml", "rb") as f:
            response = await client.post(
                "/api/v1/plans/generate",
                files={"swagger": f},
                data={"llm_mode": "mock"}
            )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Poll for completion
        for _ in range(30):
            status = await client.get(f"/api/v1/jobs/{job_id}")
            if status.json()["status"] == "completed":
                break
            await asyncio.sleep(1)

        # Verify result
        result = await client.get(f"/api/v1/jobs/{job_id}")
        assert result.json()["status"] == "completed"

        plan = result.json()["result"]
        assert plan["spec_version"] == "0.1"
        assert len(plan["steps"]) > 0

@pytest.mark.asyncio
async def test_execute_plan_integration():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create plan
        plan = create_test_plan()

        # Execute
        response = await client.post(
            "/api/v1/execute",
            json={"plan": plan}
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait and verify
        result = await wait_for_job(client, job_id)
        assert result["status"] == "completed"
        assert result["result"]["passed"] > 0
```

#### 18.4 Data-Testid Convention

```typescript
// Convenção para identificadores de teste
// Formato: [component]-[element]-[variant]

// Exemplos:
data-testid="plan-editor"              // Container
data-testid="plan-editor-save"         // Botão salvar
data-testid="plan-editor-undo"         // Botão undo
data-testid="step-0-id"                // Input ID do step 0
data-testid="step-0-delete"            // Botão delete do step 0
data-testid="validation-status"        // Indicador de validação
data-testid="execution-progress"       // Barra de progresso
data-testid="history-table"            // Tabela de histórico
data-testid="history-row-0"            // Linha 0 do histórico
```

---

## PARTE V — Referência

---

## 19. Glossário Oficial

| Termo | Definição |
|-------|-----------|
| **AQA** | Autonomous Quality Agent - nome do sistema |
| **Brain** | Subsistema Python responsável por IA, geração e validação |
| **Runner** | Binário Rust que executa planos UTDL com alta performance |
| **UTDL** | Universal Test Definition Language - formato JSON dos planos |
| **Plan/Plano** | Arquivo UTDL contendo configuração e lista de steps |
| **Step** | Unidade atômica de execução (requisição HTTP, wait, etc.) |
| **Assertion** | Regra de validação (status_code, json_body, header, latency) |
| **Extract/Extraction** | Regra para capturar dados da resposta para uso posterior |
| **Context** | Dicionário de variáveis disponíveis durante execução |
| **DAG** | Directed Acyclic Graph - grafo de dependências entre steps |
| **Provider** | Serviço de LLM (OpenAI, xAI) |
| **Mock Mode** | Modo de teste que simula respostas do LLM |
| **Real Mode** | Modo que usa APIs reais de LLM (custo) |
| **Workspace** | Diretório `.aqa/` com configurações e planos |
| **Job** | Tarefa assíncrona (geração ou execução) |
| **Trace** | Registro de telemetria OpenTelemetry |
| **Snapshot** | Cópia de um plano em determinado momento |
| **Diff** | Comparação entre duas versões de um plano |
| **Heartbeat** | Sinal periódico de que uma execução está ativa |

---

### 20. Mapa de Estados Globais da UI

#### 20.1 Estados do Workspace

```typescript
type WorkspaceState =
    | "not_initialized"   // Nenhum .aqa/ encontrado
    | "loading"           // Carregando configuração
    | "loaded"            // Pronto para uso
    | "corrupted"         // config.yaml inválido
    | "missing_config";   // .aqa/ existe mas sem config.yaml
```

#### 20.2 Estados do LLM

```typescript
type LLMState =
    | "mock"              // Usando MockLLMProvider
    | "real_available"    // Real mode, API key válida
    | "real_unavailable"  // Real mode, sem API key
    | "real_error"        // Real mode, erro de conexão
    | "switching";        // Trocando de modo
```

#### 20.3 Estados do Runner

```typescript
type RunnerState =
    | "not_found"         // Binário não encontrado
    | "idle"              // Pronto, nenhuma execução
    | "running"           // Executando plano
    | "error"             // Última execução falhou
    | "compiling";        // Compilando (se auto-build)
```

#### 20.4 Estados do Editor

```typescript
type EditorState =
    | "empty"             // Nenhum plano aberto
    | "loading"           // Carregando plano
    | "editing"           // Editando (tem alterações)
    | "saved"             // Salvo (sem alterações)
    | "readonly"          // Somente leitura
    | "review"            // Revisando diff do LLM
    | "locked"            // Bloqueado (execução em andamento)
    | "error";            // Plano inválido
```

#### 20.5 Estados de Execução

```typescript
type ExecutionState =
    | "idle"              // Nenhuma execução
    | "pending"           // Aguardando início
    | "running"           // Em execução
    | "paused"            // Pausado (futuro)
    | "completed"         // Finalizado com sucesso
    | "failed"            // Finalizado com falhas
    | "cancelled"         // Cancelado pelo usuário
    | "timeout"           // Excedeu tempo limite
    | "stalled";          // Sem heartbeat (possível travamento)
```

#### 20.6 Diagrama de Estados Completo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ESTADOS GLOBAIS DA UI                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WORKSPACE          LLM              RUNNER           EDITOR                │
│  ──────────        ─────            ───────          ───────               │
│  not_initialized   mock ◄──────►    not_found        empty                  │
│       │               │                │                │                   │
│       ▼               ▼                ▼                ▼                   │
│    loading         switching         idle            loading               │
│       │               │                │                │                   │
│       ▼               ▼                ▼                ▼                   │
│    loaded          real_available    running ◄───►   editing               │
│       │               │                │                │                   │
│       ▼               ▼                ▼                ▼                   │
│   corrupted       real_unavailable   error           saved                 │
│                       │                                 │                   │
│                       ▼                                 ▼                   │
│                   real_error                         readonly              │
│                                                         │                   │
│                                                         ▼                   │
│                                                       review               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 21. Casos de Erro Críticos e Recuperação

#### 21.1 Tabela de Erros e Recuperação

| Código | Erro | Causa | Recuperação | UI Action |
|--------|------|-------|-------------|-----------|
| `WS_NOT_INIT` | Workspace não inicializado | `.aqa/` não existe | `aqa init` | Wizard de setup |
| `WS_CORRUPTED` | Workspace corrompido | `config.yaml` inválido | Editar ou recriar | Modal com opções |
| `LLM_NO_KEY` | API key ausente | Variável não configurada | Configurar API key | Link para Settings |
| `LLM_INVALID_KEY` | API key inválida | Key expirada ou errada | Verificar/atualizar key | Input para nova key |
| `LLM_RATE_LIMIT` | Rate limit excedido | Muitas chamadas | Aguardar ou usar mock | Timer + sugestão mock |
| `LLM_TIMEOUT` | Timeout do LLM | Servidor lento | Retry ou mock | Retry button |
| `RUNNER_NOT_FOUND` | Runner não encontrado | Não compilado | `cargo build --release` | Instruções de build |
| `RUNNER_CRASH` | Runner crashou | Bug ou OOM | Verificar logs | Link para logs |
| `PLAN_INVALID` | Plano inválido | Estrutura errada | Corrigir erros | Lista de erros clicáveis |
| `PLAN_CYCLE` | Dependência circular | `A→B→A` | Remover ciclo | Highlight no DAG |
| `OPENAPI_INVALID` | OpenAPI inválida | Spec malformada | Corrigir spec | Erros de validação |
| `EXEC_TIMEOUT` | Timeout de execução | Plano muito longo | Aumentar timeout | Slider de timeout |
| `EXEC_CANCELLED` | Execução cancelada | Usuário cancelou | N/A | Confirmação |
| `NET_ERROR` | Erro de rede | Sem conexão | Verificar rede | Retry button |
| `AUTH_FAILED` | Autenticação falhou | Credenciais erradas | Verificar credenciais | Link para Settings |

#### 21.2 Componente de Erro Padrão

```typescript
interface ErrorDisplay {
    code: string;
    title: string;
    message: string;
    recoveryActions: RecoveryAction[];
    details?: string;      // Stack trace, etc.
    helpUrl?: string;      // Link para docs
}

interface RecoveryAction {
    label: string;
    action: () => void;
    primary?: boolean;
}

// Exemplo de uso
<ErrorDisplay
    code="LLM_NO_KEY"
    title="API Key não configurada"
    message="Configure uma API key para usar o modo Real."
    recoveryActions={[
        { label: "Configurar", action: openSettings, primary: true },
        { label: "Usar Mock", action: switchToMock }
    ]}
    helpUrl="/docs/setup#api-keys"
/>
```

#### 21.3 Fluxo de Recuperação de Erros

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Erro      │ ──▶ │   Detectar  │ ──▶ │   Mostrar   │
│   Ocorre    │     │   Tipo      │     │   Modal     │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
            ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
            │   Action 1  │           │   Action 2  │           │   Dismiss   │
            │   (Primary) │           │ (Secondary) │           │             │
            └─────────────┘           └─────────────┘           └─────────────┘
                    │                          │                          │
                    ▼                          ▼                          ▼
            ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
            │   Retry     │           │   Workaround│           │   Log &     │
            │   Original  │           │   Alternativo│           │   Continue  │
            └─────────────┘           └─────────────┘           └─────────────┘
```

---

## 22. Exemplos UTDL para Implementação UI

Esta seção fornece exemplos prontos para uso durante o desenvolvimento da UI.

### 22.1 Fluxo de Autenticação OAuth2

```json
{
  "name": "OAuth2 Authentication Flow",
  "description": "Testa login OAuth2 com refresh token",
  "base_url": "https://api.example.com",
  "global_headers": {
    "Content-Type": "application/json",
    "X-Client-Version": "1.0.0"
  },
  "variables": {
    "client_id": "{{env:OAUTH_CLIENT_ID}}",
    "client_secret": "{{env:OAUTH_CLIENT_SECRET}}"
  },
  "steps": [
    {
      "id": "authorize",
      "method": "POST",
      "path": "/oauth/token",
      "body": {
        "grant_type": "client_credentials",
        "client_id": "{{client_id}}",
        "client_secret": "{{client_secret}}",
        "scope": "read write"
      },
      "expect": {
        "status": 200,
        "body_contains": ["access_token", "refresh_token"]
      },
      "extract": {
        "access_token": "$.access_token",
        "refresh_token": "$.refresh_token",
        "expires_in": "$.expires_in"
      }
    },
    {
      "id": "use_token",
      "depends_on": ["authorize"],
      "method": "GET",
      "path": "/api/v1/user/profile",
      "headers": {
        "Authorization": "Bearer {{access_token}}"
      },
      "expect": {
        "status": 200,
        "json_schema": {
          "type": "object",
          "required": ["id", "email"]
        }
      },
      "extract": {
        "user_id": "$.id",
        "user_email": "$.email"
      }
    },
    {
      "id": "refresh_flow",
      "depends_on": ["authorize"],
      "method": "POST",
      "path": "/oauth/token",
      "body": {
        "grant_type": "refresh_token",
        "refresh_token": "{{refresh_token}}"
      },
      "expect": {
        "status": 200,
        "body_contains": ["access_token"]
      }
    }
  ]
}
```

### 22.2 API CRUD Completa

```json
{
  "name": "CRUD Operations",
  "description": "Teste completo de operações CRUD",
  "base_url": "https://api.example.com/v1",
  "steps": [
    {
      "id": "create",
      "method": "POST",
      "path": "/resources",
      "body": {
        "name": "Test Resource",
        "type": "example"
      },
      "expect": {
        "status": 201,
        "headers": {
          "Location": "regex:^/resources/\\d+$"
        }
      },
      "extract": {
        "resource_id": "$.id"
      }
    },
    {
      "id": "read",
      "depends_on": ["create"],
      "method": "GET",
      "path": "/resources/{{resource_id}}",
      "expect": {
        "status": 200,
        "body": {
          "id": "{{resource_id}}",
          "name": "Test Resource"
        }
      }
    },
    {
      "id": "update",
      "depends_on": ["read"],
      "method": "PUT",
      "path": "/resources/{{resource_id}}",
      "body": {
        "name": "Updated Resource"
      },
      "expect": {
        "status": 200
      }
    },
    {
      "id": "verify_update",
      "depends_on": ["update"],
      "method": "GET",
      "path": "/resources/{{resource_id}}",
      "expect": {
        "status": 200,
        "body": {
          "name": "Updated Resource"
        }
      }
    },
    {
      "id": "delete",
      "depends_on": ["verify_update"],
      "method": "DELETE",
      "path": "/resources/{{resource_id}}",
      "expect": {
        "status": 204
      }
    },
    {
      "id": "verify_delete",
      "depends_on": ["delete"],
      "method": "GET",
      "path": "/resources/{{resource_id}}",
      "expect": {
        "status": 404
      }
    }
  ]
}
```

### 22.3 Testes Negativos e Edge Cases

```json
{
  "name": "Negative Test Cases",
  "description": "Valida tratamento de erros da API",
  "base_url": "https://api.example.com",
  "steps": [
    {
      "id": "invalid_auth",
      "method": "GET",
      "path": "/api/protected",
      "headers": {
        "Authorization": "Bearer invalid_token"
      },
      "expect": {
        "status": 401,
        "body": {
          "error": "unauthorized"
        }
      }
    },
    {
      "id": "forbidden_resource",
      "method": "DELETE",
      "path": "/api/admin/users/1",
      "headers": {
        "Authorization": "Bearer {{user_token}}"
      },
      "expect": {
        "status": 403
      }
    },
    {
      "id": "validation_error",
      "method": "POST",
      "path": "/api/users",
      "body": {
        "email": "invalid-email",
        "password": "123"
      },
      "expect": {
        "status": 400,
        "body_contains": ["validation", "error"]
      }
    },
    {
      "id": "not_found",
      "method": "GET",
      "path": "/api/resources/nonexistent-id",
      "expect": {
        "status": 404
      }
    },
    {
      "id": "rate_limit",
      "method": "GET",
      "path": "/api/expensive-operation",
      "repeat": 100,
      "expect": {
        "status_one_of": [200, 429],
        "if_status_429": {
          "headers": {
            "Retry-After": "exists"
          }
        }
      }
    },
    {
      "id": "large_payload",
      "method": "POST",
      "path": "/api/upload",
      "body": {
        "data": "{{generate:random_string:10000000}}"
      },
      "expect": {
        "status": 413
      }
    }
  ]
}
```

### 22.4 Execução Paralela com DAG Complexo

```json
{
  "name": "Complex DAG Execution",
  "description": "Demonstra execução paralela com dependências",
  "base_url": "https://api.example.com",
  "config": {
    "max_parallel": 5,
    "timeout_per_step": 30
  },
  "steps": [
    {
      "id": "setup",
      "method": "POST",
      "path": "/api/test/setup",
      "expect": { "status": 200 }
    },
    {
      "id": "branch_a1",
      "depends_on": ["setup"],
      "method": "GET",
      "path": "/api/data/a",
      "expect": { "status": 200 }
    },
    {
      "id": "branch_a2",
      "depends_on": ["setup"],
      "method": "GET",
      "path": "/api/data/b",
      "expect": { "status": 200 }
    },
    {
      "id": "branch_a3",
      "depends_on": ["setup"],
      "method": "GET",
      "path": "/api/data/c",
      "expect": { "status": 200 }
    },
    {
      "id": "merge_a",
      "depends_on": ["branch_a1", "branch_a2", "branch_a3"],
      "method": "POST",
      "path": "/api/aggregate",
      "body": {
        "sources": ["a", "b", "c"]
      },
      "expect": { "status": 200 }
    },
    {
      "id": "branch_b1",
      "depends_on": ["setup"],
      "method": "GET",
      "path": "/api/external/service1",
      "expect": { "status": 200 }
    },
    {
      "id": "branch_b2",
      "depends_on": ["setup"],
      "method": "GET",
      "path": "/api/external/service2",
      "expect": { "status": 200 }
    },
    {
      "id": "final_merge",
      "depends_on": ["merge_a", "branch_b1", "branch_b2"],
      "method": "POST",
      "path": "/api/finalize",
      "expect": { "status": 200 }
    }
  ]
}
```

### 22.5 Visualização DAG na UI

A UI deve renderizar o DAG acima como:

```
                    ┌──────────────┐
                    │    setup     │
                    └──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  branch_a1   │  │  branch_a2   │  │  branch_a3   │
│  /data/a     │  │  /data/b     │  │  /data/c     │
└──────────────┘  └──────────────┘  └──────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                    ┌──────────────┐
                    │   merge_a    │
                    │  /aggregate  │
                    └──────────────┘
                           │
                           ├──────────────────────┐
                           │                      │
┌──────────────┐  ┌──────────────┐               │
│  branch_b1   │  │  branch_b2   │               │
│  /service1   │  │  /service2   │               │
└──────────────┘  └──────────────┘               │
        │                  │                      │
        └──────────────────┼──────────────────────┘
                           │
                    ┌──────────────┐
                    │ final_merge  │
                    │  /finalize   │
                    └──────────────┘
```

### 22.6 Componentes UI para UTDL

#### Step Editor Component

```typescript
interface StepEditorProps {
  step: UTDLStep;
  availableVariables: string[];
  onUpdate: (step: UTDLStep) => void;
  onValidate: () => ValidationResult;
}

// Features:
// - Autocomplete para variáveis {{...}}
// - Syntax highlighting para JSONPath
// - Validação em tempo real
// - Preview de substituição de variáveis
```

#### DAG Visualizer Component

```typescript
interface DAGVisualizerProps {
  steps: UTDLStep[];
  executionState?: ExecutionState;
  onStepClick: (stepId: string) => void;
  layout: 'horizontal' | 'vertical' | 'auto';
}

// Features:
// - Zoom e pan
// - Status colorido por step (pending/running/success/failed)
// - Tooltips com detalhes
// - Highlight de caminho crítico
```

#### Variable Inspector Component

```typescript
interface VariableInspectorProps {
  plan: UTDLPlan;
  executionContext?: ExecutionContext;
}

// Features:
// - Lista todas as variáveis definidas
// - Mostra onde cada variável é usada
// - Valores atuais durante execução
// - Alerta para variáveis não definidas
```

---

## 23. Checklist de Implementação UI

### Fase 1: Core (MVP)
- [ ] CLI wrapper (spawn + IPC)
- [ ] Plan editor básico
- [ ] Execution view simples
- [ ] Status em tempo real
- [ ] Log viewer

### Fase 2: Enhanced
- [ ] DAG visualizer
- [ ] Variable inspector
- [ ] Syntax highlighting UTDL
- [ ] Autocomplete
- [ ] Undo/Redo

### Fase 3: Professional
- [ ] Plan versioning
- [ ] Diff viewer
- [ ] Export relatórios
- [ ] Histórico de execuções
- [ ] Filtros avançados

### Fase 4: Enterprise
- [ ] Multi-user (opcional)
- [ ] API layer completo
- [ ] Rate limiting
- [ ] Métricas OTEL
- [ ] CI/CD integration

---

## Conclusão

Este documento mapeia **todos os pontos de conexão** entre o sistema CLI atual e a futura interface de usuário. Após a auditoria completa, o documento agora inclui:

### ✅ Parte I — Arquitetura e Integração (Original)
- Arquitetura CLI vs UI
- Pontos de entrada principais
- Configurações e toggles
- Fluxos de usuário
- Mapeamento CLI → UI

### ✅ Parte II — Segurança e Infraestrutura (Novo)
- Autenticação (NoAuth, API Key, JWT)
- Rate limiting
- CORS
- Job Engine com ThreadPoolExecutor
- Métricas e OTEL

### ✅ Parte III — Editor e Execução (Novo)
- Undo/Redo
- Snapshots automáticos
- Modo somente leitura
- Heartbeat e reconexão WebSocket
- Filtragem avançada de histórico
- Exportação de relatórios
- Diff de planos com deepdiff

### ✅ Parte IV — Extensibilidade Futura (Novo)
- Mobile Testing (placeholder)
- Web UI Testing (placeholder)
- Data Generation (placeholder)
- Testes E2E, componentes e integração

### ✅ Parte V — Referência (Novo)
- Glossário oficial
- Mapa de estados globais
- Casos de erro e recuperação

---

**O documento está agora:**
- ✔ Enterprise-ready
- ✔ Engineer-friendly
- ✔ UI-team-ready
- ✔ Future-proof

**Próximos passos:**
1. Wireframes baseados neste mapeamento
2. API Layer (FastAPI) seguindo as specs
3. Protótipo de UI com componentes principais
