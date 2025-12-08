"""
================================================================================
Dependências Injetáveis da API
================================================================================

Define dependências que podem ser injetadas nos endpoints via FastAPI Depends.
Isso facilita testes (mock) e reutilização de instâncias.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Generator

from ..cache import ExecutionHistory, PlanCache, PlanVersionStore
from ..config import BrainConfig
from ..generator import UTDLGenerator
from ..validator import UTDLValidator


@lru_cache()
def get_brain_config() -> BrainConfig:
    """
    Retorna configuração do Brain (cacheada).

    ## Uso em endpoint:

        >>> @router.get("/")
        >>> def endpoint(config: BrainConfig = Depends(get_brain_config)):
        ...     pass
    """
    return BrainConfig.from_env()


def get_generator() -> Generator[UTDLGenerator, None, None]:
    """
    Fornece instância de UTDLGenerator.

    ## Uso em endpoint:

        >>> @router.post("/generate")
        >>> def generate(generator: UTDLGenerator = Depends(get_generator)):
        ...     plan = generator.generate(requirement, base_url)
    """
    config = get_brain_config()
    generator = UTDLGenerator(
        provider=config.llm_provider,
        max_correction_attempts=config.max_llm_retries,
        temperature=config.temperature,
        verbose=config.verbose,
        cache_enabled=config.cache_enabled,
    )
    yield generator


def get_validator() -> Generator[UTDLValidator, None, None]:
    """
    Fornece instância de UTDLValidator.

    ## Uso em endpoint:

        >>> @router.post("/validate")
        >>> def validate(validator: UTDLValidator = Depends(get_validator)):
        ...     result = validator.validate(plan_data)
    """
    validator = UTDLValidator()
    yield validator


def get_execution_history() -> Generator[ExecutionHistory, None, None]:
    """
    Fornece instância de ExecutionHistory.

    ## Uso em endpoint:

        >>> @router.get("/history")
        >>> def history(history: ExecutionHistory = Depends(get_execution_history)):
        ...     records = history.list()
    """
    config = get_brain_config()
    history = config.get_history()
    yield history


def get_plan_cache() -> Generator[PlanCache, None, None]:
    """
    Fornece instância de PlanCache.
    """
    cache = PlanCache.global_cache(enabled=True)
    yield cache


def get_version_store() -> Generator[PlanVersionStore, None, None]:
    """
    Fornece instância de PlanVersionStore para versionamento de planos.

    ## Uso em endpoint:

        >>> @router.get("/plans")
        >>> def list_plans(store: PlanVersionStore = Depends(get_version_store)):
        ...     plans = store.list_plans()
    """
    store = PlanVersionStore.global_store(enabled=True)
    yield store
