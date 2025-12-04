"""
# Base Classes para LLM Providers

Define a interface (contrato) que todos os providers devem seguir.

## Para todos entenderem:

É como um contrato de trabalho:
- Todo provider DEVE ter um método `generate()`
- Todo provider DEVE retornar um `LLMResponse`
- Se não seguir, o código quebra (e isso é bom, pega erros cedo)

## Por que usar ABC (Abstract Base Class)?

ABC = "Classe Base Abstrata"
- Não pode ser instanciada diretamente
- Força as subclasses a implementar os métodos
- Documenta claramente o que é esperado
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """
    Resposta padronizada de qualquer provider LLM.

    ## Campos:

    - content: O texto gerado pela IA (geralmente JSON do plano UTDL)
    - model: Qual modelo foi usado (ex: "gpt-4", "grok-4", "mock")
    - provider: Nome do provider (ex: "openai", "xai", "mock")
    - tokens_used: Quantos tokens foram consumidos (0 para mock)
    - latency_ms: Tempo de resposta em milissegundos
    - metadata: Dados extras para debug (opcional)

    ## Exemplo:
        >>> response = LLMResponse(
        ...     content='{"steps": [...]}',
        ...     model="gpt-4",
        ...     provider="openai",
        ...     tokens_used=1500,
        ...     latency_ms=2340
        ... )
    """

    content: str
    model: str
    provider: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=lambda: {})

    @property
    def is_mock(self) -> bool:
        """Retorna True se a resposta veio de um mock."""
        return self.provider == "mock"


class BaseLLMProvider(ABC):
    """
    Interface base para todos os providers de LLM.

    ## Para todos entenderem:

    Esta é a "forma" que todo provider deve ter.
    É como dizer: "Todo carro deve ter volante, pedais e motor".

    ## Métodos obrigatórios:

    - generate(): Gera texto a partir de um prompt
    - name: Retorna o nome do provider
    - is_available(): Verifica se o provider está configurado

    ## Exemplo de implementação:
        >>> class MeuProvider(BaseLLMProvider):
        ...     @property
        ...     def name(self) -> str:
        ...         return "meu-provider"
        ...
        ...     def is_available(self) -> bool:
        ...         return True
        ...
        ...     def generate(self, prompt: str, **kwargs) -> LLMResponse:
        ...         return LLMResponse(content="...", model="x", provider="meu")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador do provider."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifica se o provider está disponível.

        Retorna False se:
        - API key não configurada
        - Serviço offline
        - Rate limit atingido
        """
        ...

    @abstractmethod
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
        Gera texto a partir de um prompt.

        ## Parâmetros:
            prompt: O texto de entrada (o que você quer que a IA faça)
            system_prompt: Instruções de sistema (personalidade, regras)
            temperature: Criatividade (0=determinístico, 1=criativo)
            max_tokens: Limite de tokens na resposta
            **kwargs: Parâmetros específicos do provider

        ## Retorna:
            LLMResponse com o texto gerado e metadados
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"
