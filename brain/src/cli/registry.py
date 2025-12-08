"""
================================================================================
Registry de Comandos CLI
================================================================================

Sistema de registro de comandos que evita imports circulares.

## Por que isso existe?

Antes, os comandos eram importados no final de cli/main.py, o que:
1. Pode causar imports circulares
2. Dificulta testes isolados
3. Torna difícil adicionar comandos dinamicamente

## Como funciona:

1. Cada comando se registra usando o decorator `@register_command`
2. O main.py chama `register_all_commands(cli)` para registrar todos
3. Os imports são feitos de forma controlada

## Exemplo de uso em um comando:

```python
# commands/my_cmd.py
from ..registry import register_command

@register_command
@click.command()
def my_command():
    pass
```

## Benefícios:

- Imports explícitos e controlados
- Fácil adicionar/remover comandos
- Melhor testabilidade
- Suporte a plugins futuros
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import click

if TYPE_CHECKING:
    pass


# =============================================================================
# REGISTRY GLOBAL
# =============================================================================

# TypeVar para preservar o tipo exato (Command ou Group)
T = TypeVar("T", bound=click.Command)

# Lista de comandos registrados (nome, comando)
_registered_commands: list[click.Command] = []


def register_command(cmd: T) -> T:
    """
    Decorator que registra um comando no registry global.

    Não modifica o comando, apenas o adiciona à lista de comandos.

    ## Exemplo:

        @register_command
        @click.command()
        def my_command():
            pass
    """
    if cmd not in _registered_commands:
        _registered_commands.append(cmd)
    return cmd


def get_registered_commands() -> list[click.Command]:
    """Retorna lista de comandos registrados."""
    return _registered_commands.copy()


def clear_registry() -> None:
    """Limpa o registry (útil para testes)."""
    _registered_commands.clear()


def register_all_commands(cli_group: click.Group) -> None:
    """
    Registra todos os comandos no grupo CLI principal.

    Esta função deve ser chamada após importar todos os módulos de comandos.

    ## Parâmetros:
        cli_group: O grupo click principal (geralmente `cli`)

    ## Exemplo:
        >>> from .registry import register_all_commands
        >>> register_all_commands(cli)
    """
    for cmd in _registered_commands:
        if cmd.name and cmd.name not in cli_group.commands:
            cli_group.add_command(cmd)


def load_commands() -> None:
    """
    Importa todos os módulos de comandos para registrá-los.

    Esta função faz os imports de forma controlada e em um único lugar.
    """
    # Importa cada módulo de comando
    # O simples ato de importar registra o comando via decorator
    # Os imports abaixo são propositalmente não utilizados (side-effect only)
    from .commands import init_cmd as _init_cmd  # noqa: F401
    from .commands import generate_cmd as _generate_cmd  # noqa: F401
    from .commands import validate_cmd as _validate_cmd  # noqa: F401
    from .commands import run_cmd as _run_cmd  # noqa: F401
    from .commands import explain_cmd as _explain_cmd  # noqa: F401
    from .commands import demo_cmd as _demo_cmd  # noqa: F401
    from .commands import plan_cmd as _plan_cmd  # noqa: F401
    from .commands import history_cmd as _history_cmd  # noqa: F401
    from .commands import show_cmd as _show_cmd  # noqa: F401
    from .commands import plan_version_cmd as _plan_version_cmd  # noqa: F401
    from .commands import serve_cmd as _serve_cmd  # noqa: F401

    # Silencia warnings de imports não utilizados
    del _init_cmd, _generate_cmd, _validate_cmd, _run_cmd, _explain_cmd
    del _demo_cmd, _plan_cmd, _history_cmd, _show_cmd, _plan_version_cmd
    del _serve_cmd
