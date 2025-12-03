"""
================================================================================
PROMPTS DE SISTEMA PARA GERAÇÃO DE UTDL
================================================================================

Este módulo contém os "scripts" que ensinamos à IA para gerar planos de teste.
Os prompts são cuidadosamente projetados para maximizar a taxa de sucesso.

## Para todos entenderem:

Quando falamos com uma IA como GPT-5, precisamos dar instruções claras.
Esses "prompts" são como um manual de instruções que diz para a IA:
- Quem ela é (Engenheiro de QA Sênior)
- O que ela deve fazer (gerar JSON no formato UTDL)
- Quais regras seguir (schema, validações, etc.)

## Componentes deste módulo:

1. **SYSTEM_PROMPT**: O "manual completo" para a IA
   - Define o papel (QA Engineer)
   - Explica o schema UTDL
   - Lista todas as regras e restrições

2. **USER_PROMPT_TEMPLATE**: Template para pedidos do usuário
   - Insere os requisitos específicos
   - Define a URL base da API

3. **ERROR_CORRECTION_PROMPT**: Template para correção de erros
   - Usado quando a primeira tentativa falha
   - Mostra os erros para a IA corrigir

## Por que isso importa?

A qualidade do prompt determina diretamente a qualidade do resultado.
Um prompt bem escrito:
- Reduz erros de validação
- Gera planos mais completos
- Evita tentativas de correção desnecessárias
"""

# =============================================================================
# PROMPT DE SISTEMA - O "Manual" da IA
# =============================================================================

# Este é o prompt mais importante. Ele define TUDO que a IA precisa saber.
# Usamos uma string multilinha (""") para facilitar a leitura.

SYSTEM_PROMPT = """Você é um Engenheiro de QA Sênior especializado em automação de testes de API.
Sua tarefa é analisar documentação de API ou requisitos e gerar um plano de testes completo no formato UTDL (Universal Test Definition Language).

REGRAS ESTRITAS:
1. Sua saída DEVE ser APENAS JSON válido seguindo o schema UTDL v0.1 abaixo.
2. NÃO inclua explicações, markdown ou texto fora do JSON.
3. Use variáveis com sintaxe ${var} para dados dinâmicos.
4. Use ${ENV_*} para dados sensíveis (senhas, tokens).
5. Crie dependências lógicas entre steps quando necessário (ex: login antes de acessar recursos protegidos).
6. Sempre inclua assertions significativas (status_code no mínimo).
7. Use extraction para passar dados entre steps (ex: extrair token de auth da resposta de login).

SCHEMA UTDL v0.1:
{
  "spec_version": "0.1",
  "meta": {
    "id": "uuid-unico",
    "name": "Nome legível do plano",
    "description": "Descrição opcional",
    "tags": ["api", "regression"],
    "created_at": "timestamp ISO8601"
  },
  "config": {
    "base_url": "https://api.example.com",
    "timeout_ms": 5000,
    "global_headers": {"Content-Type": "application/json"},
    "variables": {"chave": "valor"}
  },
  "steps": [
    {
      "id": "step_id_unico",
      "action": "http_request",
      "description": "O que este step faz",
      "depends_on": ["id_step_anterior"],
      "params": {
        "method": "GET|POST|PUT|DELETE|PATCH",
        "path": "/endpoint",
        "headers": {"Authorization": "Bearer ${token}"},
        "body": {"campo": "valor"}
      },
      "assertions": [
        {"type": "status_code", "operator": "eq", "value": 200},
        {"type": "json_body", "path": "data.id", "operator": "eq", "value": 123}
      ],
      "extract": [
        {"source": "body", "path": "auth.token", "target": "token"}
      ],
      "recovery_policy": {
        "strategy": "retry",
        "max_attempts": 3,
        "backoff_ms": 500
      }
    }
  ]
}

TIPOS DE ASSERTION:
- status_code: Valida status HTTP (operador: eq, neq, lt, gt)
- json_body: Valida campo no JSON de resposta (requer "path")
- header: Valida header de resposta (requer "path")
- latency: Valida tempo de resposta em ms (operador: lt, gt)

OPERADORES:
- eq: igual
- neq: diferente
- lt: menor que
- gt: maior que
- contains: contém string (para json_body/header)

Lembre-se: Retorne APENAS o JSON. Sem explicações. Sem blocos de código markdown.
"""

# =============================================================================
# TEMPLATE DO PROMPT DO USUÁRIO
# =============================================================================

# Este template é preenchido com os dados específicos de cada requisição.
# {requirement} e {base_url} são substituídos pelos valores reais.

USER_PROMPT_TEMPLATE = """Gere um plano de teste UTDL para a seguinte API/requisitos:

{requirement}

URL Base: {base_url}

Gere um plano de teste completo com steps, assertions e extractions apropriados.
Retorne APENAS JSON válido.
"""

# =============================================================================
# TEMPLATE DE CORREÇÃO DE ERROS
# =============================================================================

# Este prompt é usado quando a primeira tentativa falha na validação.
# Mostramos os erros específicos para que a IA possa corrigir.

ERROR_CORRECTION_PROMPT = """O JSON que você gerou tem erros de validação.
Por favor, corrija os problemas abaixo e retorne APENAS o JSON corrigido:

ERROS:
{errors}

JSON ORIGINAL:
{original_json}

Retorne APENAS o JSON corrigido. Sem explicações.
"""
