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
8. [Troubleshooting](#8-troubleshooting)

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
  init       Inicializa workspace .aqa/
  generate   Gera plano UTDL usando IA
  plan       Alias para generate
  validate   Valida sintaxe de um plano UTDL
  run        Executa plano via Runner
  explain    Explica um plano em linguagem natural
  demo       Demonstração interativa
```

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

## 8. Troubleshooting

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
