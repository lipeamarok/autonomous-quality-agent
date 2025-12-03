"""
================================================================================
Comando: aqa validate — Valida Plano UTDL
================================================================================

Este comando valida a sintaxe e semântica de um plano UTDL.

## Validações realizadas:
- Estrutura JSON válida
- Campos obrigatórios presentes
- Dependências entre steps válidas (sem ciclos)
- Actions suportadas pelo Runner
- Parâmetros de assertions corretos

## Uso:

```bash
# Valida um arquivo
aqa validate plan.json

# Valida múltiplos arquivos
aqa validate plans/*.json

# Modo strict (erros em warnings)
aqa validate --strict plan.json
```
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ...validator import UTDLValidator


@click.command()
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--strict",
    is_flag=True,
    help="Trata warnings como erros"
)
@click.pass_context
def validate(
    ctx: click.Context,
    files: tuple[str, ...],
    strict: bool,
) -> None:
    """
    Valida um ou mais planos UTDL.

    Verifica sintaxe JSON, campos obrigatórios, dependências
    entre steps e parâmetros de assertions.
    """
    console: Console = ctx.obj["console"]
    verbose: bool = ctx.obj["verbose"]

    validator = UTDLValidator()
    all_valid = True
    total_errors = 0
    total_warnings = 0

    # Processa cada arquivo
    for file_path in files:
        path = Path(file_path)
        console.print(f"\n🔍 Validando: [cyan]{path.name}[/cyan]")

        try:
            # Carrega JSON
            content = path.read_text(encoding="utf-8")
            plan_data = json.loads(content)

            # Valida
            result = validator.validate(plan_data)

            if result.is_valid:
                if result.warnings:
                    console.print(f"  [yellow]⚠️  Válido com {len(result.warnings)} warning(s)[/yellow]")
                    total_warnings += len(result.warnings)
                    if verbose:
                        for warning in result.warnings:
                            console.print(f"    [dim]• {warning}[/dim]")
                    if strict:
                        all_valid = False
                else:
                    console.print("  [green]✅ Válido[/green]")
            else:
                console.print(f"  [red]❌ Inválido ({len(result.errors)} erro(s))[/red]")
                all_valid = False
                total_errors += len(result.errors)
                
                # Mostra erros
                for error in result.errors:
                    console.print(f"    [red]• {error}[/red]")

        except json.JSONDecodeError as e:
            console.print(f"  [red]❌ JSON inválido: {e}[/red]")
            all_valid = False
            total_errors += 1

        except Exception as e:
            console.print(f"  [red]❌ Erro ao ler arquivo: {e}[/red]")
            all_valid = False
            total_errors += 1

    # Resumo final
    console.print()
    
    if all_valid:
        if total_warnings > 0:
            console.print(Panel(
                f"[yellow]Validação concluída com {total_warnings} warning(s)[/yellow]",
                border_style="yellow",
            ))
        else:
            console.print(Panel(
                "[green]✅ Todos os planos são válidos![/green]",
                border_style="green",
            ))
    else:
        console.print(Panel(
            f"[red]❌ Validação falhou: {total_errors} erro(s), {total_warnings} warning(s)[/red]",
            border_style="red",
        ))
        raise SystemExit(1)
