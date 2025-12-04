"""
================================================================================
SMART FORMAT ADAPTER — NORMALIZAÇÃO INTELIGENTE DE PLANOS UTDL
================================================================================

Este módulo fornece o SmartFormatAdapter, uma classe que normaliza diferentes
formatos de planos de teste para o formato UTDL válido.

## Para todos entenderem:

Quando LLMs ou usuários geram planos de teste, eles podem usar formatos
ligeiramente diferentes do UTDL oficial. Por exemplo:
- "tests" em vez de "steps"
- "status" em vez de "status_code"
- Sem os campos "meta" ou "config"

O SmartFormatAdapter corrige esses problemas automaticamente, permitindo
que planos "quase corretos" funcionem sem erros.

## Uso:

```python
from src.adapter import SmartFormatAdapter, normalize_plan

# Opção 1: Usar a classe diretamente
adapter = SmartFormatAdapter()
normalized = adapter.normalize(raw_plan_dict)

# Opção 2: Usar função auxiliar
normalized = normalize_plan("path/to/plan.json")
normalized = normalize_plan(raw_plan_dict)
```

## Aliases suportados:

| Alias          | Campo UTDL correto |
|----------------|-------------------|
| tests          | steps             |
| status         | status_code       |
| expected       | value             |
| exports        | extract           |
| from           | source            |
| name (extract) | target            |

"""

from .format_adapter import SmartFormatAdapter, normalize_plan

__all__ = ["SmartFormatAdapter", "normalize_plan"]
