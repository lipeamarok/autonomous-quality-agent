"""
# Real LLM Provider com Fallback

Provider que usa APIs reais de IA (GPT, Grok) com fallback automático.

## Para todos entenderem:

É como ter um plano B:
1. Tenta GPT-4 primeiro
2. Se falhar, tenta Grok
3. Se ambos falharem, levanta erro

## Configuração via variáveis de ambiente:

```bash
# OpenAI (GPT)
OPENAI_API_KEY=sk-...

# xAI (Grok)
XAI_API_KEY=xai-...

# Anthropic (Claude) - futuro
ANTHROPIC_API_KEY=...
```

## Prioridade de fallback:

1. OpenAI GPT-4 (padrão)
2. xAI Grok-2
3. (Futuro: Claude, Gemini, etc.)
"""

import os
import time
from typing import Any

from .base import BaseLLMProvider, LLMResponse


class RealLLMProvider(BaseLLMProvider):
    """
    Provider que usa APIs reais de LLM com fallback.

    ## Exemplo:
        >>> provider = RealLLMProvider()
        >>> if provider.is_available():
        ...     response = provider.generate("Gere um teste de login")
    """

    # Modelos padrão por provider
    DEFAULT_MODELS = {
        "openai": "gpt-4o",
        "xai": "grok-2-latest",
        "anthropic": "claude-3-5-sonnet-20241022",
    }

    def __init__(
        self,
        preferred_provider: str | None = None,
        enable_fallback: bool = True,
    ):
        """
        Inicializa o provider real.

        ## Parâmetros:
            preferred_provider: Provider preferido ("openai", "xai", "anthropic")
            enable_fallback: Se True, tenta outros providers em caso de falha
        """
        self._preferred = preferred_provider
        self._enable_fallback = enable_fallback
        self._last_provider_used: str | None = None
        self._clients: dict[str, Any] = {}

        # Inicializa clientes disponíveis
        self._init_clients()

    def _init_clients(self) -> None:
        """Inicializa clientes de API disponíveis."""
        # OpenAI
        if os.environ.get("OPENAI_API_KEY"):
            try:
                from openai import OpenAI

                self._clients["openai"] = OpenAI()
            except ImportError:
                pass

        # xAI (Grok) - usa SDK compatível com OpenAI
        if os.environ.get("XAI_API_KEY"):
            try:
                from openai import OpenAI

                self._clients["xai"] = OpenAI(
                    api_key=os.environ["XAI_API_KEY"],
                    base_url="https://api.x.ai/v1",
                )
            except ImportError:
                pass

        # Anthropic (Claude)
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from anthropic import Anthropic  # type: ignore[import-not-found]

                self._clients["anthropic"] = Anthropic()
            except ImportError:
                pass

    @property
    def name(self) -> str:
        return "real"

    @property
    def last_provider_used(self) -> str | None:
        """Retorna qual provider foi usado na última chamada."""
        return self._last_provider_used

    @property
    def available_providers(self) -> list[str]:
        """Lista de providers disponíveis (com API key configurada)."""
        return list(self._clients.keys())

    def is_available(self) -> bool:
        """Verifica se pelo menos um provider está disponível."""
        return len(self._clients) > 0

    def _get_provider_order(self) -> list[str]:
        """Retorna ordem de providers a tentar."""
        order = ["openai", "xai", "anthropic"]

        if self._preferred and self._preferred in order:
            order.remove(self._preferred)
            order.insert(0, self._preferred)

        return [p for p in order if p in self._clients]

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Gera resposta usando LLM real com fallback.

        ## Lógica:
        1. Tenta provider preferido
        2. Se falhar e fallback habilitado, tenta próximo
        3. Retorna resposta do primeiro que funcionar

        ## Erros:
        - RuntimeError: Se nenhum provider disponível
        - ConnectionError: Se todos os providers falharem
        """
        if not self.is_available():
            raise RuntimeError(
                "Nenhum provider LLM disponível. "
                "Configure OPENAI_API_KEY, XAI_API_KEY ou ANTHROPIC_API_KEY."
            )

        providers_to_try = self._get_provider_order()
        if not self._enable_fallback:
            providers_to_try = providers_to_try[:1]

        errors: list[tuple[str, Exception]] = []

        for provider_name in providers_to_try:
            try:
                response = self._call_provider(
                    provider_name,
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                self._last_provider_used = provider_name
                return response

            except Exception as e:
                errors.append((provider_name, e))
                if not self._enable_fallback:
                    raise

        # Todos falharam
        error_details = "; ".join(f"{p}: {e}" for p, e in errors)
        raise ConnectionError(f"Todos os providers falharam: {error_details}")

    def _call_provider(
        self,
        provider_name: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Chama um provider específico."""
        client = self._clients[provider_name]
        model = self.DEFAULT_MODELS[provider_name]

        start_time = time.time()

        if provider_name in ("openai", "xai"):
            response = self._call_openai_compatible(
                client,
                model,
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        elif provider_name == "anthropic":
            response = self._call_anthropic(
                client,
                model,
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            raise ValueError(f"Provider desconhecido: {provider_name}")

        elapsed_ms = (time.time() - start_time) * 1000
        response.latency_ms = elapsed_ms

        return response

    def _call_openai_compatible(
        self,
        client: Any,
        model: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Chama API compatível com OpenAI (GPT, Grok)."""
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        # Determinar provider pelo base_url
        provider = "openai"
        if hasattr(client, "_base_url") and "x.ai" in str(client._base_url):
            provider = "xai"

        return LLMResponse(
            content=content,
            model=model,
            provider=provider,
            tokens_used=tokens_used,
            metadata={"finish_reason": response.choices[0].finish_reason},
        )

    def _call_anthropic(
        self,
        client: Any,
        model: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Chama API do Anthropic (Claude)."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        # Anthropic não aceita temperature=0 exatamente
        if temperature > 0:
            kwargs["temperature"] = temperature

        response = client.messages.create(**kwargs)

        content = response.content[0].text if response.content else ""
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        return LLMResponse(
            content=content,
            model=model,
            provider="anthropic",
            tokens_used=tokens_used,
            metadata={"stop_reason": response.stop_reason},
        )
