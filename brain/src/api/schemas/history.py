"""
================================================================================
Schemas para /history
================================================================================

Request e Response para histórico de execuções.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HistoryRecordSchema(BaseModel):
    """
    Registro de uma execução no histórico.
    """

    id: str = Field(..., description="ID único da execução")
    timestamp: str = Field(..., description="Data/hora da execução (ISO 8601)")
    plan_file: str = Field(..., description="Arquivo de plano usado")
    plan_name: str | None = Field(None, description="Nome do plano")
    status: Literal["success", "failure", "error"] = Field(
        ...,
        description="Status geral da execução"
    )
    duration_ms: int = Field(..., description="Duração em milissegundos")
    total_steps: int = Field(..., description="Total de steps")
    passed_steps: int = Field(..., description="Steps que passaram")
    failed_steps: int = Field(..., description="Steps que falharam")
    tags: list[str] = Field(default_factory=list, description="Tags do plano")


class HistoryDetailSchema(HistoryRecordSchema):
    """
    Registro detalhado com relatório completo.
    """

    runner_report: dict[str, Any] | None = Field(
        None,
        description="Relatório completo do Runner"
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Metadados adicionais"
    )


class HistoryFilterParams(BaseModel):
    """
    Parâmetros de filtro para listagem de histórico.
    """

    status: Literal["success", "failure", "error"] | None = Field(
        None,
        description="Filtrar por status"
    )
    plan_name: str | None = Field(
        None,
        description="Filtrar por nome do plano (contains)"
    )
    from_date: datetime | None = Field(
        None,
        description="Data inicial (ISO 8601)"
    )
    to_date: datetime | None = Field(
        None,
        description="Data final (ISO 8601)"
    )
    tags: list[str] | None = Field(
        None,
        description="Filtrar por tags (any match)"
    )
    page: int = Field(1, ge=1, description="Página (1-indexed)")
    limit: int = Field(20, ge=1, le=100, description="Itens por página")


class HistoryListResponse(BaseModel):
    """
    Response da listagem de histórico.

    ## Exemplo:

        {
            "success": true,
            "records": [...],
            "total": 50,
            "page": 1,
            "limit": 20,
            "pages": 3
        }
    """

    success: bool = Field(True)
    records: list[HistoryRecordSchema] = Field(..., description="Lista de execuções")
    total: int = Field(..., description="Total de registros")
    page: int = Field(..., description="Página atual")
    limit: int = Field(..., description="Itens por página")
    pages: int = Field(..., description="Total de páginas")


class HistoryStatsResponse(BaseModel):
    """
    Estatísticas agregadas do histórico.
    """

    success: bool = Field(True)
    total_executions: int = Field(..., description="Total de execuções")
    success_count: int = Field(..., description="Execuções bem-sucedidas")
    failure_count: int = Field(..., description="Execuções com falhas")
    error_count: int = Field(..., description="Execuções com erro")
    success_rate: float = Field(..., description="Taxa de sucesso (%)")
    avg_duration_ms: float = Field(..., description="Duração média (ms)")
    total_steps_executed: int = Field(..., description="Total de steps executados")
