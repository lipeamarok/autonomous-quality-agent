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

# Saída JSON para CI
aqa --json validate plan.json
```
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel

from ...adapter import SmartFormatAdapter
from ...validator import UTDLValidator
from ..registry import register_command


# Console para saída JSON (não silenciável)
_json_console = Console()


def _print_json_validation_result(results: list[dict[str, Any]], all_valid: bool) -> None:
    """Imprime resultado de validação em formato JSON."""
    output: dict[str, Any] = {
        "success": all_valid,
        "files": results,
        "summary": {
            "total": len(results),
            "valid": sum(1 for r in results if r["valid"]),
            "invalid": sum(1 for r in results if not r["valid"]),
        },
    }
    _json_console.print_json(data=output)


@register_command
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
@click.option(
    "--normalize",
    is_flag=True,
    help="Normaliza automaticamente formatos alternativos (tests→steps, status→status_code, etc.)"
)
@click.pass_context
def validate(
    ctx: click.Context,
    files: tuple[str, ...],
    strict: bool,
    normalize: bool,
) -> None:
    """
    Valida um ou mais planos UTDL.

    Verifica sintaxe JSON, campos obrigatórios, dependências
    entre steps e parâmetros de assertions.
    """
    console: Console = ctx.obj["console"]
    verbose: bool = ctx.obj["verbose"]
    json_output: bool = ctx.obj.get("json_output", False)
    quiet: bool = ctx.obj.get("quiet", False)

    validator = UTDLValidator()
    adapter = SmartFormatAdapter() if normalize else None
    all_valid = True
    total_errors = 0
    total_warnings = 0
    json_results: list[dict[str, Any]] = []

    # Processa cada arquivo
    for file_path in files:
        path = Path(file_path)
        file_result: dict[str, Any] = {"file": str(path), "valid": False, "errors": [], "warnings": []}

        if not quiet and not json_output:
            console.print(f"\n🔍 Validando: [cyan]{path.name}[/cyan]")

        try:
            # Carrega e opcionalmente normaliza
            if adapter:
                try:
                    plan_data = adapter.load_and_normalize(path)
                    if not quiet and not json_output:
                        console.print("  [dim]📐 Formato normalizado[/dim]")
                except ValueError as e:
                    raise ValueError(f"Erro ao normalizar: {e}")
            else:
                content = path.read_text(encoding="utf-8")
                plan_data = json.loads(content)

            # Valida
            result = validator.validate(plan_data)

            if result.is_valid:
                file_result["valid"] = True
                file_result["warnings"] = result.warnings

                if result.warnings:
                    total_warnings += len(result.warnings)
                    if strict:
                        all_valid = False
                        file_result["valid"] = False

                    if not quiet and not json_output:
                        console.print(f"  [yellow]⚠️  Válido com {len(result.warnings)} warning(s)[/yellow]")
                        if verbose:
                            for warning in result.warnings:
                                console.print(f"    [dim]• {warning}[/dim]")
                else:
                    if not quiet and not json_output:
                        console.print("  [green]✅ Válido[/green]")
            else:
                file_result["valid"] = False
                file_result["errors"] = result.errors
                all_valid = False
                total_errors += len(result.errors)

                if not quiet and not json_output:
                    console.print(f"  [red]❌ Inválido ({len(result.errors)} erro(s))[/red]")
                    for error in result.errors:
                        console.print(f"    [red]• {error}[/red]")

        except json.JSONDecodeError as e:
            file_result["errors"] = [f"JSON inválido: {e}"]
            all_valid = False
            total_errors += 1

            if not quiet and not json_output:
                console.print(f"  [red]❌ JSON inválido: {e}[/red]")

        except Exception as e:
            file_result["errors"] = [f"Erro ao ler arquivo: {e}"]
            all_valid = False
            total_errors += 1

            if not quiet and not json_output:
                console.print(f"  [red]❌ Erro ao ler arquivo: {e}[/red]")

        json_results.append(file_result)

    # Saída JSON
    if json_output:
        _print_json_validation_result(json_results, all_valid)
        raise SystemExit(0 if all_valid else 1)

    # Resumo final (modo normal)
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
