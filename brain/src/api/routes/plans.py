"""
================================================================================
Rota: /plans
================================================================================

Gerenciamento de planos e suas versões.

## Funcionalidades:

- Listar planos versionados
- Obter plano por nome
- Listar versões de um plano
- Obter versão específica
- Comparar versões (diff)
- Restaurar versão anterior (rollback)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_version_store
from ..schemas.plans import (
    PlansListResponse,
    PlanSummary,
    PlanDetailResponse,
    PlanVersionsResponse,
    PlanVersionSummary,
    PlanDiffResponse,
    PlanDiffChange,
    PlanRestoreRequest,
    PlanRestoreResponse,
)
from ...cache import PlanVersionStore, PlanDiff


router = APIRouter()


def _diff_to_response(diff: PlanDiff, plan_name: str) -> PlanDiffResponse:
    """
    Converte PlanDiff para schema de resposta da API.
    """
    # Converte steps modificados para schema
    steps_modified: list[PlanDiffChange] = []
    for change in diff.steps_modified:
        steps_modified.append(PlanDiffChange(
            id=change.get("id", "unknown"),
            field="step",
            before=change.get("before"),
            after=change.get("after"),
        ))

    # Converte config changes
    config_changes: list[PlanDiffChange] = []
    for key, change in diff.config_changes.items():
        config_changes.append(PlanDiffChange(
            id=key,
            field="config",
            before=change.get("before"),
            after=change.get("after"),
        ))

    # Converte meta changes
    meta_changes: list[PlanDiffChange] = []
    for key, change in diff.meta_changes.items():
        meta_changes.append(PlanDiffChange(
            id=key,
            field="meta",
            before=change.get("before"),
            after=change.get("after"),
        ))

    return PlanDiffResponse(
        success=True,
        plan_name=plan_name,
        version_a=diff.version_a,
        version_b=diff.version_b,
        has_changes=diff.has_changes,
        summary=diff.summary,
        steps_added=[s.get("id", "unknown") for s in diff.steps_added],
        steps_removed=[s.get("id", "unknown") for s in diff.steps_removed],
        steps_modified=steps_modified,
        config_changes=config_changes,
        meta_changes=meta_changes,
    )


@router.get(
    "",
    response_model=PlansListResponse,
    summary="Listar Planos Versionados",
    description="""
Lista todos os planos que possuem versões salvas.

Cada plano inclui:
- Nome identificador
- Versão atual
- Total de versões
- Data da última atualização
    """,
)
async def list_plans(
    store: PlanVersionStore = Depends(get_version_store),
) -> PlansListResponse:
    """
    Lista todos os planos versionados.
    """
    plans = store.list_plans()

    return PlansListResponse(
        success=True,
        plans=[
            PlanSummary(
                name=p.get("name", ""),
                current_version=p.get("current_version", 1),
                total_versions=p.get("total_versions", 1),
                updated_at=p.get("updated_at"),
            )
            for p in plans
        ],
        total=len(plans),
    )


@router.get(
    "/{plan_name}",
    response_model=PlanDetailResponse,
    summary="Obter Plano",
    description="Retorna a versão atual (ou especificada) de um plano.",
)
async def get_plan(
    plan_name: str,
    version: int | None = Query(None, description="Versão específica (omita para atual)"),
    store: PlanVersionStore = Depends(get_version_store),
) -> PlanDetailResponse:
    """
    Obtém um plano por nome.
    """
    plan_version = store.get_version(plan_name, version)

    if plan_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E6003",
                "message": f"Plano '{plan_name}' não encontrado"
                + (f" na versão {version}" if version else ""),
            },
        )

    return PlanDetailResponse(
        success=True,
        plan_name=plan_name,
        version=plan_version.version,
        created_at=plan_version.created_at,  # Já é string ISO
        source=plan_version.source,
        description=plan_version.description,
        plan=plan_version.plan,
    )


@router.get(
    "/{plan_name}/versions",
    response_model=PlanVersionsResponse,
    summary="Listar Versões",
    description="Lista todas as versões de um plano específico.",
)
async def list_versions(
    plan_name: str,
    store: PlanVersionStore = Depends(get_version_store),
) -> PlanVersionsResponse:
    """
    Lista todas as versões de um plano.
    """
    versions = store.list_versions(plan_name)

    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E6003",
                "message": f"Plano '{plan_name}' não encontrado",
            },
        )

    return PlanVersionsResponse(
        success=True,
        plan_name=plan_name,
        versions=[
            PlanVersionSummary(
                version=v.get("version", 1),
                created_at=v.get("created_at"),
                source=v.get("source", "unknown"),
                description=v.get("description"),
                llm_provider=v.get("llm_provider"),
                llm_model=v.get("llm_model"),
            )
            for v in versions
        ],
        total=len(versions),
    )


@router.get(
    "/{plan_name}/versions/{version}",
    response_model=PlanDetailResponse,
    summary="Obter Versão Específica",
    description="Retorna uma versão específica de um plano.",
)
async def get_version_endpoint(
    plan_name: str,
    version: int,
    store: PlanVersionStore = Depends(get_version_store),
) -> PlanDetailResponse:
    """
    Obtém uma versão específica de um plano.
    """
    plan_version = store.get_version(plan_name, version)

    if plan_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E6003",
                "message": f"Versão {version} do plano '{plan_name}' não encontrada",
            },
        )

    return PlanDetailResponse(
        success=True,
        plan_name=plan_name,
        version=plan_version.version,
        created_at=plan_version.created_at,  # Já é string ISO
        source=plan_version.source,
        description=plan_version.description,
        plan=plan_version.plan,
    )


@router.get(
    "/{plan_name}/diff",
    response_model=PlanDiffResponse,
    summary="Comparar Versões",
    description="""
Compara duas versões de um plano e retorna as diferenças.

Se `version_b` não for fornecido, compara com a versão atual.
    """,
)
async def diff_versions(
    plan_name: str,
    version_a: int = Query(..., description="Versão base (mais antiga)"),
    version_b: int | None = Query(None, description="Versão a comparar (omita para atual)"),
    store: PlanVersionStore = Depends(get_version_store),
) -> PlanDiffResponse:
    """
    Compara duas versões de um plano.
    """
    diff = store.diff(plan_name, version_a, version_b)

    if diff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E6003",
                "message": f"Não foi possível comparar versões do plano '{plan_name}'",
            },
        )

    return _diff_to_response(diff, plan_name)


@router.post(
    "/{plan_name}/versions/{version}/restore",
    response_model=PlanRestoreResponse,
    summary="Restaurar Versão",
    description="""
Restaura uma versão anterior de um plano.

Isso cria uma nova versão com o conteúdo da versão especificada.
    """,
)
async def restore_version(
    plan_name: str,
    version: int,
    request: PlanRestoreRequest | None = None,
    store: PlanVersionStore = Depends(get_version_store),
) -> PlanRestoreResponse:
    """
    Restaura uma versão anterior de um plano.
    """
    description = request.description if request and request.description else ""

    new_version = store.rollback(plan_name, version, description)

    if new_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E6003",
                "message": f"Não foi possível restaurar versão {version} do plano '{plan_name}'",
            },
        )

    return PlanRestoreResponse(
        success=True,
        plan_name=plan_name,
        restored_from=version,
        new_version=new_version.version,
        created_at=new_version.created_at,  # Já é string ISO
    )
