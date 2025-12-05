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

## Flags Globais:

- `--verbose / -v` → Modo verbose (mais detalhes)
- `--quiet / -q` → Modo silencioso (só erros)
- `--json` → Saída estruturada JSON (para CI/CD)
"""

from __future__ import annotations

import logging

import click
from rich.console import Console
from rich.logging import RichHandler

# Console global para output formatado
console = Console()
error_console = Console(stderr=True)

# Console silencioso (para modo --quiet)
quiet_console = Console(quiet=True)


def setup_logging(verbose: bool, quiet: bool) -> None:
    """Configura logging baseado em flags."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=error_console, show_time=False, show_path=False)],
    )


# =============================================================================
# GRUPO PRINCIPAL
# =============================================================================


@click.group()
@click.version_option(version="0.3.0", prog_name="aqa")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Modo verbose (mostra mais detalhes)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Modo silencioso (suprime banners, mostra só erros)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Saída estruturada em JSON (para CI/CD)",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool, json_output: bool) -> None:
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

    \b
    Flags Globais:
      -v, --verbose  Mostra logs detalhados
      -q, --quiet    Suprime saída (só erros)
      --json         Saída JSON estruturada
    """
    # Configura logging
    setup_logging(verbose, quiet)

    # Armazena configuração no contexto para passar aos subcomandos
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["json_output"] = json_output

    # Escolhe console baseado em flags
    if json_output or quiet:
        ctx.obj["console"] = quiet_console
    else:
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
from .commands.explain_cmd import explain
from .commands.demo_cmd import demo
from .commands.plan_cmd import plan
from .commands.history_cmd import history
from .commands.show_cmd import show
from .commands.plan_version_cmd import planversion

# Registra os comandos no grupo principal
cli.add_command(init)
cli.add_command(generate)
cli.add_command(validate)
cli.add_command(run)
cli.add_command(explain)
cli.add_command(demo)
cli.add_command(plan)
cli.add_command(history)
cli.add_command(show)
cli.add_command(planversion)


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================


def main() -> None:
    """Entry point para o comando `aqa`."""
    cli()


if __name__ == "__main__":
    main()
