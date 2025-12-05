"""
================================================================================
Módulo de Erros Unificados — AQA Brain
================================================================================

Fornece códigos de erro padronizados e mensagens estruturadas para
melhor integração entre Brain e Runner.

## Categorias de Erro

Os códigos são organizados por categoria, compatíveis com o Runner:

| Faixa  | Categoria       | Descrição                     |
|--------|-----------------|-------------------------------|
| E1xxx  | Validação       | Erro no plano de teste        |
| E2xxx  | HTTP            | Erro na requisição HTTP       |
| E3xxx  | Assertion       | Teste não passou              |
| E4xxx  | Configuração    | Problema de setup/ambiente    |
| E5xxx  | Interno         | Bug interno                   |
| E6xxx  | Brain           | Erros específicos do Brain    |

## Por que unificar erros?

1. **Consistência**: Mesma estrutura no Brain e Runner
2. **Automação**: CI/CD pode agir baseado no código
3. **UX**: Mensagens claras com sugestões de correção
4. **Debug**: Path JSON exato para localizar problemas

## Exemplo:

    >>> from brain.src.errors import ValidationError, ErrorCode
    >>> error = ValidationError(
    ...     code=ErrorCode.PLAN_EXCEEDS_MAX_STEPS,
    ...     message="Plano excede limite de steps",
    ...     path="$.steps",
    ...     suggestion="Reduza o número de steps ou aumente o limite",
    ... )
    >>> print(error)
    E6001: Plano excede limite de steps ($.steps)
"""

from .codes import ErrorCode, ErrorCodes, ErrorCategory, Severity
from .structured import (
    StructuredError,
    ValidationError,
    ConfigurationError,
    GenerationError,
    format_error,
    format_errors_for_json,
    format_errors_for_cli,
)
from .limits import (
    ExecutionLimits,
    LimitViolation,
    validate_plan_limits,
)

__all__ = [
    # Códigos
    "ErrorCode",
    "ErrorCodes",
    "ErrorCategory",
    "Severity",
    # Erros estruturados
    "StructuredError",
    "ValidationError",
    "ConfigurationError",
    "GenerationError",
    "format_error",
    "format_errors_for_json",
    "format_errors_for_cli",
    # Limites
    "ExecutionLimits",
    "LimitViolation",
    "validate_plan_limits",
]
