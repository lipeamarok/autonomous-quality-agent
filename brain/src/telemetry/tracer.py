"""
================================================================================
Tracer — Tracing Distribuído com OpenTelemetry
================================================================================

Este módulo implementa tracing distribuído para o AQA Brain.

## Para todos entenderem:

Tracing é como um "rastreador de pacotes" para código. Cada operação
importante cria um "span" (segmento) que registra:
- Quando começou e terminou
- Atributos (metadados)
- Status (sucesso/erro)
- Relacionamento com outros spans (parent/child)

## Configuração via Environment:

```bash
# Ativar telemetria
export AQA_TELEMETRY_ENABLED=true

# Endpoint OTLP (Jaeger, Tempo, etc.)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Nome do serviço
export OTEL_SERVICE_NAME=aqa-brain

# Modo console (desenvolvimento)
export AQA_TELEMETRY_CONSOLE=true
```

## Spans do Brain:

```
aqa.generate_plan (root)
├── aqa.cache.lookup
├── aqa.swagger.parse
├── aqa.llm.call
│   ├── aqa.llm.prompt_build
│   └── aqa.llm.api_call
├── aqa.validation
└── aqa.cache.store
```
"""

from __future__ import annotations

import os
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Callable, TypeVar
from functools import wraps
import time
import uuid

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================


@dataclass
class TelemetryConfig:
    """Configuração de telemetria via environment."""

    enabled: bool = field(default_factory=lambda: os.getenv("AQA_TELEMETRY_ENABLED", "").lower() == "true")
    console_export: bool = field(default_factory=lambda: os.getenv("AQA_TELEMETRY_CONSOLE", "").lower() == "true")
    otlp_endpoint: str | None = field(default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
    service_name: str = field(default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "aqa-brain"))
    service_version: str = field(default_factory=lambda: os.getenv("OTEL_SERVICE_VERSION", "0.3.0"))


# Global config
_config = TelemetryConfig()


# =============================================================================
# SPAN CONTEXT
# =============================================================================


@dataclass
class SpanContext:
    """
    Contexto de um span para propagação entre serviços.

    ## Para todos entenderem:
    Quando o Brain gera um plano e passa para o Runner executar,
    precisamos passar o trace_id para que os spans do Runner
    apareçam como "filhos" do span do Brain.

    ## Formato W3C Trace Context:
    - traceparent: 00-<trace_id>-<span_id>-<flags>
    - tracestate: vendor=value (opcional)
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    sampled: bool = True

    def to_traceparent(self) -> str:
        """Converte para formato W3C traceparent."""
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    @classmethod
    def from_traceparent(cls, header: str) -> SpanContext | None:
        """Parse de W3C traceparent header."""
        try:
            parts = header.split("-")
            if len(parts) != 4:
                return None
            version, trace_id, span_id, flags = parts
            if version != "00":
                return None
            return cls(
                trace_id=trace_id,
                span_id=span_id,
                sampled=flags == "01",
            )
        except Exception:
            return None

    def to_headers(self) -> dict[str, str]:
        """Gera headers para propagação HTTP."""
        return {"traceparent": self.to_traceparent()}


# =============================================================================
# SPAN
# =============================================================================


@dataclass
class Span:
    """
    Um span de tracing.

    ## Ciclo de vida:
    1. Criado com nome e parent opcional
    2. Atributos adicionados durante execução
    3. Status definido (ok/error)
    4. Finalizado (registra duração)
    """

    name: str
    context: SpanContext
    parent_context: SpanContext | None = None
    attributes: dict[str, Any] = field(default_factory=lambda: {})
    status: str = "unset"
    status_message: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    events: list[dict[str, Any]] = field(default_factory=lambda: [])

    def set_attribute(self, key: str, value: Any) -> None:
        """Define um atributo no span."""
        self.attributes[key] = value

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        """Define múltiplos atributos."""
        self.attributes.update(attributes)

    def set_status(self, status: str, message: str = "") -> None:
        """Define status: 'ok', 'error', 'unset'."""
        self.status = status
        self.status_message = message

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Adiciona um evento ao span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def record_exception(self, exception: Exception) -> None:
        """Registra uma exceção como evento."""
        self.add_event("exception", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
        })
        self.set_status("error", str(exception))

    def end(self) -> None:
        """Finaliza o span."""
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        """Duração em milissegundos."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário (para exportação)."""
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.parent_context.span_id if self.parent_context else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": self.events,
        }


# =============================================================================
# TRACER
# =============================================================================


class Tracer:
    """
    Tracer principal para criar spans.

    ## Uso:
    ```python
    tracer = Tracer()

    with tracer.span("operation") as span:
        span.set_attribute("key", "value")
        do_something()
    ```
    """

    def __init__(self, service_name: str = "aqa-brain"):
        self.service_name = service_name
        self._current_span: Span | None = None
        self._spans: list[Span] = []
        self._exporters: list[Callable[[Span], None]] = []

    def add_exporter(self, exporter: Callable[[Span], None]) -> None:
        """Adiciona um exporter de spans."""
        self._exporters.append(exporter)

    def _generate_id(self, length: int = 16) -> str:
        """Gera ID hexadecimal."""
        return uuid.uuid4().hex[:length * 2]

    @contextmanager
    def span(
        self,
        name: str,
        parent: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """
        Cria um span como context manager.

        ## Parâmetros:
        - name: Nome do span (ex: "aqa.generate_plan")
        - parent: Contexto pai (para spans aninhados)
        - attributes: Atributos iniciais

        ## Exemplo:
        ```python
        with tracer.span("generate", attributes={"file": "api.yaml"}) as span:
            result = generate_plan()
            span.set_attribute("steps", len(result.steps))
        ```
        """
        # Determina parent
        parent_ctx = parent or (self._current_span.context if self._current_span else None)

        # Cria contexto do span
        if parent_ctx:
            context = SpanContext(
                trace_id=parent_ctx.trace_id,
                span_id=self._generate_id(8),
                parent_span_id=parent_ctx.span_id,
            )
        else:
            context = SpanContext(
                trace_id=self._generate_id(16),
                span_id=self._generate_id(8),
            )

        # Cria span
        span = Span(
            name=name,
            context=context,
            parent_context=parent_ctx,
            attributes=attributes or {},
        )

        # Set current
        previous_span = self._current_span
        self._current_span = span

        try:
            yield span
            if span.status == "unset":
                span.set_status("ok")
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            span.end()
            self._current_span = previous_span
            self._spans.append(span)

            # Export
            for exporter in self._exporters:
                try:
                    exporter(span)
                except Exception as ex:
                    logger.warning(f"Failed to export span: {ex}")

    def get_current_span(self) -> Span | None:
        """Retorna o span atual."""
        return self._current_span

    def get_current_context(self) -> SpanContext | None:
        """Retorna o contexto do span atual."""
        return self._current_span.context if self._current_span else None


# =============================================================================
# NOOP TRACER (quando desativado)
# =============================================================================


class NoopSpan:
    """Span que não faz nada (para quando telemetria está desativada)."""

    context = SpanContext(trace_id="00000000000000000000000000000000", span_id="0000000000000000")

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        pass

    def set_status(self, status: str, message: str = "") -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass


class NoopTracer:
    """Tracer que não faz nada."""

    @contextmanager
    def span(
        self,
        name: str,
        parent: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[NoopSpan, None, None]:
        yield NoopSpan()

    def get_current_span(self) -> None:
        return None

    def get_current_context(self) -> None:
        return None


# =============================================================================
# EXPORTERS
# =============================================================================


def console_exporter(span: Span) -> None:
    """Exporta spans para console (desenvolvimento)."""
    import json
    data = span.to_dict()
    logger.info(f"[SPAN] {json.dumps(data, indent=2, default=str)}")


def otlp_exporter_factory(endpoint: str) -> Callable[[Span], None]:
    """
    Cria exporter OTLP.

    ## Nota:
    Esta é uma implementação simplificada. Para produção,
    use opentelemetry-exporter-otlp oficial.
    """
    import requests

    def exporter(span: Span) -> None:
        # Formato simplificado para OTLP
        payload: dict[str, list[dict[str, object]]] = {
            "resourceSpans": [{
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "aqa-brain"}},
                    ]
                },
                "scopeSpans": [{
                    "scope": {"name": "aqa"},
                    "spans": [span.to_dict()],
                }]
            }]
        }
        try:
            requests.post(
                f"{endpoint}/v1/traces",
                json=payload,
                timeout=5,
            )
        except Exception as e:
            logger.debug(f"OTLP export failed: {e}")

    return exporter


# =============================================================================
# GLOBAL TRACER
# =============================================================================

_tracer: Tracer | NoopTracer = NoopTracer()


def init_telemetry(
    enabled: bool | None = None,
    console: bool | None = None,
    otlp_endpoint: str | None = None,
    service_name: str | None = None,
) -> Tracer | NoopTracer:
    """
    Inicializa telemetria.

    ## Parâmetros (todos opcionais, usa env vars como fallback):
    - enabled: Ativar telemetria
    - console: Exportar para console
    - otlp_endpoint: Endpoint OTLP (ex: http://localhost:4317)
    - service_name: Nome do serviço

    ## Retorna:
    Tracer configurado
    """
    global _tracer

    # Resolve config
    is_enabled = enabled if enabled is not None else _config.enabled
    use_console = console if console is not None else _config.console_export
    endpoint = otlp_endpoint or _config.otlp_endpoint
    name = service_name or _config.service_name

    if not is_enabled:
        _tracer = NoopTracer()
        logger.debug("Telemetry disabled")
        return _tracer

    # Cria tracer real
    _tracer = Tracer(service_name=name)

    # Adiciona exporters
    if use_console:
        _tracer.add_exporter(console_exporter)
        logger.info("Console span exporter enabled")

    if endpoint:
        _tracer.add_exporter(otlp_exporter_factory(endpoint))
        logger.info(f"OTLP exporter enabled: {endpoint}")

    logger.info(f"Telemetry initialized for service: {name}")
    return _tracer


def get_tracer() -> Tracer | NoopTracer:
    """Retorna o tracer global."""
    return _tracer


def shutdown_telemetry() -> None:
    """Desliga telemetria (flush pendente)."""
    global _tracer
    logger.debug("Telemetry shutdown")
    _tracer = NoopTracer()


# =============================================================================
# DECORATORS
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])


def trace_span(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator para adicionar tracing a uma função.

    ## Uso:
    ```python
    @trace_span("aqa.generate_plan")
    def generate_plan(swagger_file: str) -> Plan:
        ...

    @trace_span()  # Usa nome da função
    def validate_plan(plan: Plan) -> bool:
        ...
    ```
    """
    def decorator(func: F) -> F:
        span_name = name or f"aqa.{func.__name__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.span(span_name, attributes=attributes):
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# CONTEXT PROPAGATION
# =============================================================================


def inject_context(headers: dict[str, str] | None = None) -> dict[str, str]:
    """
    Injeta contexto de tracing em headers HTTP.

    ## Uso:
    ```python
    # Brain enviando para Runner
    headers = inject_context()
    response = requests.post(runner_url, headers=headers, json=plan)
    ```
    """
    result = headers.copy() if headers else {}
    tracer = get_tracer()
    ctx = tracer.get_current_context()
    if ctx:
        result.update(ctx.to_headers())
    return result


def extract_context(headers: dict[str, str]) -> SpanContext | None:
    """
    Extrai contexto de tracing de headers HTTP.

    ## Uso:
    ```python
    # Runner recebendo do Brain
    parent_ctx = extract_context(request.headers)
    with tracer.span("execute_plan", parent=parent_ctx):
        ...
    ```
    """
    traceparent = headers.get("traceparent")
    if traceparent:
        return SpanContext.from_traceparent(traceparent)
    return None
