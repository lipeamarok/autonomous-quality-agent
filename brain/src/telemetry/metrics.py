"""
================================================================================
Metrics — Métricas de Observabilidade
================================================================================

Este módulo implementa coleta de métricas para o AQA Brain.

## Para todos entenderem:

Métricas são números que ajudam a entender o comportamento do sistema:
- Contadores: Incrementam (ex: cache_hits)
- Histogramas: Distribuições (ex: tempo de geração)
- Gauges: Valores instantâneos (ex: planos em cache)

## Métricas Coletadas:

### Geração
- `aqa.generation.duration_seconds` → Tempo de geração de planos
- `aqa.generation.steps_count` → Número de steps por plano
- `aqa.generation.correction_loops` → Loops de correção com LLM

### Cache
- `aqa.cache.hits_total` → Cache hits
- `aqa.cache.misses_total` → Cache misses
- `aqa.cache.size_bytes` → Tamanho do cache

### LLM
- `aqa.llm.tokens_total` → Tokens consumidos
- `aqa.llm.requests_total` → Requisições para LLM
- `aqa.llm.errors_total` → Erros de LLM

### Validação
- `aqa.validation.errors_total` → Erros de validação
- `aqa.validation.duration_seconds` → Tempo de validação

## Configuração:

```bash
export AQA_METRICS_ENABLED=true
export AQA_METRICS_PORT=9090  # Prometheus endpoint
```
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Any
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================


@dataclass
class MetricsConfig:
    """Configuração de métricas."""
    
    enabled: bool = field(
        default_factory=lambda: os.getenv("AQA_METRICS_ENABLED", "").lower() == "true"
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("AQA_METRICS_PORT", "9090"))
    )
    prefix: str = "aqa"


_config = MetricsConfig()


# =============================================================================
# METRIC TYPES
# =============================================================================


class Counter:
    """
    Contador monotônico (só incrementa).
    
    ## Uso:
    ```python
    cache_hits = Counter("cache_hits", "Number of cache hits")
    cache_hits.add(1)
    cache_hits.add(5, labels={"endpoint": "/api/users"})
    ```
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0.0
        self._labeled_values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = Lock()
    
    def add(self, value: float = 1, labels: dict[str, str] | None = None) -> None:
        """Incrementa o contador."""
        with self._lock:
            if labels:
                key = tuple(sorted(labels.items()))
                self._labeled_values[key] = self._labeled_values.get(key, 0.0) + value
            else:
                self._value += value
    
    def get(self, labels: dict[str, str] | None = None) -> float:
        """Retorna valor atual."""
        with self._lock:
            if labels:
                key = tuple(sorted(labels.items()))
                return self._labeled_values.get(key, 0.0)
            return self._value
    
    def to_prometheus(self) -> str:
        """Formata para Prometheus."""
        lines = [f"# HELP {self.name} {self.description}"]
        lines.append(f"# TYPE {self.name} counter")
        
        with self._lock:
            if self._value > 0:
                lines.append(f"{self.name} {self._value}")
            for key, value in self._labeled_values.items():
                labels_str = ",".join(f'{k}="{v}"' for k, v in key)
                lines.append(f"{self.name}{{{labels_str}}} {value}")
        
        return "\n".join(lines)


class Histogram:
    """
    Histograma para distribuições.
    
    ## Uso:
    ```python
    gen_time = Histogram("generation_seconds", "Time to generate plan")
    gen_time.observe(2.5)
    
    # Ou como context manager
    with gen_time.time():
        generate_plan()
    ```
    """
    
    # Buckets padrão (em segundos)
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, float("inf"))
    
    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: tuple[float, ...] | None = None,
    ):
        self.name = name
        self.description = description
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._count = 0
        self._sum = 0.0
        self._bucket_counts: dict[float, int] = {b: 0 for b in self.buckets}
        self._lock = Lock()
    
    def observe(self, value: float) -> None:
        """Registra uma observação."""
        with self._lock:
            self._count += 1
            self._sum += value
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] += 1
    
    @contextmanager
    def time(self):
        """Context manager para medir tempo automaticamente."""
        start = time.time()
        try:
            yield
        finally:
            self.observe(time.time() - start)
    
    def get_stats(self) -> dict[str, float]:
        """Retorna estatísticas."""
        with self._lock:
            return {
                "count": self._count,
                "sum": self._sum,
                "avg": self._sum / self._count if self._count > 0 else 0,
            }
    
    def to_prometheus(self) -> str:
        """Formata para Prometheus."""
        lines = [f"# HELP {self.name} {self.description}"]
        lines.append(f"# TYPE {self.name} histogram")
        
        with self._lock:
            cumulative = 0
            for bucket in sorted(self.buckets):
                if bucket == float("inf"):
                    bucket_label = "+Inf"
                else:
                    bucket_label = str(bucket)
                cumulative += self._bucket_counts[bucket]
                lines.append(f'{self.name}_bucket{{le="{bucket_label}"}} {cumulative}')
            lines.append(f"{self.name}_sum {self._sum}")
            lines.append(f"{self.name}_count {self._count}")
        
        return "\n".join(lines)


class Gauge:
    """
    Gauge para valores instantâneos.
    
    ## Uso:
    ```python
    cache_size = Gauge("cache_size_bytes", "Size of cache in bytes")
    cache_size.set(1024)
    cache_size.inc(100)
    cache_size.dec(50)
    ```
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0.0
        self._lock = Lock()
    
    def set(self, value: float) -> None:
        """Define valor."""
        with self._lock:
            self._value = value
    
    def inc(self, value: float = 1) -> None:
        """Incrementa."""
        with self._lock:
            self._value += value
    
    def dec(self, value: float = 1) -> None:
        """Decrementa."""
        with self._lock:
            self._value -= value
    
    def get(self) -> float:
        """Retorna valor atual."""
        with self._lock:
            return self._value
    
    def to_prometheus(self) -> str:
        """Formata para Prometheus."""
        lines = [f"# HELP {self.name} {self.description}"]
        lines.append(f"# TYPE {self.name} gauge")
        with self._lock:
            lines.append(f"{self.name} {self._value}")
        return "\n".join(lines)


# =============================================================================
# METRICS REGISTRY
# =============================================================================


class Metrics:
    """
    Registry de métricas do AQA.
    
    ## Métricas disponíveis:
    
    ```python
    Metrics.generation_time.observe(2.5)
    Metrics.cache_hits.add(1)
    Metrics.llm_tokens.add(500, labels={"provider": "openai"})
    ```
    """
    
    # Geração
    generation_time = Histogram(
        "aqa_generation_duration_seconds",
        "Time to generate test plan",
        buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
    )
    generation_steps = Histogram(
        "aqa_generation_steps_count",
        "Number of steps in generated plan",
        buckets=(1, 5, 10, 20, 50, 100, 200),
    )
    correction_loops = Histogram(
        "aqa_generation_correction_loops",
        "Number of LLM correction loops",
        buckets=(0, 1, 2, 3, 4, 5, 10),
    )
    
    # Cache
    cache_hits = Counter("aqa_cache_hits_total", "Number of cache hits")
    cache_misses = Counter("aqa_cache_misses_total", "Number of cache misses")
    cache_size = Gauge("aqa_cache_size_bytes", "Size of cache in bytes")
    cache_entries = Gauge("aqa_cache_entries_count", "Number of entries in cache")
    
    # LLM
    llm_tokens = Counter("aqa_llm_tokens_total", "Total tokens consumed")
    llm_requests = Counter("aqa_llm_requests_total", "Total LLM API requests")
    llm_errors = Counter("aqa_llm_errors_total", "Total LLM API errors")
    llm_latency = Histogram(
        "aqa_llm_latency_seconds",
        "LLM API response time",
        buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
    )
    
    # Validação
    validation_errors = Counter("aqa_validation_errors_total", "Validation errors")
    validation_time = Histogram(
        "aqa_validation_duration_seconds",
        "Time to validate plan",
    )
    
    # Execução (do Runner, reportado via API)
    execution_steps = Counter("aqa_execution_steps_total", "Steps executed")
    execution_passed = Counter("aqa_execution_passed_total", "Steps passed")
    execution_failed = Counter("aqa_execution_failed_total", "Steps failed")
    
    @classmethod
    def all_metrics(cls) -> list[Counter | Histogram | Gauge]:
        """Retorna todas as métricas."""
        return [
            cls.generation_time,
            cls.generation_steps,
            cls.correction_loops,
            cls.cache_hits,
            cls.cache_misses,
            cls.cache_size,
            cls.cache_entries,
            cls.llm_tokens,
            cls.llm_requests,
            cls.llm_errors,
            cls.llm_latency,
            cls.validation_errors,
            cls.validation_time,
            cls.execution_steps,
            cls.execution_passed,
            cls.execution_failed,
        ]
    
    @classmethod
    def to_prometheus(cls) -> str:
        """Exporta todas as métricas em formato Prometheus."""
        lines: list[str] = []
        for metric in cls.all_metrics():
            lines.append(metric.to_prometheus())
            lines.append("")
        return "\n".join(lines)
    
    @classmethod
    def get_summary(cls) -> dict[str, Any]:
        """Retorna resumo das métricas (para JSON API)."""
        return {
            "generation": {
                "time": cls.generation_time.get_stats(),
                "steps": cls.generation_steps.get_stats(),
                "corrections": cls.correction_loops.get_stats(),
            },
            "cache": {
                "hits": cls.cache_hits.get(),
                "misses": cls.cache_misses.get(),
                "hit_rate": (
                    cls.cache_hits.get() / (cls.cache_hits.get() + cls.cache_misses.get())
                    if (cls.cache_hits.get() + cls.cache_misses.get()) > 0
                    else 0
                ),
                "size_bytes": cls.cache_size.get(),
                "entries": cls.cache_entries.get(),
            },
            "llm": {
                "tokens": cls.llm_tokens.get(),
                "requests": cls.llm_requests.get(),
                "errors": cls.llm_errors.get(),
                "latency": cls.llm_latency.get_stats(),
            },
            "validation": {
                "errors": cls.validation_errors.get(),
                "time": cls.validation_time.get_stats(),
            },
            "execution": {
                "steps": cls.execution_steps.get(),
                "passed": cls.execution_passed.get(),
                "failed": cls.execution_failed.get(),
            },
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def init_metrics(
    enabled: bool | None = None,
    port: int | None = None,
) -> bool:
    """
    Inicializa sistema de métricas.
    
    ## Parâmetros:
    - enabled: Ativar métricas
    - port: Porta para endpoint Prometheus
    
    ## Retorna:
    True se inicializado com sucesso
    """
    is_enabled = enabled if enabled is not None else _config.enabled
    
    if not is_enabled:
        logger.debug("Metrics disabled")
        return False
    
    # Por enquanto, apenas marca como habilitado
    # Em produção, aqui iniciaria um servidor HTTP para Prometheus
    logger.info("Metrics enabled")
    return True


def record_generation_time(seconds: float, steps_count: int = 0) -> None:
    """Registra tempo de geração."""
    Metrics.generation_time.observe(seconds)
    if steps_count > 0:
        Metrics.generation_steps.observe(steps_count)


def record_cache_hit() -> None:
    """Registra cache hit."""
    Metrics.cache_hits.add(1)


def record_cache_miss() -> None:
    """Registra cache miss."""
    Metrics.cache_misses.add(1)


def record_validation_error(error_type: str = "unknown") -> None:
    """Registra erro de validação."""
    Metrics.validation_errors.add(1, labels={"type": error_type})


def record_llm_tokens(
    tokens: int,
    provider: str = "unknown",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Registra tokens consumidos."""
    Metrics.llm_tokens.add(tokens, labels={"provider": provider})
    Metrics.llm_requests.add(1, labels={"provider": provider})
