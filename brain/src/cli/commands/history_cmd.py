"""
================================================================================
Comando: aqa history — Visualiza Histórico de Execuções
================================================================================

Este comando permite visualizar e analisar o histórico de execuções de testes.

## Uso:

```bash
# Lista últimas 10 execuções
aqa history

# Lista mais execuções
aqa history --limit 20

# Filtra por status
aqa history --status failure

# Mostra detalhes de uma execução específica
aqa history show abc123

# Mostra estatísticas
aqa history stats
```
"""

from __future__ import annotations

from datetime import datetime
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...cache import ExecutionHistory
from ...config import BrainConfig


def _get_history() -> ExecutionHistory:
    """Obtém instância de ExecutionHistory configurada."""
    config = BrainConfig.from_env()
    return config.get_history()


def _format_timestamp(ts: str) -> str:
    """Formata timestamp para exibição amigável."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return ts


def _format_duration(ms: int) -> str:
    """Formata duração em formato amigável."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000
        return f"{minutes}m{seconds:.0f}s"


@click.group(invoke_without_command=True)
@click.option(
    "--limit", "-n",
    type=int,
    default=10,
    help="Número de execuções a exibir (padrão: 10)"
)
@click.option(
    "--status", "-s",
    type=click.Choice(["success", "failure", "error"]),
    default=None,
    help="Filtrar por status"
)
@click.pass_context
def history(ctx: click.Context, limit: int, status: str | None) -> None:
    """
    Visualiza histórico de execuções de testes.

    \b
    Exemplos:
      aqa history                  # Lista últimas 10 execuções
      aqa history -n 20            # Lista últimas 20
      aqa history -s failure       # Apenas falhas
      aqa history show abc123      # Detalhes de uma execução
      aqa history stats            # Estatísticas gerais
    """
    # Se nenhum subcomando, lista execuções
    if ctx.invoked_subcommand is None:
        console: Console = ctx.obj["console"]
        verbose: bool = ctx.obj["verbose"]
        json_output: bool = ctx.obj.get("json_output", False)

        hist = _get_history()

        if not hist.enabled:
            console.print("[yellow]⚠️ Histórico de execuções está desabilitado[/yellow]")
            return

        # Obtém registros
        if status:
            records = hist.get_by_status(status, limit=limit)  # type: ignore
        else:
            records = hist.get_recent(limit=limit)

        if not records:
            console.print("[dim]Nenhuma execução encontrada[/dim]")
            return

        # Modo JSON
        if json_output:
            console.print_json(data={"executions": records})
            return

        # Tabela de execuções
        table = Table(title=f"📊 Histórico de Execuções (últimas {len(records)})")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Data/Hora", style="dim")
        table.add_column("Plano", max_width=30)
        table.add_column("Status", justify="center")
        table.add_column("Steps", justify="right")
        table.add_column("Duração", justify="right")

        for record in records:
            status_icon = {
                "success": "[green]✅ OK[/green]",
                "failure": "[red]❌ FAIL[/red]",
                "error": "[red]💥 ERR[/red]",
            }.get(record.get("status", ""), record.get("status", ""))

            steps_str = f"{record.get('passed_steps', 0)}/{record.get('total_steps', 0)}"
            plan_name = record.get("plan_file", "")
            if len(plan_name) > 28:
                plan_name = "..." + plan_name[-25:]

            table.add_row(
                record.get("id", ""),
                _format_timestamp(record.get("timestamp", "")),
                plan_name,
                status_icon,
                steps_str,
                _format_duration(record.get("duration_ms", 0)),
            )

        console.print(table)

        if verbose:
            stats = hist.stats()
            console.print(f"\n[dim]Total: {stats.get('total_records', 0)} execuções | "
                         f"Sucesso: {stats.get('success_count', 0)} | "
                         f"Falhas: {stats.get('failure_count', 0)}[/dim]")


@history.command()
@click.argument("execution_id")
@click.pass_context
def show(ctx: click.Context, execution_id: str) -> None:
    """
    Mostra detalhes de uma execução específica.

    \b
    Exemplo:
      aqa history show abc123
    """
    console: Console = ctx.obj["console"]
    json_output: bool = ctx.obj.get("json_output", False)

    hist = _get_history()
    record = hist.get_full_record(execution_id)

    if not record:
        console.print(f"[red]❌ Execução '{execution_id}' não encontrada[/red]")
        raise SystemExit(1)

    # Modo JSON
    if json_output:
        console.print_json(data=record)
        return

    # Painel com informações básicas
    status_color = "green" if record.get("status") == "success" else "red"
    console.print(Panel(
        f"[bold]ID:[/bold] {record.get('id', '')}\n"
        f"[bold]Data:[/bold] {_format_timestamp(record.get('timestamp', ''))}\n"
        f"[bold]Plano:[/bold] {record.get('plan_file', '')}\n"
        f"[bold]Status:[/bold] [{status_color}]{record.get('status', '').upper()}[/{status_color}]\n"
        f"[bold]Duração:[/bold] {_format_duration(record.get('duration_ms', 0))}\n"
        f"[bold]Steps:[/bold] {record.get('passed_steps', 0)} passed / "
        f"{record.get('failed_steps', 0)} failed / {record.get('total_steps', 0)} total",
        title="📋 Detalhes da Execução",
        border_style="blue",
    ))

    # Se há runner_report, mostra detalhes dos steps
    runner_report = record.get("runner_report")
    if runner_report and "step_results" in runner_report:
        console.print()
        table = Table(title="Resultados dos Steps")
        table.add_column("Step ID", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duração", justify="right")
        table.add_column("Erro", style="dim", max_width=50)

        for step in runner_report["step_results"]:
            status_icon = {
                "passed": "[green]✅ PASS[/green]",
                "failed": "[red]❌ FAIL[/red]",
                "skipped": "[yellow]⏭️ SKIP[/yellow]",
            }.get(step.get("status", ""), step.get("status", ""))

            error = step.get("error", "") or ""
            if len(error) > 47:
                error = error[:44] + "..."

            table.add_row(
                step.get("step_id", ""),
                status_icon,
                _format_duration(step.get("duration_ms", 0)),
                error,
            )

        console.print(table)


@history.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """
    Mostra estatísticas do histórico de execuções.

    \b
    Exemplo:
      aqa history stats
    """
    console: Console = ctx.obj["console"]
    json_output: bool = ctx.obj.get("json_output", False)

    hist = _get_history()
    statistics = hist.stats()

    # Modo JSON
    if json_output:
        console.print_json(data=statistics)
        return

    if not statistics.get("enabled"):
        console.print("[yellow]⚠️ Histórico de execuções está desabilitado[/yellow]")
        return

    total = statistics.get("total_records", 0)
    success = statistics.get("success_count", 0)
    failure = statistics.get("failure_count", 0)
    error = statistics.get("error_count", 0)

    # Calcula porcentagens
    success_pct = (success / total * 100) if total > 0 else 0
    failure_pct = (failure / total * 100) if total > 0 else 0
    error_pct = (error / total * 100) if total > 0 else 0

    console.print(Panel(
        f"[bold]Total de Execuções:[/bold] {total}\n\n"
        f"[green]✅ Sucesso:[/green] {success} ({success_pct:.1f}%)\n"
        f"[red]❌ Falhas:[/red] {failure} ({failure_pct:.1f}%)\n"
        f"[red]💥 Erros:[/red] {error} ({error_pct:.1f}%)\n\n"
        f"[dim]Diretório: {statistics.get('history_dir', '')}[/dim]",
        title="📊 Estatísticas do Histórico",
        border_style="blue",
    ))


@history.command()
@click.option("--force", "-f", is_flag=True, help="Não pedir confirmação")
@click.pass_context
def clear(ctx: click.Context, force: bool) -> None:
    """
    Limpa o histórico de execuções.

    \b
    Exemplo:
      aqa history clear
      aqa history clear --force
    """
    console: Console = ctx.obj["console"]

    if not force:
        if not click.confirm("Deseja realmente limpar todo o histórico?"):
            console.print("[dim]Operação cancelada[/dim]")
            return

    hist = _get_history()
    stats_before = hist.stats()
    total_before = stats_before.get("total_records", 0)

    # Limpa o índice (registros antigos serão órfãos mas ocupam pouco espaço)
    import shutil
    if hist.history_dir.exists():
        shutil.rmtree(hist.history_dir)
        hist.clear_all()

    console.print(f"[green]✅ Histórico limpo: {total_before} registros removidos[/green]")
