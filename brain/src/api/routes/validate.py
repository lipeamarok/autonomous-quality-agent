"""
================================================================================
Rota: /validate
================================================================================

Validação de planos UTDL.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_validator
from ..schemas.validate import ValidateRequest, ValidateResponse, ValidationIssue
from ...validator import UTDLValidator, ValidationMode


router = APIRouter()


@router.post(
    "",
    response_model=ValidateResponse,
    summary="Validar Plano UTDL",
    description="""
Valida a estrutura de um plano UTDL.

## Modos de validação:

- **strict**: Warnings viram erros. Use para produção/CI.
- **default**: Erros bloqueiam, warnings são reportados.
- **lenient**: Tolerante a planos parciais. Use para desenvolvimento.

## Validações realizadas:

- Estrutura do schema UTDL
- IDs únicos de steps
- Dependências existentes
- Ausência de ciclos no DAG
- Variáveis interpoladas válidas
- Limites de execução (max_steps, max_retries)
    """,
)
async def validate_plan(
    request: ValidateRequest,
    validator: UTDLValidator = Depends(get_validator),
) -> ValidateResponse:
    """
    Valida um plano UTDL.

    ## Parâmetros:

    - **plan**: Plano UTDL a validar (objeto JSON)
    - **mode**: Modo de validação (strict, default, lenient)

    ## Retorna:

    - **is_valid**: Se o plano é válido
    - **issues**: Lista de problemas encontrados
    - **stats**: Estatísticas do plano
    """
    # Mapeia string para enum
    mode_map = {
        "strict": ValidationMode.STRICT,
        "default": ValidationMode.DEFAULT,
        "lenient": ValidationMode.LENIENT,
    }
    validation_mode = mode_map.get(request.mode, ValidationMode.DEFAULT)

    # Configura validator com o modo
    validator = UTDLValidator(mode=validation_mode)

    # Executa validação
    result = validator.validate(request.plan)

    # Converte erros para schema de resposta
    issues: list[ValidationIssue] = []

    # Erros são strings simples, mas structured_errors podem ter mais info
    structured_errors = result.get_errors_with_paths()
    for err_dict in structured_errors:
        issues.append(
            ValidationIssue(
                severity="error",
                code=None,
                message=err_dict.get("message", "Erro desconhecido"),
                path=err_dict.get("path"),
                suggestion=err_dict.get("suggestion"),
            )
        )

    # Warnings são strings simples
    for warning in result.warnings:
        issues.append(
            ValidationIssue(
                severity="warning",
                code=None,
                message=warning,
                path=None,
                suggestion=None,
            )
        )

    # Calcula estatísticas do plano se válido
    stats: dict[str, int] | None = None
    if result.is_valid and result.plan is not None:
        steps = result.plan.steps
        total_assertions = sum(
            len(step.assertions) if step.assertions else 0
            for step in steps
        )
        total_extractions = sum(
            len(step.extract) if step.extract else 0
            for step in steps
        )
        stats = {
            "steps": len(steps),
            "assertions": total_assertions,
            "extractions": total_extractions,
        }

    return ValidateResponse(
        success=True,
        is_valid=result.is_valid,
        issues=issues,
        error_count=len(result.errors),
        warning_count=len(result.warnings),
        stats=stats,
    )
