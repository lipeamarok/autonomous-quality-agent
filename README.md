# Autonomous Quality Agent

[![CI](https://github.com/lipeamarok/autonomous-quality-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/lipeamarok/autonomous-quality-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-stable-orange.svg)](https://www.rust-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.5.0-green.svg)](https://github.com/lipeamarok/autonomous-quality-agent/releases)
[![Tests](https://img.shields.io/badge/tests-446%20passed-brightgreen.svg)](brain/tests/)

> **Transformando requisitos em testes executáveis com IA e Alta Performance.**

O **Autonomous Quality Agent** é uma plataforma de engenharia de qualidade que atua como um agente inteligente. Ele ingere documentação técnica (Swagger, Texto), planeja cenários de teste usando LLMs (The Brain) e os executa com performance nativa e concorrência extrema (The Runner).

---

## 📖 Documentação

| Documento | Descrição |
|-----------|-----------|
| [**User Guide**](docs/user-guide.md) | Guia completo para usuários: instalação, CLI, CI/CD |
| [**Developer Guide**](docs/developer-guide.md) | Para contribuidores: estrutura, testes, padrões |
| [**Architecture**](docs/architecture.md) | Decisões técnicas, C4 diagrams, spec UTDL |
| [**Interface Spec**](docs/interface.md) | Especificação completa da UI (roadmap) |
| [**Plugin Development**](docs/plugin_development.md) | Como criar executores customizados |
| [**Error Codes**](docs/error_codes.md) | Referência de códigos de erro |
| [**Environment Variables**](docs/environment_variables.md) | Variáveis de ambiente |
| [**Reference TDD**](docs/reference-tdd.md) | Documento de design técnico completo (histórico) |

---

## 📋 Índice

- [Arquitetura](#-arquitetura-monorepo)
- [Instalação](#-instalação)
- [CLI `aqa`](#-cli-aqa)
- [Comandos](#-comandos)
- [Exemplos de Uso](#-exemplos-de-uso)
- [UTDL - Formato de Planos](#-utdl---universal-test-definition-language)
- [Desenvolvimento](#-desenvolvimento)
- [Licença](#-licença)

---

## 🏗 Arquitetura (Monorepo)

O projeto é dividido em dois componentes principais desacoplados pelo protocolo **UTDL (Universal Test Definition Language)**.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Autonomous Quality Agent                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐         UTDL (JSON)         ┌──────────────────┐    │
│   │              │  ──────────────────────────▶│                  │    │
│   │  🧠 Brain    │                             │  🦀 Runner       │    │
│   │  (Python)    │                             │  (Rust)          │    │
│   │              │◀──────────────────────────  │                  │    │
│   └──────────────┘       Results (JSON)        └──────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 🧠 The Brain (`/brain`)

- **Linguagem:** Python 3.11+
- **Responsabilidade:** Cognição, Planejamento e Validação
- **Função:** Lê requisitos, gera planos de teste em JSON (UTDL) e garante que são válidos antes da execução

**Componentes:**
- `src/cli/` — CLI `aqa` (Click + Rich)
- `src/generator/` — Geração de planos via LLM
- `src/validator/` — Validação de planos UTDL (Pydantic)
- `src/cache/` — Cache de planos gerados

### 🦀 The Runner (`/runner`)

- **Linguagem:** Rust (Tokio + Reqwest)
- **Responsabilidade:** Execução Determinística e Performance
- **Função:** Consome o plano UTDL, executa requisições HTTP em paralelo massivo e gera telemetria (OpenTelemetry)

**Componentes:**
- `src/executors/` — Executores de ações (HTTP, Wait)
- `src/extractors/` — Extração de dados de respostas
- `src/validation/` — Validação de planos
- `src/planner/` — Planejador DAG para execução paralela

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.11+
- Rust (Cargo)
- Make (opcional)

### Setup Rápido

```bash
# Clone o repositório
git clone https://github.com/lipeamarok/autonomous-quality-agent.git
cd autonomous-quality-agent

# Setup completo (Python + Rust)
make setup

# Ou manualmente:
cd brain && pip install -e ".[dev]"
cd ../runner && cargo build --release
```

### Verificar Instalação

```bash
# Verifica se o CLI está disponível
aqa --version

# Roda todos os testes
make test
```

---

## 🖥 CLI `aqa`

O CLI `aqa` é a interface principal para interagir com o Autonomous Quality Agent.

### Sintaxe Básica

```bash
aqa [OPTIONS] COMMAND [ARGS]
```

### Flags Globais

| Flag | Descrição |
|------|-----------|
| `--version` | Mostra versão e sai |
| `-v, --verbose` | Modo verbose (mostra mais detalhes) |
| `-q, --quiet` | Modo silencioso (só erros) |
| `--json` | Saída estruturada em JSON (para CI/CD) |
| `--help` | Mostra ajuda |

---

## 📚 Comandos

### Status de Estabilidade

| Comando | Status | Descrição |
|---------|--------|-----------|
| `init` | ✅ Stable | Inicializa workspace |
| `generate` | ✅ Stable | Gera planos via LLM |
| `validate` | ✅ Stable | Valida planos UTDL |
| `run` | ✅ Stable | Executa testes |
| `plan-list` | ✅ Stable | Lista planos salvos |
| `config` | ✅ Stable | Gerencia configuração |
| `storage` | 🔶 Beta | Backend de storage |
| `cache` | 🔶 Beta | Gerenciamento de cache |
| `trace` | 🔬 Experimental | Tracing e telemetria |

### `aqa init`

Inicializa um workspace AQA no diretório especificado.

```bash
# Inicializa no diretório atual
aqa init

# Inicializa em diretório específico
aqa init ./meu-projeto

# Força sobrescrita se já existir
aqa init --force
```

**Estrutura criada:**
```
.aqa/
├── config.yaml      # Configuração do projeto
├── plans/           # Planos UTDL gerados
└── reports/         # Relatórios de execução
```

### `aqa generate`

Gera um plano de teste UTDL usando IA a partir de um Swagger/OpenAPI.

```bash
# Gera plano a partir de Swagger
aqa generate --swagger api.yaml

# Gera plano a partir de URL
aqa generate --swagger https://api.example.com/swagger.json

# Especifica arquivo de saída
aqa generate --swagger api.yaml --output plano.json
```

### `aqa validate`

Valida a sintaxe e semântica de um ou mais planos UTDL.

```bash
# Valida um arquivo
aqa validate plan.json

# Valida múltiplos arquivos
aqa validate plans/*.json

# Modo strict (warnings viram erros)
aqa validate --strict plan.json

# Saída JSON para CI/CD
aqa --json validate plan.json
```

**Exemplo de saída JSON:**
```json
{
  "success": true,
  "files": [
    {"file": "plan.json", "valid": true, "errors": [], "warnings": []}
  ],
  "summary": {"total": 1, "valid": 1, "invalid": 0}
}
```

### `aqa run`

Executa um plano de teste UTDL usando o Runner.

```bash
# Executa plano existente
aqa run plan.json

# Gera e executa em um comando
aqa run --swagger api.yaml

# Especifica path do runner
aqa run --runner-path ./runner/target/release/runner plan.json

# Saída JSON (ideal para CI/CD)
aqa --json run plan.json
```

**Opções:**

| Opção | Descrição |
|-------|-----------|
| `--swagger` | Gera plano a partir de Swagger antes de executar |
| `--runner-path` | Caminho explícito para o binário do Runner |

---

## 💡 Exemplos de Uso

### Fluxo Completo: Swagger → Testes

```bash
# 1. Inicializa workspace
aqa init

# 2. Gera plano de testes a partir do Swagger
aqa generate --swagger https://petstore.swagger.io/v2/swagger.json

# 3. Valida o plano gerado
aqa validate .aqa/plans/petstore.json

# 4. Executa os testes
aqa run .aqa/plans/petstore.json
```

### Uso em CI/CD (GitHub Actions)

```yaml
- name: Run API Tests
  run: |
    aqa --json validate plan.json
    aqa --json run plan.json > results.json

- name: Check Results
  run: |
    if [ $(jq '.success' results.json) != "true" ]; then
      exit 1
    fi
```

### Modo Silencioso para Scripts

```bash
# Apenas erros são mostrados
aqa -q validate plan.json && aqa -q run plan.json
```

### Debug com Verbose

```bash
# Mostra detalhes da execução
aqa -v run plan.json
```

---

## 📄 UTDL - Universal Test Definition Language

UTDL é o formato JSON que define planos de teste. É o contrato entre Brain e Runner.

### Estrutura Básica

```json
{
  "spec_version": "0.1",
  "meta": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "API Smoke Test",
    "description": "Testes básicos de health check",
    "tags": ["smoke", "api"]
  },
  "config": {
    "base_url": "https://api.example.com",
    "timeout_ms": 5000,
    "global_headers": {
      "Content-Type": "application/json"
    }
  },
  "steps": [
    {
      "id": "health_check",
      "action": "http_request",
      "description": "Verifica se a API está respondendo",
      "params": {
        "method": "GET",
        "path": "/health"
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 200}
      ]
    }
  ]
}
```

### Tipos de Actions

| Action | Descrição |
|--------|-----------|
| `http_request` | Executa requisição HTTP |
| `wait` | Pausa execução por N milissegundos |

### Tipos de Assertions

| Type | Descrição | Exemplo |
|------|-----------|---------|
| `status_code` | Código HTTP | `{"type": "status_code", "operator": "eq", "value": 200}` |
| `json_body` | Campo no JSON | `{"type": "json_body", "path": "data.id", "operator": "eq", "value": 123}` |
| `header` | Header HTTP | `{"type": "header", "path": "Content-Type", "operator": "contains", "value": "json"}` |
| `latency` | Tempo de resposta | `{"type": "latency", "operator": "lt", "value": 500}` |

### Extrações

Capturam valores de respostas para usar em steps seguintes:

```json
{
  "extract": [
    {
      "source": "body",
      "path": "$.auth.token",
      "target": "auth_token"
    },
    {
      "source": "header",
      "path": "X-Request-Id",
      "target": "request_id"
    },
    {
      "source": "status_code",
      "target": "last_status"
    }
  ]
}
```

### Dependências entre Steps

```json
{
  "steps": [
    {"id": "login", "action": "http_request", ...},
    {"id": "get_profile", "depends_on": ["login"], ...}
  ]
}
```

---

## 🛠 Desenvolvimento

### Estrutura do Projeto

```
autonomous-quality-agent/
├── brain/                  # Componente Python
│   ├── src/
│   │   ├── cli/           # CLI aqa com registry pattern
│   │   │   ├── registry.py    # @register_command decorator
│   │   │   └── commands/      # Comandos modulares
│   │   ├── generator/     # Geração via LLM
│   │   ├── validator/     # Validação UTDL
│   │   ├── llm/           # Providers (OpenAI, Mock)
│   │   ├── storage/       # Backends (JSON, SQLite, S3)
│   │   └── telemetry/     # Métricas e tracing
│   └── tests/
│       ├── test_*.py              # Unit tests
│       ├── test_integration*.py   # Integration tests
│       ├── test_e2e_*.py          # End-to-end tests
│       └── test_audit_*.py        # Security audit tests
├── runner/                 # Componente Rust
│   └── src/
│       ├── executors/     # HTTP, Wait, GraphQL
│       ├── extractors/    # Extração de dados
│       ├── planner/       # DAG execution planner
│       └── validation/    # Validação de planos
├── schemas/               # JSON Schemas UTDL
└── docs/                  # Documentação completa
```

### Rodando Testes

```bash
# Todos os testes
make test

# Apenas Python
cd brain && pytest -v

# Apenas Rust
cd runner && cargo test
```

### Cobertura de Testes

- **Python (Brain):** 423 testes (unit, integration, e2e, security audit)
- **Rust (Runner):** 95 testes
- **Total:** 518 testes

### Categorias de Testes

| Categoria | Descrição |
|-----------|-----------|
| Unit Tests | Testes unitários de componentes isolados |
| Integration Tests | Testes de integração Brain ↔ Runner |
| E2E Tests | Testes end-to-end com fluxos completos |
| Extreme Tests | Testes de stress, paralelismo e edge cases |
| Security Audit | Testes de segurança (credential leakage, prompt sanitization) |

---

## 📄 Licença

- **Versões < 1.0.0** (incluindo esta): [MIT License](LICENSE)
- **Versões >= 1.0.0**: [Elastic License 2.0 (ELv2)](https://www.elastic.co/licensing/elastic-license)

Veja o [CHANGELOG](CHANGELOG.md) para detalhes sobre cada versão.
