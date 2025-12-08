"""
================================================================================
Rate Limiting
================================================================================

Middleware e utilitários para rate limiting da API.

## Configuração via Ambiente:

- AQA_RATE_LIMIT_ENABLED: Habilitar rate limiting (default: true)
- AQA_RATE_LIMIT_REQUESTS: Número de requests permitidos (default: 100)
- AQA_RATE_LIMIT_WINDOW: Janela de tempo em segundos (default: 60)
- AQA_RATE_LIMIT_BY: Critério de limitação: ip, api_key (default: ip)

## Exemplo de uso:

```python
from src.api.rate_limit import get_rate_limiter, rate_limit_exceeded_handler

app = FastAPI()
limiter = get_rate_limiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```
"""

from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter  # type: ignore[import-untyped]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-untyped]
from slowapi.util import get_remote_address  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Awaitable


# =============================================================================
# CONFIGURATION
# =============================================================================


class RateLimitBy(str, Enum):
    """Critério para rate limiting."""

    IP = "ip"
    API_KEY = "api_key"


class RateLimitConfig(BaseModel):
    """Configuração de rate limiting."""

    enabled: bool = Field(default=True, description="Se rate limiting está habilitado")
    requests: int = Field(default=100, description="Número de requests permitidos")
    window: int = Field(default=60, description="Janela de tempo em segundos")
    limit_by: RateLimitBy = Field(
        default=RateLimitBy.IP,
        description="Critério de limitação",
    )

    @property
    def rate_string(self) -> str:
        """Retorna string no formato SlowAPI (ex: '100/minute')."""
        if self.window == 60:
            return f"{self.requests}/minute"
        elif self.window == 3600:
            return f"{self.requests}/hour"
        elif self.window == 86400:
            return f"{self.requests}/day"
        else:
            return f"{self.requests}/{self.window}seconds"


def get_rate_limit_config() -> RateLimitConfig:
    """Obtém configuração de rate limiting do ambiente."""
    enabled_str = os.getenv("AQA_RATE_LIMIT_ENABLED", "true").lower()
    enabled = enabled_str in ("true", "1", "yes", "on")

    requests = int(os.getenv("AQA_RATE_LIMIT_REQUESTS", "100"))
    window = int(os.getenv("AQA_RATE_LIMIT_WINDOW", "60"))
    limit_by_str = os.getenv("AQA_RATE_LIMIT_BY", "ip").lower()

    try:
        limit_by = RateLimitBy(limit_by_str)
    except ValueError:
        limit_by = RateLimitBy.IP

    return RateLimitConfig(
        enabled=enabled,
        requests=requests,
        window=window,
        limit_by=limit_by,
    )


# =============================================================================
# KEY FUNCTIONS
# =============================================================================


def get_key_from_request(request: Request) -> str:
    """
    Obtém a chave de identificação para rate limiting.

    Ordem de prioridade:
    1. API Key (se presente no header)
    2. IP address
    """
    # Tenta obter API key do header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Usa apenas o prefixo da key para anonimizar
        return f"key:{api_key[:12]}"

    # Fallback para IP
    return get_remote_address(request)


def get_key_by_config(request: Request) -> str:
    """Obtém chave baseado na configuração."""
    config = get_rate_limit_config()

    if config.limit_by == RateLimitBy.API_KEY:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key[:12]}"

    return get_remote_address(request)


# =============================================================================
# LIMITER INSTANCE
# =============================================================================

# Instância global do limiter
_limiter: Limiter | None = None


def get_rate_limiter() -> Limiter:
    """Obtém instância do rate limiter."""
    global _limiter

    if _limiter is None:
        config = get_rate_limit_config()

        if config.limit_by == RateLimitBy.API_KEY:
            key_func = get_key_from_request
        else:
            key_func = get_remote_address

        _limiter = Limiter(
            key_func=key_func,
            default_limits=[config.rate_string] if config.enabled else [],
            enabled=config.enabled,
        )

    return _limiter


def reset_rate_limiter() -> None:
    """Reseta o limiter (útil para testes)."""
    global _limiter
    _limiter = None


# =============================================================================
# EXCEPTION HANDLER
# =============================================================================


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> Response:
    """Handler para quando o rate limit é excedido."""
    config = get_rate_limit_config()

    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": {
                "code": "E4029",
                "message": "Rate limit exceeded",
                "detail": f"Too many requests. Limit: {config.requests} per {config.window}s",
                "retry_after": config.window,
            },
        },
        headers={
            "Retry-After": str(config.window),
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Window": str(config.window),
        },
    )


# =============================================================================
# DECORATORS
# =============================================================================


def rate_limit(
    limit: str | None = None,
) -> Any:
    """
    Decorator para aplicar rate limit a um endpoint específico.

    ## Uso:

    ```python
    @router.post("/generate")
    @rate_limit("10/minute")
    async def generate(...):
        ...
    ```

    ## Parâmetros:

    - limit: String no formato "N/period" (ex: "10/minute", "100/hour")
             Se None, usa o limite padrão da configuração.
    """
    limiter = get_rate_limiter()

    if limit:
        return limiter.limit(limit)  # type: ignore[no-any-return]
    else:
        config = get_rate_limit_config()
        return limiter.limit(config.rate_string)  # type: ignore[no-any-return]


# =============================================================================
# MIDDLEWARE
# =============================================================================


class RateLimitMiddleware:
    """
    Middleware para adicionar headers de rate limit às respostas.

    Adiciona os headers:
    - X-RateLimit-Limit: Número máximo de requests
    - X-RateLimit-Remaining: Requests restantes
    - X-RateLimit-Reset: Timestamp de reset
    """

    def __init__(self, app: Callable[..., Awaitable[Response]]) -> None:
        self.app = app
        self.config = get_rate_limit_config()

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Processa a request e adiciona headers."""
        response = await call_next(request)

        if self.config.enabled:
            response.headers["X-RateLimit-Limit"] = str(self.config.requests)
            response.headers["X-RateLimit-Window"] = f"{self.config.window}s"

        return response
