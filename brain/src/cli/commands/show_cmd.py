"""
================================================================================
Comando: aqa show — Visualiza Planos de Teste
================================================================================

Este comando permite visualizar, analisar e comparar planos UTDL.

## Uso:

```bash
# Mostra resumo do plano
aqa show plan.json

# Mostra steps detalhados
aqa show plan.json --steps

# Mostra apenas endpoints críticos
aqa show plan.json --critical

# Compara dois planos (diff)
aqa show plan1.json --diff plan2.json

# Lista apenas steps que fazem POST/PUT/DELETE
aqa show plan.json --methods POST,PUT,DELETE
```
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.tree import Tree

from ...adapter import SmartFormatAdapter
from ...validator import UTDLValidator, Plan


def _load_plan(path: Path, normalize: bool = True) -> tuple[Plan, dict[str, Any]]:
    """Carrega e valida um plano."""
    if normalize:
        adapter = SmartFormatAdapter()
        plan_data = adapter.load_and_normalize(path)
    else:
        plan_data = json.loads(path.read_text(encoding="utf-8"))

    validator = UTDLValidator()
    validation = validator.validate(plan_data)

    if not validation.is_valid:
        raise ValueError(f"Plano inválido: {', '.join(validation.errors)}")

    plan = Plan.model_validate(plan_data)
    return plan, plan_data


def _get_step_method(step: Any) -> str:
    """Extrai método HTTP de um step."""
    action = step.action if hasattr(step, "action") else step.get("action", {})
    if isinstance(action, dict):
        action_dict = cast(dict[str, Any], action)
        method = action_dict.get("method", "GET")
        return str(method).upper() if method else "GET"
    elif hasattr(action, "method"):
        return (action.method or "GET").upper()
    return "GET"


def _get_step_endpoint(step: Any) -> str:
    """Extrai endpoint de um step."""
    action = step.action if hasattr(step, "action") else step.get("action", {})
    if isinstance(action, dict):
        action_dict = cast(dict[str, Any], action)
        endpoint = action_dict.get("endpoint") or action_dict.get("path") or ""
        return str(endpoint)
    elif hasattr(action, "endpoint"):
        return action.endpoint or ""
    return ""


def _is_critical_method(method: str) -> bool:
    """Verifica se método é considerado crítico (mutação)."""
    return method.upper() in ("POST", "PUT", "DELETE", "PATCH")


@click.command()
@click.argument(
    "plan_file",
    type=click.Path(exists=True),
)
@click.option(
    "--steps", "-s",
    is_flag=True,
    help="Mostra detalhes de cada step"
)
@click.option(
    "--critical", "-c",
    is_flag=True,
    help="Mostra apenas endpoints críticos (POST/PUT/DELETE/PATCH)"
)
@click.option(
    "--methods", "-m",
    type=str,
    default=None,
    help="Filtra por métodos HTTP (ex: 'GET,POST')"
)
@click.option(
    "--diff", "-d",
    type=click.Path(exists=True),
    default=None,
    help="Compara com outro plano"
)
@click.option(
    "--raw",
    is_flag=True,
    help="Mostra JSON bruto"
)
@click.option(
    "--normalize/--no-normalize",
    default=True,
    help="Normaliza formato antes de exibir (padrão: sim)"
)
@click.pass_context
def show(
    ctx: click.Context,
    plan_file: str,
    steps: bool,
    critical: bool,
    methods: str | None,
    diff: str | None,
    raw: bool,
    normalize: bool,
) -> None:
    """
    Visualiza um plano de teste UTDL.

    \b
    Exemplos:
      aqa show plan.json              # Resumo do plano
      aqa show plan.json --steps      # Lista todos os steps
      aqa show plan.json --critical   # Apenas POST/PUT/DELETE
      aqa show plan.json --diff v2.json  # Compara planos
    """
    console: Console = ctx.obj["console"]
    verbose: bool = ctx.obj["verbose"]
    json_output: bool = ctx.obj.get("json_output", False)

    try:
        plan, plan_data = _load_plan(Path(plan_file), normalize=normalize)
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)

    # Modo diff
    if diff:
        _show_diff(console, plan, plan_data, Path(diff), normalize)
        return

    # Modo JSON raw
    if raw:
        if json_output:
            console.print_json(data=plan_data)
        else:
            syntax = Syntax(
                json.dumps(plan_data, indent=2, ensure_ascii=False),
                "json",
                theme="monokai",
                line_numbers=True,
            )
            console.print(syntax)
        return

    # Modo JSON estruturado
    if json_output:
        output: dict[str, object] = {
            "meta": {
                "id": plan.meta.id,
                "name": plan.meta.name,
                "description": plan.meta.description,
                "tags": plan.meta.tags,
                "created_at": plan.meta.created_at,
            },
            "config": {
                "base_url": plan.config.base_url,
            },
            "steps_count": len(plan.steps),
            "steps": [
                {
                    "id": s.id,
                    "method": _get_step_method(s),
                    "endpoint": _get_step_endpoint(s),
                    "description": getattr(s, "description", None),
                }
                for s in plan.steps
            ],
        }
        console.print_json(data=output)
        return

    # Filtra steps se necessário
    filtered_steps = list(plan.steps)

    if critical:
        filtered_steps = [s for s in filtered_steps if _is_critical_method(_get_step_method(s))]

    if methods:
        allowed_methods = [m.strip().upper() for m in methods.split(",")]
        filtered_steps = [s for s in filtered_steps if _get_step_method(s) in allowed_methods]

    # Painel com metadados
    tags_str = ", ".join(plan.meta.tags) if plan.meta.tags else "N/A"
    console.print(Panel(
        f"[bold]ID:[/bold] {plan.meta.id}\n"
        f"[bold]Nome:[/bold] {plan.meta.name}\n"
        f"[bold]Descrição:[/bold] {plan.meta.description or 'N/A'}\n"
        f"[bold]Tags:[/bold] {tags_str}\n"
        f"[bold]Criado em:[/bold] {plan.meta.created_at}\n"
        f"[bold]Base URL:[/bold] {plan.config.base_url}\n"
        f"[bold]Total Steps:[/bold] {len(plan.steps)}"
        + (f" ([cyan]{len(filtered_steps)} filtrados[/cyan])" if len(filtered_steps) != len(plan.steps) else ""),
        title=f"📋 {plan_file}",
        border_style="blue",
    ))

    # Se não pediu steps detalhados, mostra resumo
    if not steps:
        # Estatísticas por método
        method_counts: dict[str, int] = {}
        for s in plan.steps:
            method = _get_step_method(s)
            method_counts[method] = method_counts.get(method, 0) + 1

        console.print()
        console.print("[bold]Distribuição por Método:[/bold]")
        for method, count in sorted(method_counts.items()):
            color = "red" if _is_critical_method(method) else "green"
            console.print(f"  [{color}]{method}[/{color}]: {count}")

        console.print()
        console.print("[dim]Use --steps para ver detalhes de cada step[/dim]")
        return

    # Tabela de steps
    console.print()
    table = Table(title=f"Steps ({len(filtered_steps)})")
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Método", justify="center", width=8)
    table.add_column("Endpoint", max_width=40)
    table.add_column("Descrição", style="dim", max_width=30)

    for i, step in enumerate(filtered_steps, 1):
        method = _get_step_method(step)
        method_color = "red" if _is_critical_method(method) else "green"
        desc = getattr(step, "description", None) or ""
        if len(desc) > 27:
            desc = desc[:24] + "..."

        table.add_row(
            str(i),
            step.id,
            f"[{method_color}]{method}[/{method_color}]",
            _get_step_endpoint(step),
            desc,
        )

    console.print(table)

    # Mostra dependências se verbose
    if verbose:
        has_deps = False
        console.print()
        tree = Tree("📊 Dependências")

        for step in filtered_steps:
            deps_raw = getattr(step, "depends_on", None)
            deps: list[str] = list(deps_raw) if deps_raw else []
            if deps:
                has_deps = True
                step_node = tree.add(f"[cyan]{step.id}[/cyan]")
                for dep in deps:
                    step_node.add(f"← {dep}")

        if has_deps:
            console.print(tree)
        else:
            console.print("[dim]Nenhuma dependência entre steps[/dim]")


def _show_diff(
    console: Console,
    plan1: Plan,
    plan1_data: dict[str, Any],
    plan2_path: Path,
    normalize: bool,
) -> None:
    """Mostra diff entre dois planos."""
    try:
        plan2, _ = _load_plan(plan2_path, normalize=normalize)
    except ValueError as e:
        console.print(f"[red]❌ Erro no segundo plano: {e}[/red]")
        raise SystemExit(1)

    console.print(Panel(
        f"[bold]Plano 1:[/bold] {plan1.meta.name} ({len(plan1.steps)} steps)\n"
        f"[bold]Plano 2:[/bold] {plan2.meta.name} ({len(plan2.steps)} steps)",
        title="🔍 Comparação de Planos",
        border_style="blue",
    ))
    console.print()

    # IDs de steps em cada plano
    ids1 = {s.id for s in plan1.steps}
    ids2 = {s.id for s in plan2.steps}

    added = ids2 - ids1
    removed = ids1 - ids2
    common = ids1 & ids2

    # Steps adicionados
    if added:
        console.print("[green]✅ Steps adicionados:[/green]")
        for step_id in sorted(added):
            step = next(s for s in plan2.steps if s.id == step_id)
            console.print(f"  [green]+ {step_id}[/green] ({_get_step_method(step)} {_get_step_endpoint(step)})")
        console.print()

    # Steps removidos
    if removed:
        console.print("[red]❌ Steps removidos:[/red]")
        for step_id in sorted(removed):
            step = next(s for s in plan1.steps if s.id == step_id)
            console.print(f"  [red]- {step_id}[/red] ({_get_step_method(step)} {_get_step_endpoint(step)})")
        console.print()

    # Steps em comum (potencialmente modificados)
    if common:
        console.print(f"[dim]📋 {len(common)} steps em comum[/dim]")

    # Resumo
    console.print()
    if not added and not removed:
        console.print("[green]✅ Planos têm os mesmos steps[/green]")
    else:
        console.print(f"[bold]Resumo:[/bold] +{len(added)} / -{len(removed)} / ={len(common)}")
