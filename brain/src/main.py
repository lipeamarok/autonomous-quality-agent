"""
================================================================================
PONTO DE ENTRADA DO BRAIN — Autonomous Quality Agent
================================================================================

Este módulo serve como ponto de entrada principal para o subsistema Brain,
responsável por gerar planos de teste UTDL a partir de requisitos.

## Para leigos:

Este é o arquivo "principal" do Brain. Quando você executa:
```bash
python -m brain.src.main generate --requirement "Testar login"
```

O Python primeiro executa este arquivo, que chama a função `main()` do CLI.

## Por que ter este arquivo separado?

1. **Convenção Python**: `__main__.py` ou `main.py` é o ponto de entrada padrão
2. **Organização**: Mantém a lógica real no módulo `cli.py`
3. **Flexibilidade**: Facilita importar o Brain como biblioteca

## Uso:

```bash
# Via módulo (recomendado)
python -m brain.src.main generate --requirement "Testar API de login"
python -m brain.src.main run --swagger ./openapi.json

# Direto (também funciona)
python brain/src/main.py generate --requirement "Testar API"
```

## Comandos disponíveis:

| Comando  | Descrição                                |
|----------|------------------------------------------|
| generate | Gera plano UTDL e imprime/salva          |
| run      | Gera plano E executa via Runner Rust     |

## Arquitetura:

```
main.py (este) -> cli.py -> generator/llm.py -> LLM (OpenAI/Claude)
                         -> ingestion/swagger.py -> OpenAPI spec
                         -> runner/execute.py -> Runner (Rust)
```
"""

# Nota: Existe tanto src/cli.py quanto src/cli/ (pacote).
# O pyright pode confundir qual módulo estamos importando.
# Usamos importação explícita do arquivo cli.py via TYPE_CHECKING.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Importa a função main do módulo CLI (arquivo cli.py)
# Este import funciona em runtime, mas pyright pode reportar erro.
from .cli import main as cli_main  # type: ignore[attr-defined]

# Este bloco só executa se rodarmos este arquivo diretamente
# Não executa se importarmos como módulo
if __name__ == "__main__":
    cli_main()  # type: ignore[operator]
