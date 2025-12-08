"""
================================================================================
Rotas da API
================================================================================

Este módulo agrupa todas as rotas da API.
"""

from fastapi import APIRouter, Depends

from .auth import router as auth_router
from .health import router as health_router
from .generate import router as generate_router
from .validate import router as validate_router
from .execute import router as execute_router
from .history import router as history_router
from .workspace import router as workspace_router
from .plans import router as plans_router
from .metrics import router as metrics_router
from ..auth import require_api_key


def create_api_router() -> APIRouter:
    """
    Cria e configura o router principal da API.

    ## Rotas registradas:

    - /health - Health check (público)
    - /auth - Autenticação e gerenciamento de keys
    - /generate - Geração de planos (protegido)
    - /validate - Validação de planos (protegido)
    - /execute - Execução de planos (protegido)
    - /history - Histórico de execuções (protegido)
    - /workspace - Gerenciamento de workspace (protegido)
    - /plans - Gerenciamento de planos e versões (protegido)

    ## Autenticação:

    Quando AQA_AUTH_MODE=apikey, endpoints protegidos requerem
    header X-API-Key com uma key válida.
    """
    router = APIRouter()

    # Rotas públicas (sem autenticação)
    router.include_router(health_router, tags=["Health"])
    router.include_router(auth_router, prefix="/auth", tags=["Auth"])

    # Rotas protegidas (requerem API key quando auth está habilitada)
    # A dependency require_api_key verifica o modo de auth automaticamente
    protected_deps = [Depends(require_api_key)]

    router.include_router(
        generate_router,
        prefix="/generate",
        tags=["Generate"],
        dependencies=protected_deps,
    )
    router.include_router(
        validate_router,
        prefix="/validate",
        tags=["Validate"],
        dependencies=protected_deps,
    )
    router.include_router(
        execute_router,
        prefix="/execute",
        tags=["Execute"],
        dependencies=protected_deps,
    )
    router.include_router(
        history_router,
        prefix="/history",
        tags=["History"],
        dependencies=protected_deps,
    )
    router.include_router(
        workspace_router,
        prefix="/workspace",
        tags=["Workspace"],
        dependencies=protected_deps,
    )
    router.include_router(
        plans_router,
        prefix="/plans",
        tags=["Plans"],
        dependencies=protected_deps,
    )

    # Metrics (público para scraping)
    router.include_router(
        metrics_router,
        prefix="/metrics",
        tags=["Metrics"],
    )

    return router


__all__ = ["create_api_router"]
