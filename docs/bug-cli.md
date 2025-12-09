# 🐛 Bugs CLI - Relatório de Testes Exaustivos

**Data:** 2025-12-09
**Versão testada:** AQA CLI 0.3.0 / API 0.5.0
**Ambiente:** Windows 11, Python 3.11, Rust Runner compilado

---

## ✅ STATUS FINAL: TODOS OS BUGS CORRIGIDOS

| Bug | Status | Descrição |
|-----|--------|-----------|
| BUG-001 a 004 | ✅ Corrigido | Display incorreto do `aqa run` - corrigido `_parse_report()` em execute.py |
| BUG-005 | ✅ Corrigido | `aqa demo` gera schema inválido - corrigido DEMO_PLAN em demo_cmd.py |
| BUG-006 | ✅ Corrigido | `--json` retorna vazio - corrigido console selection em main.py |
| BUG-007 | ✅ Corrigido | `run --swagger` usa real LLM - adicionado suporte MockLLM |
| BUG-008 | ⚪ Não é bug | config.yaml salvo corretamente em UTF-8 (problema de display do PowerShell) |
| BUG-009 | ✅ Corrigido | Runner falha silenciosa - adicionado check de exit code/stderr |
| BUG-010 | ✅ Corrigido | `--include-auth` - steps de auth agora usam formato UTDL correto |
| BUG-011 | ✅ Corrigido | `aqa plan` gera formato incompatível - corrigido _generate_plan_from_spec() |
| BUG-012 | ✅ Corrigido | `--normalize` incompleto - SmartFormatAdapter agora converte action dict |
| BUG-013 | ✅ Corrigido | `--max-steps 0` ignorado - adicionado check explícito |
| BUG-014 | ✅ Corrigido | `planversion diff` crash - corrigido _format_diff_output() |
| BUG-015 | ✅ Corrigido | `--swagger` não aceita URL - alterado de click.Path para str |
| BUG-016 | ✅ Corrigido | Timeout negativo aceito - adicionada validação |
| BUG-017 | ⚪ Removido | `--max-retries` não suportado pelo Runner - flag removida |
| BUG-018 | ⚪ Não é bug | `--include-negative` funciona quando spec tem constraints |

**Arquivos modificados:**
- `brain/src/runner/execute.py` - parsing de relatório do runner
- `brain/src/cli/main.py` - console selection para JSON output
- `brain/src/cli/commands/demo_cmd.py` - DEMO_PLAN template
- `brain/src/cli/commands/run_cmd.py` - validações e MockLLM
- `brain/src/cli/commands/generate_cmd.py` - URL support para --swagger
- `brain/src/cli/commands/plan_cmd.py` - geração de formato UTDL
- `brain/src/cli/commands/plan_version_cmd.py` - diff formatting
- `brain/src/ingestion/security.py` - steps de auth em formato UTDL
- `brain/src/adapter/format_adapter.py` - normalização de formatos antigos

---

## 📊 Resumo Executivo (Original)

| Categoria | Quantidade |
|-----------|------------|
| 🔴 Críticos | 6 |
| 🟠 Médios | 7 |
| 🟡 Menores | 5 |
| **Total** | **18** |

---

## 🔴 BUGS CRÍTICOS (Afetam Funcionalidade Principal)

### BUG-001 a BUG-004: Display Incorreto do `aqa run`

**Sintomas (todos relacionados):**
1. Tabela de resultados sempre vazia
2. Contagem mostra "1/0 passaram" em vez de "1/1"
3. Duração sempre "0.00ms" apesar do runner reportar corretamente
4. Nome do plano sempre "Plano Desconhecido"

**Evidência:**
```
       Resultados dos Steps
┏━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━┓
┃ Step ┃ Status ┃ Duração ┃ Erro ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━┩
└──────┴────────┴─────────┴──────┘   ← VAZIA!

╭─────────────────────────────── ✅ Todos os testes passaram ───────────────────────────────╮
│ ✓ PASSOU | Plano Desconhecido                    ← NOME ERRADO
│ Steps: 1/0 passaram, 0 falharam, 0 pulados       ← CONTAGEM ERRADA
│ Duração: 0.00ms                                  ← DURAÇÃO ERRADA
╰───────────────────────────────────────────────────────────────────────────────────────────╯
```

**Prova que o Runner funciona corretamente:**
```json
// Conteúdo de report_test.json (--report flag)
{
  "plan_name": "Health Check",        // ✅ Correto
  "status": "passed",
  "duration_ms": 309,                 // ✅ Correto
  "summary": {
    "total_steps": 1,
    "passed": 1,                      // ✅ Correto
    "failed": 0
  },
  "steps": [{
    "step_id": "health",
    "status": "passed",
    "duration_ms": 308
  }]
}
```

**Causa Raiz Provável:**
O código em `brain/src/cli/commands/run_cmd.py` não está parseando corretamente o JSON retornado pelo Runner.

**Arquivos a Investigar:**
- `brain/src/cli/commands/run_cmd.py` - função que exibe resultados
- `brain/src/runner/execute.py` - função que executa e parseia output do runner

**Ação:**
1. Localizar onde o relatório do runner é parseado
2. Verificar se está acessando os campos corretos (`plan_name`, `summary.passed`, `duration_ms`, `steps`)
3. Corrigir o mapeamento de campos

---

### BUG-005: `aqa demo` Gera Schema Inválido

**Comando:** `aqa demo`

**Problema:** Gera plano com assertions usando formato antigo:
```json
// GERADO (ERRADO):
"assertions": [{"type": "status", "expected": 200}]

// ESPERADO (CORRETO):
"assertions": [{"type": "status_code", "operator": "eq", "value": 200}]
```

**Validação falha com 16 erros:**
```
aqa validate demo_plan.json
  ❌ Inválido (16 erro(s))
    • Input should be 'eq', 'neq', 'lt', 'gt' or 'contains'
    • Field required (operator)
    • Field required (value)
```

**Arquivo a Corrigir:**
- `brain/src/cli/commands/demo_cmd.py` ou template usado pelo demo

**Ação:**
1. Localizar template do demo
2. Atualizar para usar `operator` + `value` em vez de `expected`
3. Usar `status_code` em vez de `status`

---

### BUG-006: `--json` Retorna Saída Vazia

**Comandos afetados:**
```bash
aqa run test_plan.json --json    # Retorna: (vazio)
aqa history --json               # Retorna: (vazio)
```

**Esperado:** JSON estruturado com os resultados

**Arquivos a Investigar:**
- `brain/src/cli/commands/run_cmd.py`
- `brain/src/cli/commands/history_cmd.py`

**Ação:**
1. Verificar se a flag `--json` está sendo tratada
2. Implementar output JSON quando flag presente

---

### BUG-009: Runner Falha Silenciosa

**Cenário:** Quando o runner não consegue parsear o plano (48 erros de validação), o CLI ainda mostra "sucesso".

**Evidência:**
```bash
aqa run plan_cmd_test.json
# Runner stderr: 48 erros de validação
# CLI output: ✅ Todos os testes passaram (tabela vazia)
```

**Causa:** CLI não verifica stderr do runner nem código de saída.

**Arquivo a Corrigir:**
- `brain/src/runner/execute.py`

**Ação:**
1. Capturar stderr do processo runner
2. Verificar exit code != 0
3. Exibir erro apropriado quando runner falha

---

### BUG-011: `aqa plan` Gera Formato Incompatível

**Comando:** `aqa plan --base-url http://localhost:8000 --output plan.json`

**Problema:** Gera estrutura completamente diferente do UTDL:
```json
// GERADO (ERRADO):
{
  "action": {"type": "http", "method": "GET"},  // Deveria ser "action": "http_request"
  "expected": {"status": 200}                    // Deveria ser assertions array
}
```

**Resultado:** 48 erros de validação

**Arquivo a Corrigir:**
- `brain/src/cli/commands/plan_cmd.py`
- Possivelmente usar mesmo gerador que `aqa generate`

**Ação:**
1. Avaliar se `aqa plan` deveria existir ou ser alias de `aqa generate`
2. Se manter, corrigir para gerar UTDL válido

---

### BUG-014: `planversion diff` Crash

**Comando:** `aqa planversion diff my-test 2 3`

**Erro:**
```
AttributeError: 'str' object has no attribute 'get'
  File "brain/src/cli/commands/plan_version_cmd.py", line 92
    method = action.get("method", "")
```

**Causa:** Código assume que `action` é dict, mas no UTDL correto é string (`"http_request"`).

**Arquivo a Corrigir:**
- `brain/src/cli/commands/plan_version_cmd.py` linha ~92

**Ação:**
```python
# ANTES:
method = action.get("method", "")

# DEPOIS:
if isinstance(action, dict):
    method = action.get("method", "")
else:
    method = step.get("params", {}).get("method", "")
```

---

## 🟠 BUGS MÉDIOS

### BUG-007: `run --swagger` Usa LLM Real por Padrão

**Problema:** `aqa run --swagger` tenta usar LLM real e falha sem API key, enquanto `aqa generate --swagger` usa mock por padrão.

**Inconsistência de UX.**

**Arquivo a Corrigir:**
- `brain/src/cli/commands/run_cmd.py`

**Ação:** Usar mock como padrão, igual ao `generate`.

---

### BUG-010: `--include-auth` Não Detecta SecuritySchemes

**Comando:** `aqa generate --swagger openapi.json --include-auth`

**Problema:** Mesmo com `securitySchemes` definido no OpenAPI, não detecta autenticação.

**Arquivo a Investigar:**
- `brain/src/ingestion/security.py`

**Ação:** Verificar parsing do OpenAPI para securitySchemes.

---

### BUG-012: `--normalize` Incompleto

**Problema:** Flag `--normalize` deveria converter formatos alternativos, mas não converte:
- `action.type='http'` → `action='http_request'`

**Arquivo a Corrigir:**
- `brain/src/adapter/format_adapter.py` ou similar

**Ação:** Implementar conversão completa.

---

### BUG-013: `--max-steps 0` Ignorado

**Comando:** `aqa run test_plan.json --max-steps 0`

**Problema:** Executou 1 step em vez de 0.

**Ação:** Validar no CLI e passar corretamente ao runner.

---

### BUG-015: `--swagger` Não Aceita URL

**Comando:** `aqa generate --swagger http://localhost:8000/openapi.json`

**Erro:** `Path 'http://...' does not exist.`

**Problema:** Click valida como path local antes de tentar download.

**Arquivo a Corrigir:**
- Definição do parâmetro `--swagger` no CLI

**Ação:**
1. Remover validação `exists=True` do Click
2. Implementar download de URL se começar com `http://` ou `https://`

---

### BUG-017: `--max-retries 0` Causa Crash

**Comando:** `aqa run test_plan.json --max-retries 0`

**Erro:** `Falha ao parsear relatório do Runner`

**Causa:** Runner provavelmente não aceita 0 retries.

**Ação:** Validar no CLI (mínimo 1) ou corrigir no runner.

---

### BUG-018: `--include-negative` Não Funciona

**Comando:** `aqa generate --swagger openapi.json --include-negative`

**Problema:** Sempre adiciona "0 casos negativos".

**Causa Provável:** MockLLM não implementa ou lógica está quebrada.

**Arquivo a Investigar:**
- `brain/src/ingestion/negative_cases.py`

---

## 🟡 BUGS MENORES

### BUG-008: `config.yaml` Encoding UTF-8

**Comando:** `aqa config init`

**Problema:** Caracteres como `ã`, `ç` aparecem corrompidos no arquivo gerado.

**Ação:** Usar `encoding='utf-8'` ao escrever arquivo.

---

### BUG-016: Timeout Negativo Aceito

**Comando:** `aqa run test_plan.json --timeout -1`

**Problema:** Aceita valor negativo, deveria validar >= 1.

**Ação:** Adicionar validação no Click.

---

## ✅ Funcionalidades que Funcionam Corretamente

- `aqa validate` (múltiplos arquivos, wildcards, --strict, --normalize parcial)
- `aqa generate --swagger --llm-mode mock`
- `aqa generate --requirement` (com mock)
- `aqa history` (list, show, clear, filtros --status)
- `aqa planversion` (save, list, versions, show) - exceto diff
- `-q` / `--quiet` (exit codes corretos)
- `--report` / `-o` (salva JSON correto do runner)
- `--parallel` (modo paralelo funciona)
- `aqa --version`, `aqa --help`

---

## 🎯 PLANO DE AÇÃO

### Fase 1: Bugs Críticos de Display (Impacto Imediato)
**Tempo estimado: 2-3 horas**

| Ordem | Bug | Arquivo Principal | Complexidade |
|-------|-----|-------------------|--------------|
| 1.1 | BUG-001 a 004 | `run_cmd.py` + `execute.py` | Média |
| 1.2 | BUG-006 | `run_cmd.py` + `history_cmd.py` | Baixa |
| 1.3 | BUG-009 | `execute.py` | Baixa |

**Estratégia:**
1. Abrir `brain/src/runner/execute.py` e entender como runner é chamado
2. Verificar como stdout/stderr são capturados
3. Corrigir parsing do JSON do runner
4. Propagar dados corretos para display

### Fase 2: Geradores Inválidos
**Tempo estimado: 2 horas**

| Ordem | Bug | Arquivo Principal | Complexidade |
|-------|-----|-------------------|--------------|
| 2.1 | BUG-005 | `demo_cmd.py` | Baixa |
| 2.2 | BUG-011 | `plan_cmd.py` | Média |
| 2.3 | BUG-014 | `plan_version_cmd.py` | Baixa |

**Estratégia:**
1. Atualizar templates para UTDL correto
2. Corrigir crash do diff com verificação de tipo

### Fase 3: Flags e Validações
**Tempo estimado: 1-2 horas**

| Ordem | Bug | Arquivo Principal | Complexidade |
|-------|-----|-------------------|--------------|
| 3.1 | BUG-007 | `run_cmd.py` | Baixa |
| 3.2 | BUG-012 | `format_adapter.py` | Média |
| 3.3 | BUG-013, 016, 017 | CLI params | Baixa |
| 3.4 | BUG-015 | `generate_cmd.py` | Média |

### Fase 4: Features Incompletas
**Tempo estimado: 2-3 horas**

| Ordem | Bug | Arquivo Principal | Complexidade |
|-------|-----|-------------------|--------------|
| 4.1 | BUG-010 | `security.py` | Média |
| 4.2 | BUG-018 | `negative_cases.py` | Média |
| 4.3 | BUG-008 | `config_cmd.py` | Baixa |

---

## 📋 Comandos de Teste para Validação

Após cada correção, executar:

```bash
# Setup
cd c:\autonomous-quality-agent\test-workspace
$env:AQA_RUNNER_PATH = "c:\autonomous-quality-agent\runner\target\release\runner.exe"

# Fase 1 - Display
aqa run test_plan.json                    # Deve mostrar tabela preenchida
aqa run test_plan.json --json             # Deve retornar JSON
aqa run failing_test_v2.json              # Deve mostrar erro detalhado
aqa run plan_cmd_test.json                # Deve mostrar erro do runner

# Fase 2 - Geradores
aqa demo && aqa validate demo_plan.json   # Deve ser válido
aqa plan --base-url http://localhost:8000 -o plan.json && aqa validate plan.json
aqa planversion diff my-test 2 3          # Não deve crashar

# Fase 3 - Flags
aqa run --swagger openapi.json            # Deve usar mock
aqa run test_plan.json --max-steps 0      # Deve executar 0 steps
aqa run test_plan.json --timeout -1       # Deve rejeitar
aqa generate --swagger http://localhost:8000/openapi.json  # Deve baixar

# Fase 4 - Features
aqa generate --swagger openapi.json --include-auth   # Deve detectar auth
aqa generate --swagger openapi.json --include-negative  # Deve gerar casos
aqa config init && cat config.yaml        # UTF-8 correto
```

---

## 🏁 Critério de Sucesso

CLI estará 100% quando:
1. ✅ `aqa run` exibe corretamente todos os dados do runner
2. ✅ `--json` retorna output estruturado
3. ✅ `aqa demo` e `aqa plan` geram UTDL válido
4. ✅ `planversion diff` não crasha
5. ✅ Todas as flags funcionam conforme documentado
6. ✅ Erros do runner são propagados ao usuário
