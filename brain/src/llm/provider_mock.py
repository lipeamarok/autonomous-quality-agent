"""
# Mock LLM Provider

Provider que retorna respostas determinísticas para testes.

## Para todos entenderem:

É como um "dublê" de filme:
- Parece com o ator real (mesma interface)
- Mas é previsível e controlável
- Perfeito para testes automatizados

## Quando usar:

✅ CI/CD (testes rápidos sem custo)
✅ Testes unitários
✅ Desenvolvimento local
✅ Demonstrações

## Quando NÃO usar:

❌ Produção
❌ Validar qualidade real da IA
❌ Testes de performance da API
"""

import json
import time
from typing import Any

from .base import BaseLLMProvider, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """
    Provider mock para testes.

    Retorna planos UTDL pré-definidos baseados em palavras-chave
    no prompt, garantindo testes determinísticos.

    ## Exemplo:
        >>> provider = MockLLMProvider()
        >>> response = provider.generate("Teste de login")
        >>> assert "login" in response.content
    """

    # Templates de resposta baseados em palavras-chave
    TEMPLATES: dict[str, dict[str, Any]] = {
        "login": {
            "meta": {"name": "Login Test", "version": "1.0"},
            "config": {"base_url": "${BASE_URL}"},
            "steps": [
                {
                    "id": "login",
                    "action": "http_request",
                    "description": "Autentica usuário",
                    "params": {
                        "method": "POST",
                        "path": "/auth/login",
                        "body": {"email": "${USER_EMAIL}", "password": "${USER_PASSWORD}"},
                    },
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 200}
                    ],
                    "extract": [
                        {"source": "body", "path": "$.token", "target": "auth_token"}
                    ],
                }
            ],
        },
        "crud": {
            "meta": {"name": "CRUD Test", "version": "1.0"},
            "config": {"base_url": "${BASE_URL}"},
            "steps": [
                {
                    "id": "create",
                    "action": "http_request",
                    "description": "Cria recurso",
                    "params": {"method": "POST", "path": "/items", "body": {"name": "test"}},
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 201}
                    ],
                    "extract": [{"source": "body", "path": "$.id", "target": "item_id"}],
                },
                {
                    "id": "read",
                    "action": "http_request",
                    "description": "Lê recurso",
                    "depends_on": ["create"],
                    "params": {"method": "GET", "path": "/items/${item_id}"},
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 200}
                    ],
                },
                {
                    "id": "update",
                    "action": "http_request",
                    "description": "Atualiza recurso",
                    "depends_on": ["read"],
                    "params": {
                        "method": "PUT",
                        "path": "/items/${item_id}",
                        "body": {"name": "updated"},
                    },
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 200}
                    ],
                },
                {
                    "id": "delete",
                    "action": "http_request",
                    "description": "Remove recurso",
                    "depends_on": ["update"],
                    "params": {"method": "DELETE", "path": "/items/${item_id}"},
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 204}
                    ],
                },
            ],
        },
        "health": {
            "meta": {"name": "Health Check", "version": "1.0"},
            "config": {"base_url": "${BASE_URL}"},
            "steps": [
                {
                    "id": "health",
                    "action": "http_request",
                    "description": "Verifica saúde da API",
                    "params": {"method": "GET", "path": "/health"},
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 200}
                    ],
                }
            ],
        },
    }

    # Template padrão quando nenhuma palavra-chave é encontrada
    DEFAULT_TEMPLATE: dict[str, Any] = {
        "meta": {"name": "Generic API Test", "version": "1.0"},
        "config": {"base_url": "${BASE_URL}"},
        "steps": [
            {
                "id": "request",
                "action": "http_request",
                "description": "Request genérico",
                "params": {"method": "GET", "path": "/"},
                "assertions": [
                    {"type": "status_code", "operator": "eq", "value": 200}
                ],
            }
        ],
    }

    def __init__(self, latency_ms: float = 10.0, fail_on_next: bool = False):
        """
        Inicializa o mock provider.

        ## Parâmetros:
            latency_ms: Latência simulada (para testes de timeout)
            fail_on_next: Se True, próxima chamada levanta exceção
        """
        self._latency_ms = latency_ms
        self._fail_on_next = fail_on_next
        self._call_count = 0
        self._last_prompt: str | None = None

    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        """Mock está sempre disponível."""
        return True

    @property
    def call_count(self) -> int:
        """Quantas vezes generate() foi chamado."""
        return self._call_count

    @property
    def last_prompt(self) -> str | None:
        """Último prompt recebido (para assertions em testes)."""
        return self._last_prompt

    def set_fail_on_next(self, fail: bool = True) -> None:
        """Configura para falhar na próxima chamada."""
        self._fail_on_next = fail

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
        Gera resposta mock baseada em palavras-chave no prompt.

        ## Lógica:
        1. Procura palavras-chave no prompt
        2. Retorna template correspondente
        3. Se nenhuma encontrada, retorna template padrão

        ## Exemplo:
            >>> provider = MockLLMProvider()
            >>> response = provider.generate("testar autenticação login")
            >>> "login" in response.content  # True, pois "login" está no prompt
        """
        self._call_count += 1
        self._last_prompt = prompt

        # Simular falha (para testes de fallback)
        if self._fail_on_next:
            self._fail_on_next = False
            raise ConnectionError("Mock: Simulated failure")

        # Simular latência
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000)

        start_time = time.time()

        # Encontrar template baseado em palavras-chave
        prompt_lower = prompt.lower()
        template = self.DEFAULT_TEMPLATE

        for keyword, tpl in self.TEMPLATES.items():
            if keyword in prompt_lower:
                template = tpl
                break

        # Converter para JSON
        content = json.dumps(template, indent=2)

        elapsed_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=content,
            model="mock-v1",
            provider="mock",
            tokens_used=0,
            latency_ms=elapsed_ms + self._latency_ms,
            metadata={
                "template_used": next(
                    (k for k in self.TEMPLATES if k in prompt_lower), "default"
                ),
                "prompt_length": len(prompt),
            },
        )

    def reset(self) -> None:
        """Reseta contadores para novo teste."""
        self._call_count = 0
        self._last_prompt = None
        self._fail_on_next = False
