"""
================================================================================
Rotas da API
================================================================================

Este módulo agrupa todas as rotas da API.
"""

from fastapi import APIRouter

from .health import router as health_router
from .generate import router as generate_router
from .validate import router as validate_router
from .execute import router as execute_router
from .history import router as history_router
from .workspace import router as workspace_router
from .plans import router as plans_router


def create_api_router() -> APIRouter:
    """
    Cria e configura o router principal da API.

    ## Rotas registradas:

    - /health - Health check
    - /generate - Geração de planos
    - /validate - Validação de planos
    - /execute - Execução de planos
    - /history - Histórico de execuções
    - /workspace - Gerenciamento de workspace
    - /plans - Gerenciamento de planos e versões
    """
    router = APIRouter()

    # Rotas sem prefixo (raiz)
    router.include_router(health_router, tags=["Health"])

    # Rotas com prefixo /api/v1
    router.include_router(generate_router, prefix="/generate", tags=["Generate"])
    router.include_router(validate_router, prefix="/validate", tags=["Validate"])
    router.include_router(execute_router, prefix="/execute", tags=["Execute"])
    router.include_router(history_router, prefix="/history", tags=["History"])
    router.include_router(workspace_router, prefix="/workspace", tags=["Workspace"])
    router.include_router(plans_router, prefix="/plans", tags=["Plans"])

    return router


__all__ = ["create_api_router"]
