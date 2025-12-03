"""
================================================================================
CLI `aqa` — Interface de Linha de Comando para o Autonomous Quality Agent
================================================================================

Este pacote fornece o comando `aqa` para gerar, validar e executar
planos de teste UTDL diretamente do terminal.

## Comandos disponíveis:

```bash
aqa init                           # Inicializa workspace .aqa/
aqa generate --swagger api.yaml    # Gera plano UTDL
aqa validate plan.json             # Valida sintaxe UTDL
aqa run plan.json                  # Executa plano
aqa run --swagger api.yaml         # Gera e executa (fluxo completo)
```

## Para todos entenderem:

O CLI é construído com:
- **Click**: Framework moderno para CLIs em Python
- **Rich**: Formatação colorida, progress bars, tabelas
"""

from .main import cli

__all__ = ["cli"]
