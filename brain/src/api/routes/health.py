"""
================================================================================
Rota: /health
================================================================================

Health check e status da API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from ..schemas.common import HealthResponse


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Verifica se a API está funcionando e retorna informações de status.",
)
async def health_check(request: Request) -> HealthResponse:
    """
    Retorna status de saúde da API.

    ## Resposta:

    - `status`: "healthy" se tudo OK
    - `version`: Versão do AQA
    - `timestamp`: Hora atual
    - `components`: Status de componentes internos
    """
    from ..app import AQA_VERSION

    # Verifica componentes
    components: dict[str, str] = {}

    # Verifica se Runner está acessível
    try:
        from pathlib import Path
        # Procura runner em locais conhecidos
        project_root = Path(__file__).parent.parent.parent.parent.parent
        release_path = project_root / "runner" / "target" / "release" / "runner.exe"
        debug_path = project_root / "runner" / "target" / "debug" / "runner.exe"

        if release_path.exists() or debug_path.exists():
            components["runner"] = "available"
        else:
            components["runner"] = "not_found"
    except Exception:
        components["runner"] = "error"

    # Verifica LLM provider
    try:
        import os
        # Verifica se há API key configurada
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_xai = bool(os.environ.get("XAI_API_KEY"))

        if has_openai or has_xai:
            components["llm"] = "configured"
        else:
            components["llm"] = "mock_only"
    except Exception:
        components["llm"] = "error"

    # Verifica storage
    try:
        from ...config import BrainConfig
        config = BrainConfig.from_env()
        history = config.get_history()
        if history:
            components["storage"] = "available"
        else:
            components["storage"] = "not_configured"
    except Exception:
        components["storage"] = "error"

    return HealthResponse(
        status="healthy",
        version=AQA_VERSION,
        timestamp=datetime.now(timezone.utc),
        components=components,
    )


@router.get(
    "/",
    summary="API Info",
    description="Informações básicas sobre a API.",
)
async def api_info() -> dict[str, Any]:
    """
    Retorna informações básicas sobre a API.
    """
    from ..app import AQA_VERSION

    return {
        "name": "Autonomous Quality Agent API",
        "version": AQA_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
