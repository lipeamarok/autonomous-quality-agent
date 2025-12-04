"""
# Factory de Providers LLM

Seleciona o provider correto baseado em configuração.

## Para todos entenderem:

É como um "garçom" que decide qual cozinheiro vai preparar seu prato:
- Se você pediu "mock", manda pro cozinheiro de teste
- Se você pediu "real", manda pro cozinheiro de verdade
- Se não especificou, olha o ambiente

## Ordem de prioridade para decidir o modo:

1. Parâmetro direto (`mode=`)
2. Variável de ambiente (`AQA_LLM_MODE`)
3. Arquivo de config (`llm.mode` no aqa.yaml)
4. Padrão: "real" se há API key, "mock" se não há
"""

import os
from typing import Any

from .base import BaseLLMProvider
from .provider_mock import MockLLMProvider
from .provider_real import RealLLMProvider


def get_llm_provider(
    mode: str | None = None,
    config: dict[str, Any] | None = None,
    **kwargs: Any,
) -> BaseLLMProvider:
    """
    Retorna o provider LLM apropriado.

    ## Parâmetros:
        mode: "mock" ou "real" (sobrescreve tudo)
        config: Dict com configuração (ex: {"llm": {"mode": "mock"}})
        **kwargs: Parâmetros extras para o provider

    ## Retorna:
        BaseLLMProvider configurado

    ## Exemplo:
        >>> # Modo explícito
        >>> provider = get_llm_provider(mode="mock")
        >>> assert provider.name == "mock"

        >>> # Via ambiente
        >>> os.environ["AQA_LLM_MODE"] = "mock"
        >>> provider = get_llm_provider()
        >>> assert provider.name == "mock"

        >>> # Via config
        >>> provider = get_llm_provider(config={"llm": {"mode": "mock"}})
        >>> assert provider.name == "mock"
    """
    # 1. Parâmetro direto tem prioridade máxima
    resolved_mode = mode

    # 2. Variável de ambiente
    if not resolved_mode:
        resolved_mode = os.environ.get("AQA_LLM_MODE")

    # 3. Config file
    if not resolved_mode and config:
        llm_config = config.get("llm")
        if llm_config is not None and isinstance(llm_config, dict):
            mode_value = llm_config.get("mode", None)  # type: ignore[union-attr]
            if isinstance(mode_value, str):
                resolved_mode = mode_value

    # 4. Auto-detect baseado em disponibilidade de API keys
    if not resolved_mode:
        has_api_key = any(
            os.environ.get(key)
            for key in ["OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY"]
        )
        resolved_mode = "real" if has_api_key else "mock"

    # Criar provider
    if resolved_mode == "mock":
        return MockLLMProvider(**kwargs)

    return RealLLMProvider(**kwargs)


def get_available_modes() -> dict[str, Any]:
    """
    Retorna quais modos estão disponíveis.

    ## Retorna:
        Dict com status de cada modo

    ## Exemplo:
        >>> modes = get_available_modes()
        >>> modes["mock"]  # Sempre True
        True
        >>> modes["real"]  # True se alguma API key configurada
        False
    """
    real_provider = RealLLMProvider()

    return {
        "mock": True,  # Sempre disponível
        "real": real_provider.is_available(),
        "available_providers": real_provider.available_providers,
    }
