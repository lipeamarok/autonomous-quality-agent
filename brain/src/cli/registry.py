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
    from .commands import (  # noqa: F401
        init_cmd,
        generate_cmd,
        validate_cmd,
        run_cmd,
        explain_cmd,
        demo_cmd,
        plan_cmd,
        history_cmd,
        show_cmd,
        plan_version_cmd,
    )
