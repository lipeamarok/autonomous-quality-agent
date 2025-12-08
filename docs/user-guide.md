# Autonomous Quality Agent - User Guide

> Guia completo para usuários do AQA: instalação, configuração e uso diário.

## Índice

1. [Introdução](#1-introdução)
2. [Instalação](#2-instalação)
3. [Início Rápido](#3-início-rápido)
4. [Comandos CLI](#4-comandos-cli)
5. [Configuração](#5-configuração)
6. [Exemplos Práticos](#6-exemplos-práticos)
7. [Variáveis de Ambiente](#7-variáveis-de-ambiente)
8. [Integração CI/CD](#8-integração-cicd)
9. [Exemplos Completos de UTDL](#9-exemplos-completos-de-utdl)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Introdução

O **Autonomous Quality Agent (AQA)** é uma plataforma de engenharia de qualidade que transforma requisitos em testes executáveis automaticamente usando IA.

### O que o AQA faz?

- **Gera planos de teste** a partir de texto natural ou especificações OpenAPI/Swagger
- **Executa testes de API** com alta performance (Runner em Rust)
- **Valida respostas** automaticamente com assertions configuráveis
- **Gerencia autenticação** detectando e implementando fluxos OAuth2, Bearer, API Key

### Componentes

| Componente | Descrição |
|------------|-----------|
| **Brain** (Python) | IA que interpreta requisitos e gera planos de teste |
| **Runner** (Rust) | Motor de execução de alta performance |
| **UTDL** | Formato intermediário dos planos de teste (JSON) |

---

## 2. Instalação

### Pré-requisitos

- Python 3.11+
- Rust 1.75+ (para compilar o Runner)
- Git

### Instalação via pip

```bash
# Clone o repositório
git clone https://github.com/lipeamarok/autonomous-quality-agent.git
cd autonomous-quality-agent

# Instale o Brain (Python)
cd brain
pip install -e .

# Compile o Runner (Rust)
cd ../runner
cargo build --release
```

### Verificar instalação

```bash
# Verificar CLI do Brain
aqa --version

# Verificar Runner
./runner/target/release/runner --help
```

### Instalação do Runner no PATH

```bash
# Linux/macOS
cp runner/target/release/runner /usr/local/bin/

# Windows (PowerShell como Admin)
Copy-Item runner\target\release\runner.exe C:\Windows\System32\
```

---

## 3. Início Rápido

### 3.1 Inicializar Workspace

```bash
aqa init
```

Isso cria a estrutura:

```
.aqa/
├── config.yaml    # Configurações do projeto
├── plans/         # Planos de teste gerados
└── reports/       # Relatórios de execução
```

### 3.2 Gerar Primeiro Plano

```bash
# A partir de texto natural
aqa generate --input "Testar endpoint de health check em /api/health"

# A partir de OpenAPI/Swagger
aqa generate --swagger ./openapi.yaml
```

### 3.3 Validar Plano

```bash
aqa validate plans/plan_001.json
```

### 3.4 Executar Plano

```bash
aqa run plans/plan_001.json
```

---

## 4. Comandos CLI

### Visão Geral

```
aqa [COMANDO] [OPÇÕES]

Comandos:
  init         Inicializa workspace .aqa/
  generate     Gera plano UTDL usando IA
  plan         Alias para generate
  validate     Valida sintaxe de um plano UTDL
  run          Executa plano via Runner
  explain      Explica um plano em linguagem natural
  demo         Demonstração interativa
  history      Histórico de execuções
  show         Visualiza plano em formato legível
  planversion  Gerenciamento de versões de planos
```

### Estabilidade dos Comandos

| Comando | Status | Notas |
|---------|--------|-------|
| `init` | ✅ **Estável** | Pronto para produção |
| `generate` | ✅ **Estável** | Pronto para produção |
| `validate` | ✅ **Estável** | Pronto para produção |
| `run` | ✅ **Estável** | Pronto para produção |
| `explain` | ✅ **Estável** | Pronto para produção |
| `demo` | ✅ **Estável** | Demonstração para onboarding |
| `history` | ✅ **Estável** | Requer storage configurado |
| `show` | ✅ **Estável** | Visualização de planos |
| `plan` | ⚠️ **Alias** | Alias para `generate` |
| `planversion` | ✅ **Estável** | Gerenciamento de versões de planos |

**Legenda:**
- ✅ **Estável**: Pode ser usado em produção, API não mudará
- ⚠️ **Alias**: Redirecionamento para outro comando

### Flags Globais

| Flag | Descrição |
|------|-----------|
| `--verbose, -v` | Logs detalhados |
| `--quiet, -q` | Apenas erros |
| `--json` | Saída JSON (para CI/CD) |
| `--llm-mode` | Modo do LLM: `mock` ou `real` |

---

### `aqa init`

Inicializa um novo workspace AQA.

```bash
aqa init
aqa init --path ./meu-projeto
```

---

### `aqa generate`

Gera plano de teste UTDL.

```bash
# Texto natural
aqa generate --input "Testar CRUD de usuários na API"

# OpenAPI/Swagger
aqa generate --swagger ./api-spec.yaml

# Com base URL específica
aqa generate --input "testar login" --base-url https://api.staging.com

# Salvar em arquivo específico
aqa generate --input "health check" --output custom-plan.json

# Modo mock (sem custo de LLM)
aqa generate --input "login" --llm-mode mock
```

**Opções:**

| Opção | Descrição |
|-------|-----------|
| `--input, -i` | Requisito em texto natural |
| `--swagger, -s` | Arquivo OpenAPI/Swagger |
| `--base-url` | URL base da API |
| `--output, -o` | Arquivo de saída |
| `--llm-mode` | `mock` ou `real` |

---

### `aqa validate`

Valida sintaxe e estrutura de um plano UTDL.

```bash
aqa validate plan.json

# Modo estrito (warnings viram erros)
aqa validate plan.json --strict

# Saída JSON
aqa validate plan.json --json
```

**Saída de sucesso:**
```
✓ Plano válido
  - Versão: 0.1
  - Steps: 5
  - Dependências: OK
  - Ciclos: Nenhum
```

**Saída com erro:**
```
✗ Plano inválido
  - Erro: Step 'get_user' depende de 'login' que não existe
```

---

### `aqa run`

Executa um plano de teste.

```bash
# Executar plano existente
aqa run plan.json

# Gerar e executar em um comando
aqa run --input "testar API de produtos"

# Com limites customizados
aqa run plan.json --max-steps 50 --timeout 120

# Apenas validar (dry-run)
aqa run plan.json --dry-run
```

**Opções:**

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--max-steps` | Máximo de steps | 100 |
| `--timeout` | Timeout total (segundos) | 300 |
| `--parallel` | Steps paralelos | 10 |
| `--dry-run` | Apenas valida, não executa | false |
| `--report` | Arquivo de relatório | auto |

---

### `aqa explain`

Explica um plano em linguagem natural.

```bash
aqa explain plan.json
```

**Exemplo de saída:**
```
📋 Plano: "Teste de Autenticação"

Este plano executa 3 passos:

1. [login] POST /auth/login
   → Realiza login com credenciais
   → Extrai: token JWT

2. [get_profile] GET /users/me
   → Busca perfil do usuário autenticado
   → Depende de: login
   → Valida: status 200, email contém @

3. [logout] POST /auth/logout
   → Encerra sessão
   → Depende de: get_profile
```

---

### `aqa demo`

Executa demonstração interativa.

```bash
aqa demo

# Demonstração específica
aqa demo --scenario auth
aqa demo --scenario crud
aqa demo --scenario health
```

---

## 5. Configuração

### Arquivo de Configuração

O arquivo `.aqa/config.yaml` controla o comportamento do AQA:

```yaml
# .aqa/config.yaml

# Configurações do LLM
llm:
  mode: real              # 'mock' para testes, 'real' para produção
  model: gpt-4           # Modelo preferido
  temperature: 0.2       # Criatividade (0.0 - 2.0)
  max_retries: 3         # Tentativas de correção

# Configurações do Runner
runner:
  path: runner           # Caminho do binário
  max_steps: 100         # Limite de steps
  max_parallel: 10       # Paralelismo
  timeout: 300           # Timeout total (segundos)

# Cache
cache:
  enabled: true
  directory: .aqa/cache
  ttl_hours: 24

# Telemetria
telemetry:
  enabled: false
  endpoint: http://localhost:4317
```

### Prioridade de Configuração

1. **Flags CLI** (maior prioridade)
2. **Variáveis de ambiente**
3. **Arquivo config.yaml**
4. **Valores padrão** (menor prioridade)

---

## 6. Exemplos Práticos

### 6.1 Teste de Health Check

```bash
aqa generate --input "Verificar se a API está online via GET /health"
```

**Plano gerado:**
```json
{
  "spec_version": "0.1",
  "meta": { "name": "Health Check" },
  "config": { "base_url": "https://api.example.com" },
  "steps": [
    {
      "id": "health_check",
      "action": "http_request",
      "params": { "method": "GET", "path": "/health" },
      "assertions": [
        { "type": "status_code", "operator": "eq", "value": 200 }
      ]
    }
  ]
}
```

---

### 6.2 Fluxo de Autenticação

```bash
aqa generate --input "Testar login com usuário admin e verificar perfil"
```

**Plano gerado:**
```json
{
  "steps": [
    {
      "id": "login",
      "action": "http_request",
      "params": {
        "method": "POST",
        "path": "/auth/login",
        "body": {
          "username": "${env:API_USERNAME}",
          "password": "${env:API_PASSWORD}"
        }
      },
      "assertions": [
        { "type": "status_code", "operator": "eq", "value": 200 }
      ],
      "extract": [
        { "source": "body", "path": "token", "target": "auth_token" }
      ]
    },
    {
      "id": "get_profile",
      "depends_on": ["login"],
      "action": "http_request",
      "params": {
        "method": "GET",
        "path": "/users/me",
        "headers": {
          "Authorization": "Bearer ${auth_token}"
        }
      },
      "assertions": [
        { "type": "status_code", "operator": "eq", "value": 200 },
        { "type": "json_body", "path": "email", "operator": "exists" }
      ]
    }
  ]
}
```

---

### 6.3 CRUD Completo

```bash
aqa generate --input "Testar CRUD completo de produtos: criar, listar, atualizar, deletar"
```

---

### 6.4 A partir de OpenAPI

```bash
# Gerar testes para toda a API
aqa generate --swagger ./petstore.yaml

# Com filtro de tags
aqa generate --swagger ./petstore.yaml --tags "users,auth"

# Apenas endpoints específicos
aqa generate --swagger ./petstore.yaml --endpoints "/users,/auth/login"
```

---

## 7. Variáveis de Ambiente

### Variáveis Suportadas

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `AQA_LLM_MODE` | Modo do LLM (`mock`/`real`) | `real` |
| `AQA_LLM_MODEL` | Modelo a usar | `gpt-4` |
| `OPENAI_API_KEY` | Chave da OpenAI | - |
| `ANTHROPIC_API_KEY` | Chave da Anthropic | - |
| `XAI_API_KEY` | Chave da xAI | - |
| `AQA_RUNNER_PATH` | Caminho do Runner | `runner` |
| `AQA_CACHE_DIR` | Diretório de cache | `.aqa/cache` |
| `AQA_VERBOSE` | Modo verbose | `false` |

### Variáveis para Testes

Use variáveis de ambiente nos planos UTDL:

```json
{
  "body": {
    "username": "${env:API_USERNAME}",
    "password": "${env:API_PASSWORD}"
  }
}
```

**Definir variáveis:**
```bash
export API_USERNAME=admin
export API_PASSWORD=secret123
aqa run plan.json
```

---

## 8. Integração CI/CD

### 8.1 GitHub Actions

```yaml
# .github/workflows/api-tests.yml
name: API Tests

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  api-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Setup Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install AQA
        run: |
          cd brain && pip install -e .
          cd ../runner && cargo build --release

      - name: Validate Plans
        run: aqa --json validate .aqa/plans/*.json

      - name: Run API Tests
        env:
          API_USERNAME: ${{ secrets.API_USERNAME }}
          API_PASSWORD: ${{ secrets.API_PASSWORD }}
        run: |
          aqa --json run .aqa/plans/smoke-tests.json > results.json

      - name: Check Results
        run: |
          if ! jq -e '.success' results.json; then
            echo "Tests failed!"
            cat results.json | jq '.steps[] | select(.status == "failed")'
            exit 1
          fi

      - name: Upload Report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: results.json
```

### 8.2 GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - validate
  - test

validate-plans:
  stage: validate
  image: python:3.11
  script:
    - pip install -e brain/
    - aqa --json validate .aqa/plans/*.json
  artifacts:
    when: on_failure
    paths:
      - .aqa/plans/

run-api-tests:
  stage: test
  image: python:3.11
  variables:
    API_USERNAME: $API_USERNAME
    API_PASSWORD: $API_PASSWORD
  before_script:
    - pip install -e brain/
    - apt-get update && apt-get install -y cargo
    - cd runner && cargo build --release
  script:
    - aqa --json run .aqa/plans/smoke-tests.json > results.json
    - "[ $(jq '.success' results.json) = 'true' ]"
  artifacts:
    paths:
      - results.json
    reports:
      junit: results.xml  # se exportar como JUnit
```

### 8.3 Jenkins Pipeline

```groovy
// Jenkinsfile
pipeline {
    agent any

    environment {
        API_USERNAME = credentials('api-username')
        API_PASSWORD = credentials('api-password')
    }

    stages {
        stage('Setup') {
            steps {
                sh 'pip install -e brain/'
                sh 'cd runner && cargo build --release'
            }
        }

        stage('Validate') {
            steps {
                sh 'aqa --json validate .aqa/plans/*.json'
            }
        }

        stage('Test') {
            steps {
                sh 'aqa --json run .aqa/plans/smoke-tests.json > results.json'
                script {
                    def results = readJSON file: 'results.json'
                    if (!results.success) {
                        error "API tests failed: ${results.failed} failures"
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'results.json', fingerprint: true
        }
    }
}
```

### 8.4 Azure DevOps

```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: pip install -e brain/
    displayName: 'Install AQA'

  - script: |
      cd runner && cargo build --release
    displayName: 'Build Runner'

  - script: aqa --json validate .aqa/plans/*.json
    displayName: 'Validate Plans'

  - script: |
      aqa --json run .aqa/plans/smoke-tests.json > results.json
    displayName: 'Run API Tests'
    env:
      API_USERNAME: $(API_USERNAME)
      API_PASSWORD: $(API_PASSWORD)

  - task: PublishTestResults@2
    inputs:
      testResultsFormat: 'JUnit'
      testResultsFiles: '**/results.xml'
```

---

## 9. Exemplos Completos de UTDL

### 9.1 Fluxo de Autenticação OAuth2

```json
{
  "spec_version": "0.1",
  "meta": {
    "id": "oauth2-flow-001",
    "name": "OAuth2 Complete Flow",
    "description": "Testa login, uso do token e refresh",
    "tags": ["auth", "oauth2", "security"]
  },
  "config": {
    "base_url": "https://api.example.com",
    "timeout_ms": 30000,
    "variables": {
      "client_id": "${env:OAUTH_CLIENT_ID}",
      "client_secret": "${env:OAUTH_CLIENT_SECRET}"
    }
  },
  "steps": [
    {
      "id": "obtain_token",
      "action": "http_request",
      "description": "Obtém access token via client credentials",
      "params": {
        "method": "POST",
        "url": "{{base_url}}/oauth/token",
        "headers": {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        "body": "grant_type=client_credentials&client_id={{client_id}}&client_secret={{client_secret}}"
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 200},
        {"type": "json_body", "path": "$.access_token", "operator": "exists"},
        {"type": "json_body", "path": "$.token_type", "operator": "eq", "value": "Bearer"}
      ],
      "extract": [
        {"source": "body", "path": "$.access_token", "target": "access_token"},
        {"source": "body", "path": "$.refresh_token", "target": "refresh_token"},
        {"source": "body", "path": "$.expires_in", "target": "expires_in"}
      ]
    },
    {
      "id": "use_protected_endpoint",
      "action": "http_request",
      "description": "Acessa recurso protegido com token",
      "depends_on": ["obtain_token"],
      "params": {
        "method": "GET",
        "url": "{{base_url}}/api/v1/me",
        "headers": {
          "Authorization": "Bearer ${access_token}"
        }
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 200},
        {"type": "json_body", "path": "$.id", "operator": "exists"}
      ]
    },
    {
      "id": "refresh_token_flow",
      "action": "http_request",
      "description": "Renova token usando refresh token",
      "depends_on": ["use_protected_endpoint"],
      "params": {
        "method": "POST",
        "url": "{{base_url}}/oauth/token",
        "headers": {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        "body": "grant_type=refresh_token&refresh_token=${refresh_token}&client_id={{client_id}}"
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 200},
        {"type": "json_body", "path": "$.access_token", "operator": "exists"}
      ]
    }
  ]
}
```

### 9.2 Casos Negativos (Teste de Erros)

```json
{
  "spec_version": "0.1",
  "meta": {
    "id": "negative-cases-001",
    "name": "API Error Handling Tests",
    "description": "Valida que a API retorna erros apropriados",
    "tags": ["negative", "errors", "validation"]
  },
  "config": {
    "base_url": "https://api.example.com",
    "timeout_ms": 10000
  },
  "steps": [
    {
      "id": "test_401_no_auth",
      "action": "http_request",
      "description": "Acesso sem autenticação deve retornar 401",
      "params": {
        "method": "GET",
        "url": "{{base_url}}/api/protected/resource"
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 401},
        {"type": "json_body", "path": "$.error", "operator": "eq", "value": "unauthorized"}
      ]
    },
    {
      "id": "test_403_forbidden",
      "action": "http_request",
      "description": "Acesso a recurso proibido deve retornar 403",
      "params": {
        "method": "GET",
        "url": "{{base_url}}/api/admin/users",
        "headers": {
          "Authorization": "Bearer ${user_token}"
        }
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 403},
        {"type": "json_body", "path": "$.error", "operator": "eq", "value": "forbidden"}
      ]
    },
    {
      "id": "test_400_invalid_input",
      "action": "http_request",
      "description": "Payload inválido deve retornar 400",
      "params": {
        "method": "POST",
        "url": "{{base_url}}/api/users",
        "headers": {
          "Content-Type": "application/json"
        },
        "body": {
          "email": "invalid-email",
          "password": "123"
        }
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 400},
        {"type": "json_body", "path": "$.errors", "operator": "exists"},
        {"type": "json_body", "path": "$.errors[0].field", "operator": "eq", "value": "email"}
      ]
    },
    {
      "id": "test_404_not_found",
      "action": "http_request",
      "description": "Recurso inexistente deve retornar 404",
      "params": {
        "method": "GET",
        "url": "{{base_url}}/api/users/99999999"
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 404},
        {"type": "json_body", "path": "$.error", "operator": "eq", "value": "not_found"}
      ]
    },
    {
      "id": "test_429_rate_limit",
      "action": "http_request",
      "description": "Exceder rate limit deve retornar 429",
      "params": {
        "method": "GET",
        "url": "{{base_url}}/api/expensive-operation"
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 429},
        {"type": "header", "path": "Retry-After", "operator": "exists"}
      ]
    },
    {
      "id": "test_422_validation_error",
      "action": "http_request",
      "description": "Validação de negócio falha deve retornar 422",
      "params": {
        "method": "POST",
        "url": "{{base_url}}/api/orders",
        "headers": {
          "Content-Type": "application/json"
        },
        "body": {
          "quantity": -1,
          "product_id": "abc123"
        }
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 422},
        {"type": "json_body", "path": "$.message", "operator": "contains", "value": "quantity"}
      ]
    }
  ]
}
```

### 9.3 Plano com Paralelismo Máximo

```json
{
  "spec_version": "0.1",
  "meta": {
    "id": "parallel-smoke-001",
    "name": "Parallel Smoke Tests",
    "description": "Testes de smoke em paralelo para rapidez"
  },
  "config": {
    "base_url": "https://api.example.com",
    "timeout_ms": 5000
  },
  "steps": [
    {
      "id": "check_health",
      "action": "http_request",
      "params": {"method": "GET", "url": "{{base_url}}/health"},
      "assertions": [{"type": "status_code", "operator": "eq", "value": 200}]
    },
    {
      "id": "check_users_api",
      "action": "http_request",
      "depends_on": ["check_health"],
      "params": {"method": "GET", "url": "{{base_url}}/api/users"},
      "assertions": [{"type": "status_code", "operator": "lt", "value": 500}]
    },
    {
      "id": "check_products_api",
      "action": "http_request",
      "depends_on": ["check_health"],
      "params": {"method": "GET", "url": "{{base_url}}/api/products"},
      "assertions": [{"type": "status_code", "operator": "lt", "value": 500}]
    },
    {
      "id": "check_orders_api",
      "action": "http_request",
      "depends_on": ["check_health"],
      "params": {"method": "GET", "url": "{{base_url}}/api/orders"},
      "assertions": [{"type": "status_code", "operator": "lt", "value": 500}]
    },
    {
      "id": "aggregate_results",
      "action": "http_request",
      "description": "Todos endpoints verificados, busca stats",
      "depends_on": ["check_users_api", "check_products_api", "check_orders_api"],
      "params": {"method": "GET", "url": "{{base_url}}/api/stats"},
      "assertions": [{"type": "status_code", "operator": "eq", "value": 200}]
    }
  ]
}
```

---

## 10. Troubleshooting

### Problema: "Runner não encontrado"

**Causa:** O binário do Runner não está no PATH.

**Solução:**
```bash
# Verificar se existe
ls runner/target/release/runner

# Adicionar ao PATH ou especificar
aqa run plan.json --runner-path ./runner/target/release/runner
```

---

### Problema: "API key não configurada"

**Causa:** Variável `OPENAI_API_KEY` não definida.

**Solução:**
```bash
export OPENAI_API_KEY=sk-...

# Ou use modo mock para testes
aqa generate --input "teste" --llm-mode mock
```

---

### Problema: "Plano inválido - ciclo detectado"

**Causa:** Dependências circulares entre steps.

**Solução:**
```bash
# Visualizar dependências
aqa explain plan.json

# Corrigir manualmente o campo depends_on
```

---

### Problema: "Timeout na execução"

**Causa:** API lenta ou plano muito grande.

**Solução:**
```bash
# Aumentar timeout
aqa run plan.json --timeout 600

# Reduzir paralelismo
aqa run plan.json --parallel 2
```

---

### Problema: "Extração falhou - campo não existe"

**Causa:** A resposta da API não contém o campo esperado.

**Solução:**
1. Verifique a resposta real da API
2. Ajuste o `path` no extract
3. Use `aqa run --verbose` para ver respostas

---

## Próximos Passos

- Leia o [Developer Guide](./developer-guide.md) para contribuir
- Consulte a [Architecture](./architecture.md) para detalhes técnicos
- Veja os [Error Codes](./error_codes.md) para referência de erros
