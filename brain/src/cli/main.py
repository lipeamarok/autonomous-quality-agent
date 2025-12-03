"""
================================================================================
CLI Principal — Entry Point e Configuração
================================================================================

Este módulo define o comando `aqa` e registra todos os subcomandos.

## Arquitetura:

```
aqa (grupo principal)
├── init      → Inicializa workspace .aqa/
├── generate  → Gera plano UTDL usando LLM
├── validate  → Valida sintaxe de um plano UTDL
└── run       → Executa plano (ou gera + executa)
```
"""

from __future__ import annotations

import click
from rich.console import Console

# Console global para output formatado
console = Console()
error_console = Console(stderr=True)


# =============================================================================
# GRUPO PRINCIPAL
# =============================================================================


@click.group()
@click.version_option(version="0.3.0", prog_name="aqa")
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Modo verbose (mostra mais detalhes)"
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """
    🧪 AQA — Autonomous Quality Agent

    Ferramenta de linha de comando para gerar e executar testes
    de API automaticamente usando IA.

    \b
    Exemplos:
      aqa init                           # Inicializa workspace
      aqa generate --swagger api.yaml    # Gera plano de testes
      aqa validate plan.json             # Valida plano UTDL
      aqa run plan.json                  # Executa plano existente
      aqa run --swagger api.yaml         # Gera e executa
    """
    # Armazena configuração no contexto para passar aos subcomandos
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["console"] = console
    ctx.obj["error_console"] = error_console


# =============================================================================
# IMPORTA E REGISTRA SUBCOMANDOS
# =============================================================================

# Importamos os comandos aqui para evitar imports circulares
from .commands.init_cmd import init
from .commands.generate_cmd import generate
from .commands.validate_cmd import validate
from .commands.run_cmd import run

# Registra os comandos no grupo principal
cli.add_command(init)
cli.add_command(generate)
cli.add_command(validate)
cli.add_command(run)


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

def main() -> None:
    """Entry point para o comando `aqa`."""
    cli()


if __name__ == "__main__":
    main()
