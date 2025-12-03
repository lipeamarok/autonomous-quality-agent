"""
================================================================================
Comando: aqa run — Executa Plano de Teste
================================================================================

Este comando executa um plano UTDL usando o Runner Rust.

## Modos de operação:

1. **Executar plano existente:**
   ```bash
   aqa run plan.json
   ```

2. **Gerar e executar (fluxo completo):**
   ```bash
   aqa run --swagger api.yaml
   aqa run --requirement "Testar login"
   ```

## Opções de saída:

- `--report FILE` → Salva relatório JSON
- `--parallel` → Executa steps em paralelo (DAG)
- `--timeout 60` → Timeout global em segundos
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from ...generator import UTDLGenerator
from ...ingestion import parse_openapi
from ...ingestion.swagger import spec_to_requirement_text
from ...runner import run_plan, RunnerResult
from ...validator import UTDLValidator, Plan
from ..utils import load_config, get_default_model


@click.command()
@click.argument(
    "plan_file",
    type=click.Path(exists=True),
    required=False,
)
@click.option(
    "--swagger", "-s",
    type=click.Path(exists=True),
    help="Gera plano a partir de spec OpenAPI e executa"
)
@click.option(
    "--requirement", "-r",
    type=str,
    help="Gera plano a partir de descrição e executa"
)
@click.option(
    "--base-url", "-u",
    type=str,
    help="URL base da API"
)
@click.option(
    "--model", "-m",
    type=str,
    help="Modelo LLM para geração"
)
@click.option(
    "--report", "-o",
    type=click.Path(),
    help="Salva relatório de execução neste arquivo"
)
@click.option(
    "--save-plan", "-p",
    type=click.Path(),
    help="Salva plano gerado (quando usando --swagger/--requirement)"
)
@click.option(
    "--parallel",
    is_flag=True,
    help="Executa steps em paralelo (modo DAG)"
)
@click.option(
    "--timeout",
    type=int,
    default=300,
    help="Timeout global em segundos (padrão: 300)"
)
@click.pass_context
def run(
    ctx: click.Context,
    plan_file: str | None,
    swagger: str | None,
    requirement: str | None,
    base_url: str | None,
    model: str | None,
    report: str | None,
    save_plan: str | None,
    parallel: bool,
    timeout: int,
) -> None:
    """
    Executa um plano de teste UTDL.

    \b
    Modos de uso:
      aqa run plan.json           # Executa plano existente
      aqa run --swagger api.yaml  # Gera e executa
      aqa run -r "Testar login"   # Gera e executa
    """
    console: Console = ctx.obj["console"]
    verbose: bool = ctx.obj["verbose"]
    _ = verbose  # Used for future verbose output

    # Valida argumentos
    if not plan_file and not swagger and not requirement:
        console.print(
            "[red]❌ Forneça um arquivo de plano ou --swagger/--requirement[/red]"
        )
        raise SystemExit(1)

    if plan_file and (swagger or requirement):
        console.print(
            "[red]❌ Não combine arquivo de plano com --swagger/--requirement[/red]"
        )
        raise SystemExit(1)

    # Carrega configuração
    config = load_config()
    final_model = model or config.get("model") or get_default_model()
    final_base_url = base_url or config.get("base_url", "https://api.example.com")

    # =========================================================================
    # MODO 1: Plano existente
    # =========================================================================
    if plan_file:
        plan_path = Path(plan_file)
        console.print(f"📄 Carregando plano: [cyan]{plan_path.name}[/cyan]")

        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ JSON inválido: {e}[/red]")
            raise SystemExit(1)

        # Valida antes de executar
        validator = UTDLValidator()
        validation = validator.validate(plan_data)
        
        if not validation.is_valid:
            console.print("[red]❌ Plano inválido:[/red]")
            for error in validation.errors:
                console.print(f"  • {error}")
            raise SystemExit(1)

        # Converte dict → objeto Plan
        plan = Plan.model_validate(plan_data)

    # =========================================================================
    # MODO 2: Gerar e executar
    # =========================================================================
    else:
        # Obtém requisito
        if swagger:
            console.print(f"📖 Parseando spec: [cyan]{swagger}[/cyan]")
            spec = parse_openapi(swagger)
            requirement_text = spec_to_requirement_text(spec)
            if "base_url" in spec and spec["base_url"]:
                final_base_url = spec["base_url"]
        else:
            requirement_text = requirement  # type: ignore

        # Gera plano
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]🧠 Gerando plano com {final_model}...[/cyan]"
            )

            try:
                generator = UTDLGenerator()
                plan = generator.generate(str(requirement_text), final_base_url)
                progress.update(task, completed=True)
            except Exception as e:
                progress.stop()
                console.print(f"[red]❌ Erro na geração: {e}[/red]")
                raise SystemExit(1)

        # Salva plano se solicitado
        if save_plan:
            Path(save_plan).write_text(plan.to_json(), encoding="utf-8")
            console.print(f"📄 Plano salvo em: [cyan]{save_plan}[/cyan]")

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================
    
    console.print()
    console.print(Panel(
        f"[bold]{plan.meta.name}[/bold]\n"
        f"[dim]{plan.meta.description or 'Sem descrição'}[/dim]\n\n"
        f"Steps: {len(plan.steps)} | "
        f"Modo: {'Paralelo' if parallel else 'Sequencial'}",
        title="🚀 Executando Plano",
        border_style="blue",
    ))
    console.print()

    # Executa
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Executando steps...[/cyan]",
                total=len(plan.steps)
            )
            
            result: RunnerResult = run_plan(plan)
            progress.update(task, completed=len(plan.steps))

    except RuntimeError as e:
        console.print(f"[red]❌ Erro de execução: {e}[/red]")
        raise SystemExit(1)

    # =========================================================================
    # RESULTADOS
    # =========================================================================

    console.print()

    # Tabela de resultados por step
    table = Table(title="Resultados dos Steps")
    table.add_column("Step", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duração", justify="right")
    table.add_column("Erro", style="dim")

    for step_result in result.steps:
        status_icon = {
            "passed": "[green]✅ PASS[/green]",
            "failed": "[red]❌ FAIL[/red]",
            "skipped": "[yellow]⏭️ SKIP[/yellow]",
            "error": "[red]💥 ERROR[/red]",
        }.get(step_result.status, step_result.status)

        duration = f"{step_result.duration_ms:.0f}ms"
        error_msg = step_result.error or ""
        error_msg = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg

        table.add_row(
            step_result.step_id,
            status_icon,
            duration,
            error_msg,
        )

    console.print(table)
    console.print()

    # Resumo
    summary = result.summary()
    if result.success:
        console.print(Panel(
            f"[green]{summary}[/green]",
            title="✅ Todos os testes passaram",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]{summary}[/red]",
            title="❌ Alguns testes falharam",
            border_style="red",
        ))

    # Salva relatório
    if report:
        report_path = Path(report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(result.raw_report, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        console.print(f"\n📊 Relatório salvo em: [cyan]{report}[/cyan]")

    # Exit code
    raise SystemExit(0 if result.success else 1)
