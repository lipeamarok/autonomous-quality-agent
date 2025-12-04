"""
================================================================================
AQA Telemetry — Observabilidade com OpenTelemetry
================================================================================

Este módulo fornece instrumentação OTEL para o Brain, incluindo:
- Tracing distribuído (spans)
- Métricas de geração
- Correlação com o Runner

## Arquitetura:

```
Brain (Python)                         Runner (Rust)
    │                                      │
    ├── trace_id: abc123 ──────────────────┤
    │                                      │
    ▼                                      ▼
[LLM Generation Span]               [Execution Span]
    │                                      │
    ├── cache_lookup                       ├── step_1
    ├── llm_call                          ├── step_2
    └── validation                        └── step_n
```

## Uso:

```python
from src.telemetry import Tracer, Metrics

# Inicializa (configura exporters)
tracer = Tracer.init(service_name="aqa-brain")

# Cria spans
with tracer.span("generate_plan") as span:
    span.set_attribute("swagger_file", "api.yaml")
    plan = generate_plan(swagger)
    span.set_attribute("steps_count", len(plan.steps))

# Registra métricas
Metrics.generation_time.record(elapsed_seconds)
Metrics.cache_hits.add(1)
```

## Exporters Suportados:

- OTLP (gRPC/HTTP) → Jaeger, Grafana Tempo, etc.
- Console (desenvolvimento)
- Noop (desativado)
"""

from .tracer import (
    Tracer,
    SpanContext,
    get_tracer,
    init_telemetry,
    shutdown_telemetry,
    trace_span,
    inject_context,
    extract_context,
)

from .metrics import (
    Metrics,
    init_metrics,
    record_generation_time,
    record_cache_hit,
    record_cache_miss,
    record_validation_error,
    record_llm_tokens,
)

__all__ = [
    # Tracer
    "Tracer",
    "SpanContext",
    "get_tracer",
    "init_telemetry",
    "shutdown_telemetry",
    "trace_span",
    "inject_context",
    "extract_context",
    # Metrics
    "Metrics",
    "init_metrics",
    "record_generation_time",
    "record_cache_hit",
    "record_cache_miss",
    "record_validation_error",
    "record_llm_tokens",
]
