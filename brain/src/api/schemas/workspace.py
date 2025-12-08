"""
================================================================================
Schemas para /workspace
================================================================================

Request e Response para gerenciamento de workspace.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkspaceInitRequest(BaseModel):
    """
    Request para inicializar workspace.

    ## Exemplo:

        {
            "path": "./my-project",
            "force": false
        }
    """

    path: str | None = Field(
        None,
        description="Caminho onde criar o workspace. Se None, usa diretório atual."
    )
    force: bool = Field(
        False,
        description="Sobrescrever se já existir"
    )


class WorkspaceInitResponse(BaseModel):
    """
    Response da inicialização de workspace.

    ## Exemplo:

        {
            "success": true,
            "workspace_path": "/home/user/project/.aqa",
            "created_files": [
                ".aqa/config.yaml",
                ".aqa/plans/",
                ".aqa/reports/"
            ]
        }
    """

    success: bool = Field(True)
    workspace_path: str = Field(..., description="Caminho absoluto do workspace criado")
    created_files: list[str] = Field(
        ...,
        description="Arquivos e diretórios criados"
    )
    already_existed: bool = Field(
        False,
        description="Se o workspace já existia"
    )


class WorkspaceStatusResponse(BaseModel):
    """
    Status do workspace atual.
    """

    success: bool = Field(True)
    initialized: bool = Field(..., description="Se existe um workspace válido")
    workspace_path: str | None = Field(None, description="Caminho do workspace, se existir")
    plans_count: int = Field(0, description="Número de planos salvos")
    history_count: int = Field(0, description="Número de execuções no histórico")
    config: dict[str, Any] | None = Field(None, description="Configuração do workspace")
