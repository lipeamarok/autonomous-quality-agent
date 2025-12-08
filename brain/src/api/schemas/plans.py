"""
================================================================================
Schemas: Plans e Versionamento
================================================================================

Modelos para endpoints de gerenciamento de planos e versões.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Plans List
# =============================================================================


class PlanSummary(BaseModel):
    """Resumo de um plano versionado."""

    name: str = Field(..., description="Nome identificador do plano")
    current_version: int = Field(..., description="Número da versão atual")
    total_versions: int = Field(..., description="Total de versões salvas")
    updated_at: str | None = Field(None, description="Data da última atualização")


class PlansListResponse(BaseModel):
    """Resposta da listagem de planos."""

    success: bool = Field(True)
    plans: list[PlanSummary] = Field(default=[], description="Lista de planos")
    total: int = Field(..., description="Total de planos")


# =============================================================================
# Plan Detail
# =============================================================================


class PlanDetailResponse(BaseModel):
    """Resposta com detalhes de um plano/versão."""

    success: bool = Field(True)
    plan_name: str = Field(..., description="Nome do plano")
    version: int = Field(..., description="Número da versão")
    created_at: str = Field(..., description="Data de criação (ISO)")
    source: str = Field(..., description="Origem: 'llm', 'user', 'rollback'")
    description: str | None = Field(None, description="Descrição da versão")
    plan: dict[str, Any] = Field(..., description="Conteúdo do plano UTDL")


# =============================================================================
# Plan Versions
# =============================================================================


class PlanVersionSummary(BaseModel):
    """Resumo de uma versão de plano."""

    version: int = Field(..., description="Número da versão")
    created_at: str | None = Field(None, description="Data de criação")
    source: str = Field(..., description="Origem: 'llm', 'user', 'rollback'")
    description: str | None = Field(None, description="Descrição da versão")
    llm_provider: str | None = Field(None, description="Provider LLM usado")
    llm_model: str | None = Field(None, description="Modelo LLM usado")


class PlanVersionsResponse(BaseModel):
    """Resposta da listagem de versões."""

    success: bool = Field(True)
    plan_name: str = Field(..., description="Nome do plano")
    versions: list[PlanVersionSummary] = Field(
        default=[], description="Lista de versões"
    )
    total: int = Field(..., description="Total de versões")


# =============================================================================
# Plan Diff
# =============================================================================


class PlanDiffChange(BaseModel):
    """Uma mudança específica no diff."""

    id: str = Field(..., description="ID do item modificado")
    field: str = Field(..., description="Campo: 'step', 'config', 'meta'")
    before: Any = Field(None, description="Valor antes")
    after: Any = Field(None, description="Valor depois")


class PlanDiffResponse(BaseModel):
    """Resposta de comparação entre versões."""

    success: bool = Field(True)
    plan_name: str = Field(..., description="Nome do plano")
    version_a: int = Field(..., description="Versão base")
    version_b: int = Field(..., description="Versão comparada")
    has_changes: bool = Field(..., description="Se há diferenças")
    summary: str = Field(..., description="Resumo textual das mudanças")
    steps_added: list[str] = Field(default=[], description="IDs de steps adicionados")
    steps_removed: list[str] = Field(default=[], description="IDs de steps removidos")
    steps_modified: list[PlanDiffChange] = Field(
        default=[], description="Steps modificados"
    )
    config_changes: list[PlanDiffChange] = Field(
        default=[], description="Mudanças de configuração"
    )
    meta_changes: list[PlanDiffChange] = Field(
        default=[], description="Mudanças de metadados"
    )


# =============================================================================
# Plan Restore
# =============================================================================


class PlanRestoreRequest(BaseModel):
    """Request para restaurar versão."""

    description: str | None = Field(
        None,
        description="Descrição opcional para a nova versão",
        examples=["Restaurado da versão 2"],
    )


class PlanRestoreResponse(BaseModel):
    """Resposta de restauração de versão."""

    success: bool = Field(True)
    plan_name: str = Field(..., description="Nome do plano")
    restored_from: int = Field(..., description="Versão de origem")
    new_version: int = Field(..., description="Nova versão criada")
    created_at: str = Field(..., description="Data de criação da nova versão")
