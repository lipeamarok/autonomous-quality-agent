"""
================================================================================
Comando: aqa explain — Explica Plano UTDL
================================================================================

Este comando mostra uma explicação legível de um plano UTDL,
traduzindo a estrutura JSON para linguagem natural.

## Uso:

```bash
# Explica um plano
aqa explain plan.json

# Formato detalhado
aqa explain plan.json --detailed

# Saída JSON (para processamento)
aqa --json explain plan.json
```
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel


def _explain_step(step: dict[str, Any], index: int) -> str:
    """Gera explicação textual de um step."""
    step_id = step.get("id", f"step_{index}")
    action = step.get("action", "unknown")
    description = step.get("description", "")

    params = step.get("params", {})
    method = params.get("method", "GET")
    path = params.get("path", "/")

    lines: list[str] = []
    lines.append(f"📍 **Step {index + 1}: {step_id}**")

    if description:
        lines.append(f"   {description}")

    if action == "http_request":
        lines.append(f"   Faz requisição {method} para `{path}`")

        if params.get("body"):
            lines.append("   Envia body JSON")

        if params.get("headers"):
            lines.append(f"   Com {len(params['headers'])} header(s) customizado(s)")

    elif action in ("wait", "sleep"):
        duration = params.get("duration_ms", params.get("ms", 0))
        lines.append(f"   Aguarda {duration}ms")

    # Assertions
    assertions = step.get("assertions", [])
    if assertions:
        lines.append(f"   ✓ Verifica {len(assertions)} assertion(s)")

    # Extractions
    extracts = step.get("extract", [])
    if extracts:
        targets = [e.get("target", "?") for e in extracts]
        lines.append(f"   📤 Extrai: {', '.join(targets)}")

    # Dependencies
    deps = step.get("depends_on", [])
    if deps:
        lines.append(f"   ⏳ Depende de: {', '.join(deps)}")

    return "\n".join(lines)


def _explain_plan_json(plan: dict[str, Any]) -> dict[str, Any]:
    """Gera explicação em formato JSON."""
    meta = plan.get("meta", {})
    config = plan.get("config", {})
    steps = plan.get("steps", [])

    return {
        "plan": {
            "id": meta.get("id", "unknown"),
            "name": meta.get("name", "Untitled"),
            "description": meta.get("description", ""),
        },
        "config": {
            "base_url": config.get("base_url", ""),
            "variables_count": len(config.get("variables", {})),
        },
        "steps": [
            {
                "index": i + 1,
                "id": s.get("id", f"step_{i}"),
                "action": s.get("action", "unknown"),
                "description": s.get("description", ""),
                "has_assertions": len(s.get("assertions", [])) > 0,
                "has_extractions": len(s.get("extract", [])) > 0,
                "depends_on": s.get("depends_on", []),
            }
            for i, s in enumerate(steps)
        ],
        "summary": {
            "total_steps": len(steps),
            "http_requests": sum(1 for s in steps if s.get("action") == "http_request"),
            "waits": sum(1 for s in steps if s.get("action") in ("wait", "sleep")),
        },
    }


@click.command()
@click.argument(
    "file",
    type=click.Path(exists=True),
    required=True,
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Mostra detalhes completos de cada step",
)
@click.pass_context
def explain(ctx: click.Context, file: str, detailed: bool) -> None:
    """
    Explica um plano UTDL em linguagem natural.

    Traduz a estrutura JSON para uma descrição legível,
    mostrando o que cada step faz e como se relacionam.
    """
    console: Console = ctx.obj["console"]
    json_output: bool = ctx.obj.get("json_output", False)

    path = Path(file)

    try:
        content = path.read_text(encoding="utf-8")
        plan = json.loads(content)
    except json.JSONDecodeError as e:
        if json_output:
            Console().print_json(data={"error": f"JSON inválido: {e}"})
        else:
            console.print(f"[red]❌ JSON inválido: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        if json_output:
            Console().print_json(data={"error": str(e)})
        else:
            console.print(f"[red]❌ Erro: {e}[/red]")
        raise SystemExit(1)

    # Saída JSON
    if json_output:
        Console().print_json(data=_explain_plan_json(plan))
        return

    # Saída formatada
    meta = plan.get("meta", {})
    config = plan.get("config", {})
    steps = plan.get("steps", [])

    # Header
    console.print()
    console.print(Panel(
        f"[bold cyan]{meta.get('name', 'Plano UTDL')}[/bold cyan]\n"
        f"[dim]{meta.get('description', '')}[/dim]",
        title="📋 Explicação do Plano",
        border_style="cyan",
    ))

    # Config
    console.print()
    console.print(f"[bold]🌐 Base URL:[/bold] {config.get('base_url', 'N/A')}")

    variables = config.get("variables", {})
    if variables:
        console.print(f"[bold]📦 Variáveis:[/bold] {len(variables)} definida(s)")
        if detailed:
            for k, v in variables.items():
                val_str = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
                console.print(f"   • {k} = {val_str}")

    # Steps
    console.print()
    console.print(f"[bold]📝 Steps ({len(steps)}):[/bold]")
    console.print()

    for i, step in enumerate(steps):
        explanation = _explain_step(step, i)
        console.print(explanation)
        console.print()

    # Summary
    http_count = sum(1 for s in steps if s.get("action") == "http_request")
    wait_count = sum(1 for s in steps if s.get("action") in ("wait", "sleep"))

    console.print(Panel(
        f"[bold]Total:[/bold] {len(steps)} steps\n"
        f"[bold]HTTP Requests:[/bold] {http_count}\n"
        f"[bold]Waits:[/bold] {wait_count}",
        title="📊 Resumo",
        border_style="green",
    ))
