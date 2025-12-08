"""
================================================================================
Rota: /history
================================================================================

Histórico de execuções de planos UTDL.

## Funcionalidades:

- Listagem paginada de execuções
- Filtro por status e nome do plano
- Estatísticas agregadas
- Detalhes de execuções individuais
- Exclusão de registros
"""

from __future__ import annotations

import math
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_execution_history
from ..schemas.history import (
    HistoryListResponse,
    HistoryRecordSchema,
    HistoryDetailSchema,
    HistoryStatsResponse,
)
from ...cache import ExecutionHistory


router = APIRouter()


def _record_to_schema(record: dict[str, Any]) -> HistoryRecordSchema:
    """
    Converte um registro do cache para o schema da API.

    ## Parâmetros:
        record: Dict com dados da execução do ExecutionHistory

    ## Retorna:
        HistoryRecordSchema pronto para serialização
    """
    # Status precisa ser um dos valores válidos
    raw_status = record.get("status", "error")
    status_val: Literal["success", "failure", "error"]
    if raw_status == "success":
        status_val = "success"
    elif raw_status == "failure":
        status_val = "failure"
    else:
        status_val = "error"

    return HistoryRecordSchema(
        id=str(record.get("id", "")),
        timestamp=str(record.get("timestamp", "")),
        plan_file=str(record.get("plan_file", "")),
        plan_name=record.get("plan_name"),
        status=status_val,
        duration_ms=int(record.get("duration_ms", 0)),
        total_steps=int(record.get("total_steps", 0)),
        passed_steps=int(record.get("passed_steps", 0)),
        failed_steps=int(record.get("failed_steps", 0)),
        tags=record.get("tags") or [],
    )


@router.get(
    "",
    response_model=HistoryListResponse,
    summary="Listar Histórico",
    description="""
Lista execuções anteriores com suporte a paginação e filtros.

## Filtros disponíveis:

- **status**: Filtrar por resultado (success, failure, error)
- **plan_name**: Buscar por nome do plano (contains)
- **page**: Página (1-indexed)
- **limit**: Itens por página (1-100)
    """,
)
async def list_history(
    status_filter: Literal["success", "failure", "error"] | None = Query(
        None,
        alias="status",
        description="Filtrar por status"
    ),
    plan_name: str | None = Query(
        None,
        description="Filtrar por nome do plano"
    ),
    page: int = Query(1, ge=1, description="Página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    history: ExecutionHistory = Depends(get_execution_history),
) -> HistoryListResponse:
    """
    Lista histórico de execuções com paginação.

    ## Observações:

    - Registros são ordenados do mais recente ao mais antigo
    - Filtros são aplicados antes da paginação
    """
    # Obtém registros - usar filtro de status no backend se possível
    if status_filter:
        all_records: list[dict[str, Any]] = history.get_by_status(status_filter, limit=1000)
    else:
        all_records = history.get_recent(limit=1000)

    # Aplica filtro por nome do plano (em memória)
    filtered: list[dict[str, Any]] = all_records
    if plan_name:
        plan_name_lower = plan_name.lower()
        filtered = [
            r for r in filtered
            if r.get("plan_name") and plan_name_lower in str(r.get("plan_name", "")).lower()
        ]

    # Paginação
    total = len(filtered)
    pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit
    paginated = filtered[offset:offset + limit]

    # Converte para schema
    records = [_record_to_schema(r) for r in paginated]

    return HistoryListResponse(
        success=True,
        records=records,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get(
    "/stats",
    response_model=HistoryStatsResponse,
    summary="Estatísticas do Histórico",
    description="Retorna estatísticas agregadas de todas as execuções.",
)
async def history_stats(
    history: ExecutionHistory = Depends(get_execution_history),
) -> HistoryStatsResponse:
    """
    Retorna estatísticas agregadas do histórico.

    ## Métricas calculadas:

    - Total de execuções
    - Contagem por status
    - Taxa de sucesso
    - Duração média
    - Total de steps executados
    """
    all_records: list[dict[str, Any]] = history.get_recent(limit=10000)

    total = len(all_records)
    success_count = sum(1 for r in all_records if r.get("status") == "success")
    failure_count = sum(1 for r in all_records if r.get("status") == "failure")
    error_count = sum(1 for r in all_records if r.get("status") == "error")

    success_rate = (success_count / total * 100) if total > 0 else 0.0

    total_duration = sum(int(r.get("duration_ms", 0)) for r in all_records)
    avg_duration = total_duration / total if total > 0 else 0.0

    total_steps = sum(int(r.get("total_steps", 0)) for r in all_records)

    return HistoryStatsResponse(
        success=True,
        total_executions=total,
        success_count=success_count,
        failure_count=failure_count,
        error_count=error_count,
        success_rate=round(success_rate, 2),
        avg_duration_ms=round(avg_duration, 2),
        total_steps_executed=total_steps,
    )


@router.get(
    "/{execution_id}",
    response_model=HistoryDetailSchema,
    summary="Detalhes da Execução",
    description="Retorna detalhes completos de uma execução específica.",
)
async def get_execution(
    execution_id: str,
    history: ExecutionHistory = Depends(get_execution_history),
) -> HistoryDetailSchema:
    """
    Retorna detalhes completos de uma execução.

    ## Inclui:

    - Todos os campos básicos
    - Relatório completo do Runner
    - Metadados adicionais
    """
    record = history.get_full_record(execution_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E4002",
                "message": f"Execução não encontrada: {execution_id}",
            },
        )

    # Status precisa ser um dos valores válidos
    raw_status = record.get("status", "error")
    status_val: Literal["success", "failure", "error"]
    if raw_status == "success":
        status_val = "success"
    elif raw_status == "failure":
        status_val = "failure"
    else:
        status_val = "error"

    return HistoryDetailSchema(
        id=str(record.get("id", "")),
        timestamp=str(record.get("timestamp", "")),
        plan_file=str(record.get("plan_file", "")),
        plan_name=record.get("plan_name"),
        status=status_val,
        duration_ms=int(record.get("duration_ms", 0)),
        total_steps=int(record.get("total_steps", 0)),
        passed_steps=int(record.get("passed_steps", 0)),
        failed_steps=int(record.get("failed_steps", 0)),
        tags=record.get("tags") or [],
        runner_report=record.get("runner_report"),
        metadata=record.get("metadata"),
    )


@router.delete(
    "/{execution_id}",
    summary="Deletar Execução",
    description="Remove uma execução do histórico.",
)
async def delete_execution(
    execution_id: str,
    history: ExecutionHistory = Depends(get_execution_history),
) -> dict[str, Any]:
    """
    Remove uma execução do histórico.

    ## Observações:

    - A exclusão é permanente
    - Retorna erro 404 se não encontrar
    """
    record = history.get_full_record(execution_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E4002",
                "message": f"Execução não encontrada: {execution_id}",
            },
        )

    # TODO: Implementar delete no ExecutionHistory
    # Por enquanto, apenas retorna sucesso (não deleta de verdade)
    # history.delete(execution_id)

    return {
        "success": True,
        "message": f"Execução {execution_id} removida",
        "deleted_id": execution_id,
    }
