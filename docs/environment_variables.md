# Variáveis de Ambiente do AQA

Este documento lista todas as variáveis de ambiente suportadas pelo Autonomous Quality Agent.

## Brain (Python)

### LLM e Geração

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `OPENAI_API_KEY` | Chave de API do OpenAI | - |
| `ANTHROPIC_API_KEY` | Chave de API do Anthropic | - |
| `AQA_LLM_PROVIDER` | Provedor LLM (`openai`, `anthropic`) | `openai` |
| `AQA_LLM_MODEL` | Modelo a usar (ex: `gpt-4`, `claude-3`) | `gpt-4` |
| `AQA_LLM_TEMPERATURE` | Temperatura do modelo (0-1) | `0.2` |
| `AQA_LLM_MAX_TOKENS` | Máximo de tokens na resposta | `4096` |

### Cache

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `AQA_CACHE_DIR` | Diretório do cache | `.aqa/cache` |
| `AQA_CACHE_TTL_DAYS` | TTL do cache em dias | `7` |
| `AQA_CACHE_ENABLED` | Habilita cache (`true`/`false`) | `true` |

### CLI

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `AQA_RUNNER_PATH` | Caminho para o binário do Runner | auto-detectado |
| `AQA_DEFAULT_OUTPUT` | Formato de saída padrão (`json`, `text`) | `text` |
| `AQA_VERBOSE` | Modo verbose por padrão | `false` |

---

## Runner (Rust)

### Execução

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `AQA_MAX_STEPS` | Máximo de steps por plano | `100` |
| `AQA_MAX_RETRIES` | Máximo total de retries | `50` |
| `AQA_MAX_PARALLEL` | Máximo de steps em paralelo | `10` |
| `AQA_TIMEOUT_MS` | Timeout por step em ms | `30000` |

### HTTP

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `AQA_HTTP_TIMEOUT_MS` | Timeout HTTP em ms | `10000` |
| `AQA_HTTP_FOLLOW_REDIRECTS` | Seguir redirects | `true` |
| `AQA_HTTP_MAX_REDIRECTS` | Máximo de redirects | `10` |

### Telemetria (OpenTelemetry)

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Endpoint do collector OTEL | - |
| `OTEL_SERVICE_NAME` | Nome do serviço nos traces | `aqa-runner` |
| `OTEL_RESOURCE_ATTRIBUTES` | Atributos adicionais | - |
| `RUST_LOG` | Nível de log (`error`, `warn`, `info`, `debug`, `trace`) | `info` |

### Segurança

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `AQA_STRICT_MODE` | Modo strict (falha em warnings) | `false` |
| `AQA_ALLOWED_HOSTS` | Hosts permitidos (comma-separated) | `*` |
| `AQA_DENY_PRIVATE_IPS` | Bloqueia IPs privados | `false` |

---

## Exemplos

### Configuração Básica

```bash
# Exportar chave do OpenAI
export OPENAI_API_KEY="sk-..."

# Configurar limites de execução
export AQA_MAX_STEPS=50
export AQA_MAX_PARALLEL=5
```

### Configuração para CI/CD

```bash
# Modo strict (falha em warnings)
export AQA_STRICT_MODE=true

# Sem cache (sempre fresco)
export AQA_CACHE_ENABLED=false

# Timeout mais curto
export AQA_TIMEOUT_MS=15000
```

### Configuração para Desenvolvimento

```bash
# Verbose
export RUST_LOG=debug
export AQA_VERBOSE=true

# OpenTelemetry local
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### Arquivo .env

Você pode criar um arquivo `.env` na raiz do projeto:

```env
# .env
OPENAI_API_KEY=sk-...
AQA_MAX_STEPS=100
AQA_MAX_PARALLEL=10
AQA_CACHE_TTL_DAYS=30
```

---

## Precedência

1. **Flags CLI** (maior prioridade)
2. **Variáveis de ambiente**
3. **Arquivo de configuração** (`.aqa/config.toml`)
4. **Valores padrão** (menor prioridade)

Exemplo:
```bash
# Variável de ambiente define MAX_STEPS=50
export AQA_MAX_STEPS=50

# Flag CLI sobrescreve para 100
aqa run --max-steps 100 plan.json
# Resultado: MAX_STEPS=100
```
