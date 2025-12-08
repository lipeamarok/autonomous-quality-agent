"""
================================================================================
Schemas para /execute
================================================================================

Request e Response para execução de planos UTDL.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StepResultSchema(BaseModel):
    """
    Resultado da execução de um step individual.
    """

    step_id: str = Field(..., description="ID do step executado")
    status: Literal["passed", "failed", "skipped"] = Field(
        ...,
        description="Status da execução"
    )
    duration_ms: float = Field(..., description="Tempo de execução em milissegundos")
    error: str | None = Field(None, description="Mensagem de erro, se falhou")
    assertions_passed: int | None = Field(None, description="Assertions que passaram")
    assertions_failed: int | None = Field(None, description="Assertions que falharam")
    extractions: dict[str, Any] | None = Field(
        None,
        description="Variáveis extraídas neste step"
    )


class ExecuteRequest(BaseModel):
    """
    Request para executar um plano UTDL.

    ## Modos de execução:

    1. Executar plano inline:
        ```json
        {
            "plan": { "spec_version": "0.1", ... }
        }
        ```

    2. Executar plano salvo:
        ```json
        {
            "plan_file": "./plans/login_test.json"
        }
        ```

    3. Gerar e executar (fluxo completo):
        ```json
        {
            "requirement": "Testar login",
            "base_url": "https://api.example.com"
        }
        ```
    """

    # Opção 1: Plano inline
    plan: dict[str, Any] | None = Field(
        None,
        description="Plano UTDL completo a executar"
    )

    # Opção 2: Arquivo de plano
    plan_file: str | None = Field(
        None,
        description="Caminho para arquivo de plano UTDL"
    )

    # Opção 3: Gerar e executar
    requirement: str | None = Field(
        None,
        description="Gerar plano a partir desta descrição e executar"
    )
    swagger: dict[str, Any] | None = Field(
        None,
        description="Gerar plano a partir desta spec OpenAPI e executar"
    )
    base_url: str | None = Field(
        None,
        description="URL base para geração (usado com requirement/swagger)"
    )

    # Opções de execução
    parallel: bool = Field(
        False,
        description="Executar steps em paralelo quando possível (DAG)"
    )
    timeout_seconds: int = Field(
        60,
        ge=1,
        le=3600,
        description="Timeout global em segundos"
    )
    max_steps: int | None = Field(
        None,
        ge=1,
        le=1000,
        description="Limitar número de steps executados"
    )
    dry_run: bool = Field(
        False,
        description="Validar plano sem executar"
    )
    save_report: bool = Field(
        True,
        description="Salvar relatório no histórico"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "plan": {
                        "spec_version": "0.1",
                        "meta": {"name": "Quick Test", "id": "qt-001"},
                        "config": {"base_url": "https://httpbin.org"},
                        "steps": [
                            {
                                "id": "get_ip",
                                "action": "http_request",
                                "params": {"method": "GET", "path": "/ip"},
                                "assertions": [{"type": "status_code", "operator": "eq", "value": 200}]
                            }
                        ]
                    },
                    "timeout_seconds": 30
                }
            ]
        }
    }


class ExecuteSummary(BaseModel):
    """
    Resumo estatístico da execução.
    """

    total_steps: int = Field(..., description="Total de steps no plano")
    passed: int = Field(..., description="Steps que passaram")
    failed: int = Field(..., description="Steps que falharam")
    skipped: int = Field(..., description="Steps pulados")
    total_duration_ms: float = Field(..., description="Duração total em ms")
    success_rate: float = Field(..., description="Taxa de sucesso (0-100)")


class ExecuteResponse(BaseModel):
    """
    Response da execução de plano UTDL.

    ## Exemplo:

        {
            "success": true,
            "execution_id": "exec-abc123",
            "plan_name": "Login Test",
            "summary": {
                "total_steps": 5,
                "passed": 4,
                "failed": 1,
                "skipped": 0,
                "total_duration_ms": 1234.5,
                "success_rate": 80.0
            },
            "steps": [...]
        }
    """

    success: bool = Field(..., description="Se todos os steps passaram")
    execution_id: str | None = Field(None, description="ID da execução para referência")
    plan_id: str | None = Field(None, description="ID do plano executado")
    plan_name: str | None = Field(None, description="Nome do plano executado")
    summary: ExecuteSummary = Field(..., description="Resumo estatístico")
    steps: list[StepResultSchema] = Field(..., description="Resultados de cada step")
    report_saved: bool = Field(False, description="Se o relatório foi salvo")
    generated_plan: bool = Field(
        False,
        description="Se o plano foi gerado (não fornecido)"
    )
