"""
================================================================================
Rota: /metrics
================================================================================

Endpoint para exposição de métricas no formato Prometheus.

## Uso:

```bash
curl http://localhost:8000/metrics
```

## Métricas expostas:

- `aqa_http_requests_total` - Total de requests HTTP
- `aqa_http_request_duration_seconds` - Duração dos requests
- `aqa_generation_total` - Planos gerados
- `aqa_execution_total` - Execuções de planos
- `aqa_cache_hits_total` - Cache hits
- `aqa_cache_misses_total` - Cache misses
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from ...telemetry.metrics import Metrics


router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================


class MetricsResponse(BaseModel):
    """Response com métricas em JSON."""

    success: bool = Field(True)
    metrics: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get(
    "",
    summary="Prometheus Metrics",
    description="""
Retorna métricas no formato Prometheus.

Use este endpoint para integração com:
- Prometheus
- Grafana
- DataDog
- New Relic
    """,
    response_class=Response,
    responses={
        200: {
            "description": "Métricas em formato Prometheus",
            "content": {"text/plain": {}},
        },
    },
)
async def get_metrics() -> Response:
    """Retorna métricas no formato Prometheus."""
    metrics_text = Metrics.to_prometheus()

    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get(
    "/json",
    response_model=MetricsResponse,
    summary="Métricas em JSON",
    description="Retorna métricas em formato JSON para debug.",
)
async def get_metrics_json() -> MetricsResponse:
    """Retorna métricas em formato JSON."""
    from ...telemetry.metrics import Counter, Gauge

    metrics_dict: dict[str, Any] = {}

    for metric in Metrics.all_metrics():
        if isinstance(metric, (Counter, Gauge)):
            metrics_dict[metric.name] = metric.get()
        else:
            # Histogram
            metrics_dict[metric.name] = metric.get_stats()

    return MetricsResponse(
        success=True,
        metrics=metrics_dict,
        timestamp=time.time(),
    )
