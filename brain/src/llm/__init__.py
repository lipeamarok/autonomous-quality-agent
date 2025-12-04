"""
# Módulo LLM - Providers de IA para Geração de Planos

Este módulo implementa o padrão Strategy para provedores de LLM,
permitindo alternar entre IA real e mock de forma transparente.

## Para todos entenderem:

Imagine que você tem um carro que pode usar gasolina ou álcool.
O motor (Brain) não precisa saber qual combustível está usando,
ele só precisa que o combustível forneça energia.

Aqui é igual:
- O Brain não sabe se está usando GPT, Grok ou Mock
- Ele só precisa que o provider retorne um plano UTDL válido

## Modos de operação:

| Modo   | Uso                          | Custo | Velocidade |
|--------|------------------------------|-------|------------|
| real   | Produção, testes manuais     | $$$   | Lento      |
| mock   | CI/CD, testes automatizados  | $0    | Rápido     |

## Como ativar cada modo:

1. Variável de ambiente:
   ```bash
   AQA_LLM_MODE=mock aqa plan --input "login"
   ```

2. Flag no CLI:
   ```bash
   aqa plan --input "login" --llm-mode mock
   ```

3. Config file (aqa.yaml):
   ```yaml
   llm:
     mode: mock
   ```
"""

from .base import BaseLLMProvider, LLMResponse
from .providers import get_llm_provider
from .provider_mock import MockLLMProvider
from .provider_real import RealLLMProvider

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "get_llm_provider",
    "MockLLMProvider",
    "RealLLMProvider",
]
