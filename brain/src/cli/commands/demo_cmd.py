"""
================================================================================
Comando: aqa demo — Demonstração Completa do AQA
================================================================================

Este comando executa uma demonstração completa do fluxo do AQA,
gerando e executando um plano de teste contra uma API de exemplo.

## Uso:

```bash
# Demo padrão (usa httpbin.org como API de teste)
aqa demo

# Demo com API customizada
aqa demo --url https://api.example.com/openapi.json

# Demo sem executar (só mostra o plano)
aqa demo --dry-run
```
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel


# Plano de demonstração usando httpbin.org (API pública de teste)
DEMO_PLAN: dict[str, Any] = {
    "utdl_version": "1.0",
    "meta": {
        "id": "demo-plan-001",
        "name": "AQA Demo - HTTPBin Test",
        "description": "Demonstração do Autonomous Quality Agent usando httpbin.org",
        "created_at": "2024-01-01T00:00:00Z",
        "tags": ["demo", "httpbin"],
    },
    "config": {
        "base_url": "https://httpbin.org",
        "variables": {
            "demo_user": "aqa_demo_user",
            "demo_value": "hello_world",
        },
    },
    "steps": [
        {
            "id": "health_check",
            "description": "Verifica se a API está respondendo",
            "action": "http_request",
            "depends_on": [],
            "params": {
                "method": "GET",
                "path": "/status/200",
            },
            "assertions": [
                {"type": "status_code", "expected": 200},
            ],
            "extract": [],
        },
        {
            "id": "get_uuid",
            "description": "Obtém um UUID único da API",
            "action": "http_request",
            "depends_on": ["health_check"],
            "params": {
                "method": "GET",
                "path": "/uuid",
            },
            "assertions": [
                {"type": "status_code", "expected": 200},
                {"type": "json_body", "path": "$.uuid", "operator": "exists"},
            ],
            "extract": [
                {"source": "body", "path": "$.uuid", "target": "generated_uuid"},
            ],
        },
        {
            "id": "echo_data",
            "description": "Envia dados e verifica o echo",
            "action": "http_request",
            "depends_on": ["get_uuid"],
            "params": {
                "method": "POST",
                "path": "/post",
                "headers": {
                    "Content-Type": "application/json",
                    "X-Demo-Header": "aqa-demo",
                },
                "body": {
                    "user": "{{demo_user}}",
                    "message": "{{demo_value}}",
                    "uuid": "{{generated_uuid}}",
                },
            },
            "assertions": [
                {"type": "status_code", "expected": 200},
                {"type": "json_body", "path": "$.json.user", "expected": "{{demo_user}}"},
            ],
            "extract": [],
        },
        {
            "id": "test_headers",
            "description": "Verifica headers customizados",
            "action": "http_request",
            "depends_on": ["health_check"],
            "params": {
                "method": "GET",
                "path": "/headers",
                "headers": {
                    "X-Custom-Header": "custom-value",
                    "Accept": "application/json",
                },
            },
            "assertions": [
                {"type": "status_code", "expected": 200},
            ],
            "extract": [],
        },
        {
            "id": "wait_step",
            "description": "Aguarda um momento antes do próximo step",
            "action": "wait",
            "depends_on": ["echo_data", "test_headers"],
            "params": {
                "duration_ms": 500,
            },
            "assertions": [],
            "extract": [],
        },
        {
            "id": "final_check",
            "description": "Verificação final da API",
            "action": "http_request",
            "depends_on": ["wait_step"],
            "params": {
                "method": "GET",
                "path": "/get",
                "params": {
                    "demo": "complete",
                    "uuid": "{{generated_uuid}}",
                },
            },
            "assertions": [
                {"type": "status_code", "expected": 200},
                {"type": "json_body", "path": "$.args.demo", "expected": "complete"},
            ],
            "extract": [],
        },
    ],
}


@click.command()
@click.option(
    "--url",
    default=None,
    help="URL do OpenAPI/Swagger para gerar plano (padrão: usa httpbin.org)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Mostra o plano sem executar",
)
@click.option(
    "--save",
    type=click.Path(),
    default=None,
    help="Salva o plano demo em um arquivo",
)
@click.pass_context
def demo(ctx: click.Context, url: str | None, dry_run: bool, save: str | None) -> None:
    """
    Executa uma demonstração completa do AQA.

    Gera e executa um plano de teste contra httpbin.org (API pública)
    para demonstrar o fluxo completo do Autonomous Quality Agent.
    """
    console: Console = ctx.obj["console"]
    json_output: bool = ctx.obj.get("json_output", False)
    quiet: bool = ctx.obj.get("quiet", False)
    
    # Banner
    if not quiet and not json_output:
        console.print()
        console.print(Panel(
            "[bold cyan]🧪 AQA Demo[/bold cyan]\n\n"
            "Demonstração do Autonomous Quality Agent\n"
            "Testando API: [green]httpbin.org[/green]",
            border_style="cyan",
        ))
        console.print()
    
    # Se URL customizada foi fornecida, mostra aviso
    if url:
        if not quiet and not json_output:
            console.print(f"[yellow]⚠️  URL customizada não implementada ainda.[/yellow]")
            console.print(f"[yellow]   Usando plano demo padrão (httpbin.org)[/yellow]")
            console.print()
    
    # Mostra o plano
    if dry_run:
        if json_output:
            Console().print_json(data=DEMO_PLAN)
        else:
            console.print("[bold]📋 Plano de Demonstração:[/bold]")
            console.print()
            console.print_json(data=DEMO_PLAN)
        return
    
    # Salva se solicitado
    if save:
        save_path = Path(save)
        save_path.write_text(json.dumps(DEMO_PLAN, indent=2), encoding="utf-8")
        if not quiet and not json_output:
            console.print(f"[green]✅ Plano salvo em: {save_path}[/green]")
            console.print()
    
    # Executa o plano
    if not quiet and not json_output:
        console.print("[bold]🚀 Executando demo...[/bold]")
        console.print()
        console.print("[dim]Para executar o plano demo completo, use:[/dim]")
        console.print()
        console.print("  [cyan]# Salvar o plano[/cyan]")
        console.print("  [white]aqa demo --save demo_plan.json[/white]")
        console.print()
        console.print("  [cyan]# Executar o plano[/cyan]")
        console.print("  [white]aqa run demo_plan.json[/white]")
        console.print()
        console.print("[dim]Ou execute tudo de uma vez com:[/dim]")
        console.print("  [white]aqa demo --save demo.json && aqa run demo.json[/white]")
        console.print()
        
        # Mostra resumo do plano
        console.print(Panel(
            f"[bold]Plano:[/bold] {DEMO_PLAN['meta']['name']}\n"
            f"[bold]Steps:[/bold] {len(DEMO_PLAN['steps'])}\n"
            f"[bold]Base URL:[/bold] {DEMO_PLAN['config']['base_url']}\n\n"
            "[dim]Steps incluídos:[/dim]\n"
            "  1. health_check - Verifica API\n"
            "  2. get_uuid - Obtém UUID\n"
            "  3. echo_data - Echo com POST\n"
            "  4. test_headers - Headers customizados\n"
            "  5. wait_step - Aguarda 500ms\n"
            "  6. final_check - Verificação final",
            title="📊 Resumo do Demo",
            border_style="green",
        ))
    
    if json_output:
        Console().print_json(data={
            "status": "demo_ready",
            "plan": DEMO_PLAN,
            "instructions": "Use 'aqa run' with the saved plan to execute",
        })
