"""
================================================================================
FastAPI Application Factory
================================================================================

Cria e configura a aplicação FastAPI do AQA.

## Uso:

```python
from src.api import create_app

app = create_app()
```

## Via CLI:

```bash
aqa serve --port 8000 --reload
```
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, status, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import APIConfig
from .routes import create_api_router
from .websocket import ExecutionStreamManager, websocket_execute


# Versão do AQA (sincronizada com pyproject.toml)
AQA_VERSION = "0.5.0"


# Manager global para WebSocket connections
ws_manager = ExecutionStreamManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerencia ciclo de vida da aplicação.

    - Startup: Inicializa recursos (conexões, caches)
    - Shutdown: Libera recursos de forma limpa
    """
    # Startup
    app.state.ws_manager = ws_manager
    app.state.start_time = datetime.now(timezone.utc)

    yield

    # Shutdown
    await ws_manager.disconnect_all()


def create_app(config: APIConfig | None = None) -> FastAPI:
    """
    Cria e configura a aplicação FastAPI.

    ## Parâmetros:

    - `config`: Configuração da API. Se None, usa valores de ambiente.

    ## Retorna:

    Aplicação FastAPI configurada com:
    - CORS habilitado
    - Middleware de erros
    - Rotas registradas
    - Documentação OpenAPI

    ## Exemplo:

        >>> app = create_app()
        >>> # ou com config customizada
        >>> app = create_app(APIConfig(port=3000, debug=True))
    """
    if config is None:
        config = APIConfig.from_env()

    # Cria app FastAPI
    app = FastAPI(
        title="Autonomous Quality Agent API",
        description="""
## 🧪 AQA — Autonomous Quality Agent

API REST para geração e execução de testes de API usando IA.

### Funcionalidades:

- **Generate**: Gerar planos de teste UTDL a partir de requisitos ou OpenAPI specs
- **Validate**: Validar estrutura de planos UTDL
- **Execute**: Executar planos via Runner de alta performance (Rust)
- **History**: Consultar histórico de execuções
- **WebSocket**: Streaming em tempo real de execuções

### Links úteis:

- [Documentação](https://github.com/lipeamarok/autonomous-quality-agent)
- [GitHub](https://github.com/lipeamarok/autonomous-quality-agent)
        """,
        version=AQA_VERSION,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url="/redoc" if config.docs_enabled else None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
        lifespan=lifespan,
    )

    # Armazena config no state
    app.state.config = config

    # Configura CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware para adicionar request_id
    # Nota: Funções decoradas são registradas pelo FastAPI, não acessadas diretamente
    @app.middleware("http")
    async def add_request_id(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        call_next: Any
    ) -> Any:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Handler de erros de validação Pydantic
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "E1009",
                    "message": "Erro de validação nos dados enviados",
                    "details": exc.errors(),
                },
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # Handler de erros genéricos
    @app.exception_handler(Exception)
    async def generic_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        # Em modo debug, mostra detalhes do erro
        if config.debug:
            error_detail = str(exc)
        else:
            error_detail = "Erro interno do servidor"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "E5001",
                    "message": error_detail,
                },
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # Registra rotas
    api_router = create_api_router()
    app.include_router(api_router, prefix=config.api_prefix)

    # Rota de health check na raiz (sem prefixo)
    @app.get("/health", tags=["Health"])
    async def root_health() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """Health check na raiz."""
        return {
            "status": "healthy",
            "version": AQA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # WebSocket para streaming de execução
    @app.websocket("/ws/execute")
    async def ws_execute_endpoint(  # pyright: ignore[reportUnusedFunction]
        websocket: WebSocket
    ) -> None:
        """
        WebSocket para execução de planos com streaming em tempo real.

        ## Protocolo:

        1. Cliente conecta
        2. Cliente envia: {"action": "execute", "plan": {...}}
        3. Servidor envia eventos: step_started, step_completed, progress
        4. Servidor envia: execution_completed com resultado final
        """
        await websocket_execute(websocket, ws_manager)

    return app


def get_app() -> FastAPI:
    """
    Retorna instância da app para uso com uvicorn.

    ## Uso com uvicorn:

    ```bash
    uvicorn src.api.app:get_app --factory --reload
    ```
    """
    return create_app()
