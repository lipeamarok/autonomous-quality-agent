# Interface Reference Document — Pontos de Conexão para UI

> **Objetivo**: Mapear todos os pontos de conexão entre o sistema CLI atual e a futura interface de usuário, facilitando a transição de comandos técnicos para componentes visuais intuitivos.

**Versão:** 1.1.0
**Última atualização:** 2024-12-05
**Status:** Enterprise-ready

---

## Índice

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
16. [Diff de Planos](#16-diff-de-planos)

### Parte IV — Extensibilidade Futura
17. [Módulos Futuros (Placeholders)](#17-módulos-futuros-placeholders)
18. [Testabilidade da UI](#18-testabilidade-da-ui)

### Parte V — Referência
19. [Glossário Oficial](#19-glossário-oficial)
20. [Mapa de Estados Globais da UI](#20-mapa-de-estados-globais-da-ui)
21. [Casos de Erro Críticos e Recuperação](#21-casos-de-erro-críticos-e-recuperação)

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
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BRAIN (Python Core)                                 │
│  Config │ Generator │ Validator │ Cache │ Storage │ LLM Providers           │
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

### 9.4 Estrutura de Diretórios Proposta

```
autonomous-quality-agent/
├── brain/                    # Existente - sem alterações
├── runner/                   # Existente - sem alterações
├── api/                      # NOVO - API Layer
│   ├── __init__.py
│   ├── main.py               # FastAPI app
│   ├── routes/
│   │   ├── workspace.py
│   │   ├── plans.py
│   │   ├── execute.py
│   │   ├── history.py
│   │   └── llm.py
│   ├── websocket/
│   │   └── execution.py
│   └── models/
│       └── requests.py
├── ui/                       # NOVO - Frontend
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── api/
│   └── public/
└── docs/
    └── interface.md          # Este documento
```

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

### 16. Diff de Planos

#### 16.1 Algoritmo Recomendado

```python
# Usar deepdiff para comparação semântica
from deepdiff import DeepDiff

def diff_plans(plan_a: dict, plan_b: dict) -> PlanDiff:
    """
    Compara dois planos e retorna diferenças estruturadas.
    """
    diff = DeepDiff(
        plan_a,
        plan_b,
        ignore_order=True,              # Arrays podem mudar ordem
        report_repetition=True,         # Detecta duplicatas
        view='tree',                    # Estrutura hierárquica
        exclude_paths=["root['meta']['created_at']"]  # Ignora timestamps
    )

    return PlanDiff(
        added=diff.get('dictionary_item_added', {}),
        removed=diff.get('dictionary_item_removed', {}),
        changed=diff.get('values_changed', {}),
        type_changed=diff.get('type_changes', {}),
    )
```

#### 16.2 Estrutura de Diff

```python
@dataclass
class PlanDiff:
    added: dict[str, Any]           # Campos/steps adicionados
    removed: dict[str, Any]         # Campos/steps removidos
    changed: dict[str, Change]      # Valores alterados
    type_changed: dict[str, Change] # Tipos alterados

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    @property
    def summary(self) -> str:
        parts = []
        if self.added:
            parts.append(f"+{len(self.added)} adicionados")
        if self.removed:
            parts.append(f"-{len(self.removed)} removidos")
        if self.changed:
            parts.append(f"~{len(self.changed)} alterados")
        return ", ".join(parts) or "Sem alterações"

@dataclass
class Change:
    path: str           # "steps[2].assertions[0].value"
    old_value: Any
    new_value: Any
```

### 16.3 UI de Diff Visual

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📊 Comparação de Planos                                                    │
│  plan_v1.json ←→ plan_v2.json                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Resumo: +2 steps, -1 step, ~3 alterações                                  │
│                                                                             │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │ ANTES (v1)                  │  │ DEPOIS (v2)                 │          │
│  │                             │  │                             │          │
│  │ steps:                      │  │ steps:                      │          │
│  │   - id: "login"             │  │   - id: "login"             │          │
│  │ -   timeout: 5000           │  │ +   timeout: 10000   ← MUDOU│          │
│  │                             │  │                             │          │
│  │ - - id: "old_step" ← REMOVIDO│  │ + - id: "new_step" ← NOVO  │          │
│  │                             │  │ +   action: "http_request"  │          │
│  │                             │  │                             │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
│                                                                             │
│  [Aceitar v2]  [Manter v1]  [Merge Manual]                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 16.4 Casos de Uso de Diff

| Cenário | Trigger | Ação UI |
|---------|---------|---------|
| LLM regenera plano | Automático após generate | Modal de review |
| Usuário abre versão antiga | Manual via histórico | Split view |
| Comparar dois planos | Manual via seleção | Side-by-side |
| Atualizar OpenAPI | Após parse | Highlight mudanças em endpoints |

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
