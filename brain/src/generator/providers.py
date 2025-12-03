"""
================================================================================
PROVEDORES DE LLM - Multi-Provider com Fallback
================================================================================

Este módulo gerencia múltiplos provedores de LLM com suporte a fallback
automático quando o provedor principal falha.

## Para todos entenderem:

Imagine que você tem dois restaurantes favoritos. Se o primeiro está fechado
ou muito cheio, você automaticamente vai para o segundo. Este módulo faz
exatamente isso com provedores de IA.

## Provedores suportados:

| Provedor | Modelo           | Descrição                              |
|----------|------------------|----------------------------------------|
| OpenAI   | gpt-5.1          | SOTA para tarefas complexas (padrão)   |
| xAI      | grok-4-1-fast    | Alta velocidade + raciocínio (fallback)|

## Estratégia de Fallback:

1. Tenta o provedor primário (OpenAI GPT-5.1)
2. Se falhar (timeout, rate limit, erro de API), tenta o fallback (Grok)
3. Se ambos falharem, lança exceção com detalhes

## Variáveis de ambiente necessárias:

- `OPENAI_API_KEY`: Chave da API OpenAI
- `XAI_API_KEY`: Chave da API xAI (Grok)

## Exemplo de uso:

    >>> from brain.src.generator.providers import LLMProvider, get_provider
    >>>
    >>> # Usando provedor padrão
    >>> provider = get_provider()
    >>> response = provider.complete("Gere um plano de testes...")
    >>>
    >>> # Usando provedor específico
    >>> grok = get_provider("grok")
    >>> response = grok.complete("...")
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

from litellm import completion  # type: ignore[import-untyped]


# =============================================================================
# ENUMS E CONSTANTES
# =============================================================================


class ProviderName(str, Enum):
    """
    Nomes dos provedores de LLM suportados.

    Usar Enum evita erros de digitação e facilita autocompletar.
    """
    OPENAI = "openai"
    XAI = "xai"


# =============================================================================
# CONFIGURAÇÃO DOS PROVEDORES
# =============================================================================


@dataclass(frozen=True)
class ProviderConfig:
    """
    Configuração de um provedor de LLM.

    frozen=True significa que o objeto é imutável após criação,
    o que é mais seguro e permite usar como chave de dicionário.

    ## Atributos:

    - `name`: Nome identificador do provedor
    - `model`: Identificador do modelo no provedor
    - `base_url`: URL base da API (None = usar padrão do LiteLLM)
    - `api_key_env`: Nome da variável de ambiente com a API key
    - `description`: Descrição humana do provedor
    - `max_tokens`: Limite de tokens na resposta
    - `supports_json_mode`: Se suporta modo JSON nativo
    """
    name: ProviderName
    model: str
    base_url: str | None
    api_key_env: str
    description: str
    max_tokens: int = 4096
    supports_json_mode: bool = True


# Configurações dos provedores disponíveis
PROVIDER_CONFIGS: dict[ProviderName, ProviderConfig] = {
    ProviderName.OPENAI: ProviderConfig(
        name=ProviderName.OPENAI,
        model="gpt-5.1",
        base_url=None,  # Usa URL padrão do LiteLLM/OpenAI
        api_key_env="OPENAI_API_KEY",
        description="Modelo SOTA (State of the Art) para tarefas complexas.",
        max_tokens=4096,
        supports_json_mode=True,
    ),
    ProviderName.XAI: ProviderConfig(
        name=ProviderName.XAI,
        model="grok-4-1-fast-reasoning",
        base_url="https://api.x.ai/v1",
        api_key_env="XAI_API_KEY",
        description="Alta velocidade com capacidade de raciocínio profundo.",
        max_tokens=4096,
        supports_json_mode=True,
    ),
}

# Ordem de fallback: primeiro OpenAI, depois Grok
FALLBACK_ORDER: list[ProviderName] = [
    ProviderName.OPENAI,
    ProviderName.XAI,
]


# =============================================================================
# EXCEÇÕES
# =============================================================================


class LLMProviderError(Exception):
    """Erro base para problemas com provedores de LLM."""
    pass


class AllProvidersFailedError(LLMProviderError):
    """Todos os provedores falharam."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        messages = [f"{name}: {error}" for name, error in errors.items()]
        super().__init__(
            f"Todos os provedores de LLM falharam:\n" + "\n".join(messages)
        )


class MissingAPIKeyError(LLMProviderError):
    """API key não configurada."""

    def __init__(self, provider: str, env_var: str) -> None:
        self.provider = provider
        self.env_var = env_var
        super().__init__(
            f"API key não configurada para {provider}. "
            f"Defina a variável de ambiente: {env_var}"
        )


# =============================================================================
# CLASSE DO PROVEDOR
# =============================================================================


class LLMProvider:
    """
    Provedor de LLM com suporte a fallback automático.

    ## Para todos entenderem:

    Esta classe é como um "gerente de restaurantes" que sabe quais
    restaurantes estão disponíveis e automaticamente te leva para
    outro se o primeiro não puder te atender.

    ## Funcionalidades:

    - Fallback automático entre provedores
    - Validação de API keys
    - Logs detalhados de tentativas
    - Suporte a configuração customizada

    ## Exemplo:

        >>> provider = LLMProvider()
        >>> response = provider.complete(
        ...     system_prompt="Você é um gerador de testes.",
        ...     user_prompt="Gere testes para login"
        ... )
    """

    def __init__(
        self,
        primary: ProviderName = ProviderName.OPENAI,
        fallbacks: list[ProviderName] | None = None,
        temperature: float = 0.2,
        verbose: bool = False,
    ) -> None:
        """
        Inicializa o provedor de LLM.

        ## Parâmetros:

        - `primary`: Provedor primário a usar
        - `fallbacks`: Lista de provedores para fallback (default: todos menos primário)
        - `temperature`: Temperatura para sampling (0.0-2.0)
        - `verbose`: Se True, loga tentativas e fallbacks
        """
        self.primary = primary
        self.fallbacks = fallbacks or [p for p in FALLBACK_ORDER if p != primary]
        self.temperature = temperature
        self.verbose = verbose

        # Ordem completa de tentativas
        self._providers = [primary] + self.fallbacks

    def _get_config(self, provider: ProviderName) -> ProviderConfig:
        """Retorna a configuração de um provedor."""
        return PROVIDER_CONFIGS[provider]

    def _get_api_key(self, config: ProviderConfig) -> str:
        """
        Obtém a API key de um provedor.

        Lança MissingAPIKeyError se não estiver configurada.
        """
        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            raise MissingAPIKeyError(config.name.value, config.api_key_env)
        return api_key

    def _call_provider(
        self,
        config: ProviderConfig,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Faz chamada a um provedor específico.

        ## Retorna:

        Conteúdo da resposta do LLM.

        ## Lança:

        Qualquer exceção da API do provedor.
        """
        api_key = self._get_api_key(config)

        # Monta kwargs para o LiteLLM
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": config.max_tokens,
            "api_key": api_key,
        }

        # Adiciona base_url se configurado
        if config.base_url:
            kwargs["api_base"] = config.base_url

        # Faz a chamada
        response: Any = completion(**kwargs)

        # Extrai conteúdo
        content: str = str(response.choices[0].message.content or "")
        return content

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, ProviderName]:
        """
        Faz chamada ao LLM com fallback automático.

        ## Parâmetros:

        - `system_prompt`: Instruções gerais para a IA
        - `user_prompt`: O pedido específico do usuário

        ## Retorna:

        Tupla (resposta, provedor_usado)

        ## Lança:

        AllProvidersFailedError se todos os provedores falharem.

        ## Exemplo:

            >>> response, provider = llm.complete(
            ...     system_prompt="Você é um assistente.",
            ...     user_prompt="Diga olá"
            ... )
            >>> print(f"Resposta de {provider}: {response}")
        """
        errors: dict[str, str] = {}

        for provider_name in self._providers:
            config = self._get_config(provider_name)

            try:
                if self.verbose:
                    print(f"[LLM] Tentando {provider_name.value} ({config.model})...")

                content = self._call_provider(config, system_prompt, user_prompt)

                if self.verbose:
                    print(f"[LLM] Sucesso com {provider_name.value}")

                return content, provider_name

            except MissingAPIKeyError as e:
                errors[provider_name.value] = str(e)
                if self.verbose:
                    print(f"[LLM] {provider_name.value}: API key não configurada")
                continue

            except Exception as e:
                errors[provider_name.value] = str(e)
                if self.verbose:
                    print(f"[LLM] {provider_name.value} falhou: {e}")
                continue

        # Todos falharam
        raise AllProvidersFailedError(errors)

    def is_available(self, provider: ProviderName | None = None) -> bool:
        """
        Verifica se um provedor está disponível (API key configurada).

        Se provider for None, verifica se algum provedor está disponível.
        """
        providers_to_check = [provider] if provider else self._providers

        for p in providers_to_check:
            config = self._get_config(p)
            if os.environ.get(config.api_key_env):
                return True

        return False

    def list_available(self) -> list[ProviderName]:
        """Lista todos os provedores com API key configurada."""
        available: list[ProviderName] = []
        for provider in self._providers:
            config = self._get_config(provider)
            if os.environ.get(config.api_key_env):
                available.append(provider)
        return available


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================


def get_provider(
    name: str | ProviderName | None = None,
    temperature: float = 0.2,
    verbose: bool = False,
) -> LLMProvider:
    """
    Cria um provedor de LLM.

    ## Parâmetros:

    - `name`: Nome do provedor primário ("openai", "xai", ou None para padrão)
    - `temperature`: Temperatura para sampling
    - `verbose`: Se True, loga tentativas

    ## Retorna:

    Instância de LLMProvider configurada.

    ## Exemplo:

        >>> provider = get_provider()  # OpenAI como primário
        >>> provider = get_provider("xai")  # Grok como primário
    """
    if name is None:
        primary = ProviderName.OPENAI
    elif isinstance(name, ProviderName):
        primary = name
    else:
        primary = ProviderName(name.lower())

    return LLMProvider(
        primary=primary,
        temperature=temperature,
        verbose=verbose,
    )


def list_providers() -> list[dict[str, Any]]:
    """
    Lista todos os provedores disponíveis com suas configurações.

    ## Retorna:

    Lista de dicionários com informações de cada provedor.

    ## Exemplo:

        >>> for p in list_providers():
        ...     print(f"{p['name']}: {p['model']} - {p['available']}")
    """
    result: list[dict[str, Any]] = []

    for provider_name, config in PROVIDER_CONFIGS.items():
        available = bool(os.environ.get(config.api_key_env))
        result.append({
            "name": provider_name.value,
            "model": config.model,
            "base_url": config.base_url,
            "api_key_env": config.api_key_env,
            "description": config.description,
            "available": available,
        })

    return result
