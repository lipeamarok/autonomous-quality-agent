"""
================================================================================
API Telemetry Middleware
================================================================================

Instrumentação OTEL para endpoints da API REST.

## Spans criados:

- `http.request` - Span principal do request
- `http.{method}.{path}` - Span específico do endpoint
- Propagação de trace context via headers

## Configuração:

```bash
AQA_TELEMETRY_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```
"""

from __future__ import annotations

import time
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..telemetry.tracer import (
    TelemetryConfig,
    Tracer,
    SpanContext,
)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    Middleware para instrumentação OTEL de requests HTTP.

    ## Atributos registrados:

    - http.method
    - http.url
    - http.route
    - http.status_code
    - http.request_id
    - http.user_agent
    - http.duration_ms
    """

    def __init__(self, app: Any, tracer: Tracer | None = None) -> None:
        super().__init__(app)
        self.config = TelemetryConfig()
        self.tracer = tracer if tracer is not None else Tracer()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        """Processa request com instrumentação."""
        if not self.config.enabled:
            return await call_next(request)

        # Extrai trace context do header se existir
        traceparent = request.headers.get("traceparent")
        parent_context = None
        if traceparent:
            parent_context = SpanContext.from_traceparent(traceparent)

        # Cria span para o request
        span_name = f"http.{request.method.lower()}"
        route = request.scope.get("route")
        if route:
            span_name = f"{span_name}.{route.path}"

        start_time = time.time()

        with self.tracer.span(span_name, parent=parent_context) as span:
            # Atributos do request
            span.set_attributes({
                "http.method": request.method,
                "http.url": str(request.url),
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname or "",
                "http.target": request.url.path,
                "http.user_agent": request.headers.get("user-agent", ""),
                "http.request_id": getattr(request.state, "request_id", ""),
            })

            try:
                response = await call_next(request)

                # Atributos da response
                duration_ms = (time.time() - start_time) * 1000
                span.set_attributes({
                    "http.status_code": response.status_code,
                    "http.duration_ms": round(duration_ms, 2),
                })

                # Status do span baseado no status code
                if response.status_code >= 500:
                    span.set_status("error", f"HTTP {response.status_code}")
                elif response.status_code >= 400:
                    span.set_status("error", f"Client error {response.status_code}")
                else:
                    span.set_status("ok")

                # Adiciona trace headers na response
                if span.context:
                    response.headers["traceparent"] = span.context.to_traceparent()

                return response

            except Exception as e:
                span.record_exception(e)
                raise


def get_telemetry_middleware(tracer: Tracer | None = None) -> type[TelemetryMiddleware]:
    """Factory para criar middleware com tracer configurado."""

    class ConfiguredTelemetryMiddleware(TelemetryMiddleware):
        def __init__(self, app: Any) -> None:
            super().__init__(app, tracer)

    return ConfiguredTelemetryMiddleware
