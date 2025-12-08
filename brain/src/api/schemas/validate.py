"""
================================================================================
Schemas para /validate
================================================================================

Request e Response para validação de planos UTDL.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    """
    Um problema encontrado na validação.

    ## Severidades:

    - `error`: Bloqueia execução, deve ser corrigido
    - `warning`: Não bloqueia, mas merece atenção
    - `info`: Informativo apenas
    """

    severity: Literal["error", "warning", "info"] = Field(
        ...,
        description="Severidade do problema"
    )
    code: str | None = Field(
        None,
        description="Código de erro estruturado (ex: E1001)"
    )
    message: str = Field(
        ...,
        description="Descrição do problema"
    )
    path: str | None = Field(
        None,
        description="Caminho JSON onde o problema foi encontrado"
    )
    suggestion: str | None = Field(
        None,
        description="Sugestão de como corrigir"
    )


class ValidateRequest(BaseModel):
    """
    Request para validar um plano UTDL.

    ## Exemplo:

        {
            "plan": {
                "spec_version": "0.1",
                "meta": { "name": "Test Plan" },
                "config": { "base_url": "https://api.example.com" },
                "steps": [...]
            },
            "mode": "default"
        }
    """

    plan: dict[str, Any] = Field(
        ...,
        description="Plano UTDL a ser validado"
    )
    mode: Literal["strict", "default", "lenient"] = Field(
        "default",
        description="Modo de validação: strict (warnings viram erros), default, lenient (tolerante)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "plan": {
                        "spec_version": "0.1",
                        "meta": {"name": "Example Plan", "id": "test-123"},
                        "config": {"base_url": "https://api.example.com"},
                        "steps": [
                            {
                                "id": "health_check",
                                "action": "http_request",
                                "params": {"method": "GET", "path": "/health"},
                                "assertions": [{"type": "status_code", "operator": "eq", "value": 200}]
                            }
                        ]
                    },
                    "mode": "default"
                }
            ]
        }
    }


class ValidateResponse(BaseModel):
    """
    Response da validação de plano UTDL.

    ## Exemplo de sucesso:

        {
            "success": true,
            "is_valid": true,
            "issues": [],
            "stats": { "steps": 5, "assertions": 12, "extractions": 3 }
        }

    ## Exemplo de falha:

        {
            "success": true,
            "is_valid": false,
            "issues": [
                {
                    "severity": "error",
                    "code": "E1005",
                    "message": "Step 'step2' depende de 'unknown' que não existe",
                    "path": "$.steps[1].depends_on[0]"
                }
            ],
            "stats": { "steps": 2, "assertions": 1, "extractions": 0 }
        }
    """

    success: bool = Field(True, description="Se a operação foi executada (não se é válido)")
    is_valid: bool = Field(..., description="Se o plano passou na validação")
    issues: list[ValidationIssue] = Field(  # type: ignore[var-annotated]
        default_factory=list,
        description="Lista de problemas encontrados"
    )
    error_count: int = Field(0, description="Número de erros")
    warning_count: int = Field(0, description="Número de warnings")
    stats: dict[str, int] | None = Field(
        None,
        description="Estatísticas do plano (steps, assertions, extractions)"
    )
