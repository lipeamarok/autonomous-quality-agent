"""
================================================================================
Comando: aqa plan version — Gerenciar Versões de Planos
================================================================================

Este módulo implementa subcomandos para versionamento de planos de teste.

## Uso:

```bash
# Listar planos versionados
aqa plan list

# Ver versões de um plano
aqa plan versions my-api-tests

# Comparar duas versões
aqa plan diff my-api-tests 1 2

# Comparar versão com a atual
aqa plan diff my-api-tests 1

# Salvar versão atual de um plano
aqa plan save my-plan.json --name "my-api-tests" --description "Initial version"

# Ver plano da versão atual
aqa plan show my-api-tests

# Ver plano de versão específica
aqa plan show my-api-tests --version 1
```
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ...cache import PlanVersionStore, PlanDiff
from ..registry import register_command


def _get_store() -> PlanVersionStore:
    """Obtém instância de PlanVersionStore."""
    return PlanVersionStore.global_store()


def _format_diff_output(
    console: Console,
    diff: PlanDiff,
    plan_name: str,
    verbose: bool = False,
) -> None:
    """
    Formata e exibe o diff entre duas versões.

    ## Parâmetros:
        console: Console Rich para output
        diff: PlanDiff com as diferenças
        plan_name: Nome do plano
        verbose: Se True, mostra detalhes completos
    """
    # Header
    console.print()
    console.print(Panel.fit(
        f"[bold]Diff: {plan_name}[/]\n"
        f"[dim]v{diff.version_a} → v{diff.version_b}[/]",
        border_style="cyan",
    ))
    console.print()

    if not diff.has_changes:
        console.print("[green]✓ Nenhuma diferença encontrada[/]")
        return

    console.print(f"[bold]Resumo:[/] {diff.summary}")
    console.print()

    # Steps adicionados
    if diff.steps_added:
        console.print(f"[green]+ {len(diff.steps_added)} steps adicionados:[/]")
        for step in diff.steps_added:
            step_id = step.get("id", "?")
            step_name = step.get("name", "Unnamed")
            action = step.get("action", {})
            method = action.get("method", "")
            endpoint = action.get("endpoint", "")
            console.print(f"  [green]+[/] {step_id}: {step_name}")
            if verbose:
                console.print(f"      [dim]{method} {endpoint}[/]")
        console.print()

    # Steps removidos
    if diff.steps_removed:
        console.print(f"[red]- {len(diff.steps_removed)} steps removidos:[/]")
        for step in diff.steps_removed:
            step_id = step.get("id", "?")
            step_name = step.get("name", "Unnamed")
            console.print(f"  [red]-[/] {step_id}: {step_name}")
        console.print()

    # Steps modificados
    if diff.steps_modified:
        console.print(f"[yellow]~ {len(diff.steps_modified)} steps modificados:[/]")
        for change in diff.steps_modified:
            step_id = change.get("id", "?")
            before = change.get("before", {})
            after = change.get("after", {})
            console.print(f"  [yellow]~[/] {step_id}: {before.get('name', 'Unnamed')}")

            if verbose:
                # Mostra diferenças específicas
                before_action = before.get("action", {})
                after_action = after.get("action", {})

                if before_action != after_action:
                    console.print("      [dim]action changed[/]")

                before_assert = before.get("assertions", [])
                after_assert = after.get("assertions", [])
                if before_assert != after_assert:
                    console.print(f"      [dim]assertions: {len(before_assert)} → {len(after_assert)}[/]")
        console.print()

    # Config changes
    if diff.config_changes:
        console.print("[cyan]⚙ Configuração modificada:[/]")
        for key, change in diff.config_changes.items():
            before = change.get("before")
            after = change.get("after")
            console.print(f"  {key}:")
            console.print(f"    [red]- {before}[/]")
            console.print(f"    [green]+ {after}[/]")
        console.print()

    # Meta changes
    if diff.meta_changes:
        console.print("[magenta]📝 Metadados modificados:[/]")
        for key, change in diff.meta_changes.items():
            console.print(f"  {key}: [dim]{change.get('before')} → {change.get('after')}[/]")


@click.command("list")
@click.option(
    "--json-output",
    is_flag=True,
    help="Saída em formato JSON.",
)
@click.pass_context
def plan_list(ctx: click.Context, json_output: bool) -> None:
    """
    Lista todos os planos versionados.

    Exibe nome, versão atual e data de atualização.

    Exemplos:

        aqa plan list

        aqa plan list --json-output
    """
    console: Console = ctx.obj["console"]
    store = _get_store()

    plans = store.list_plans()

    if json_output:
        console.print_json(data={"plans": plans})
        return

    if not plans:
        console.print("[dim]Nenhum plano versionado encontrado.[/]")
        console.print("[dim]Use 'aqa plan save' para versionar um plano.[/]")
        return

    table = Table(title="Planos Versionados", show_header=True, header_style="bold")
    table.add_column("Nome", style="cyan")
    table.add_column("Versão", justify="center")
    table.add_column("Total", justify="center", style="dim")
    table.add_column("Atualizado", style="dim")

    for plan in plans:
        table.add_row(
            plan.get("name", "?"),
            f"v{plan.get('current_version', '?')}",
            str(plan.get("total_versions", "?")),
            plan.get("updated_at", "?")[:10] if plan.get("updated_at") else "?",
        )

    console.print(table)


@click.command("versions")
@click.argument("plan_name")
@click.option(
    "--json-output",
    is_flag=True,
    help="Saída em formato JSON.",
)
@click.pass_context
def plan_versions(ctx: click.Context, plan_name: str, json_output: bool) -> None:
    """
    Lista todas as versões de um plano.

    PLAN_NAME é o nome do plano a consultar.

    Exemplos:

        aqa plan versions my-api-tests
    """
    console: Console = ctx.obj["console"]
    store = _get_store()

    versions = store.list_versions(plan_name)

    if json_output:
        console.print_json(data={"plan_name": plan_name, "versions": versions})
        return

    if not versions:
        console.print(f"[red]Plano '{plan_name}' não encontrado.[/]")
        return

    console.print(Panel.fit(
        f"[bold]Versões: {plan_name}[/]",
        border_style="cyan",
    ))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Versão", justify="center")
    table.add_column("Data")
    table.add_column("Origem")
    table.add_column("Modelo", style="dim")
    table.add_column("Descrição")

    for v in versions:
        model_info = ""
        if v.get("llm_provider") or v.get("llm_model"):
            model_info = f"{v.get('llm_provider', '')} {v.get('llm_model', '')}".strip()

        table.add_row(
            f"v{v.get('version', '?')}",
            v.get("created_at", "?")[:19].replace("T", " "),
            v.get("source", "?"),
            model_info or "-",
            (v.get("description", "")[:30] + "...") if len(v.get("description", "")) > 30 else v.get("description", "-"),
        )

    console.print(table)


@click.command("diff")
@click.argument("plan_name")
@click.argument("version_a", type=int)
@click.argument("version_b", type=int, required=False)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Mostra detalhes completos das diferenças.",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Saída em formato JSON.",
)
@click.pass_context
def plan_diff(
    ctx: click.Context,
    plan_name: str,
    version_a: int,
    version_b: int | None,
    verbose: bool,
    json_output: bool,
) -> None:
    """
    Compara duas versões de um plano.

    PLAN_NAME é o nome do plano.
    VERSION_A é a versão base (mais antiga).
    VERSION_B é a versão a comparar (omita para usar a versão atual).

    Exemplos:

        aqa plan diff my-api-tests 1 2

        aqa plan diff my-api-tests 1  # Compara v1 com atual

        aqa plan diff my-api-tests 1 2 --verbose
    """
    console: Console = ctx.obj["console"]
    store = _get_store()

    diff = store.diff(plan_name, version_a, version_b)

    if diff is None:
        console.print(f"[red]Erro: Não foi possível comparar versões.[/]")
        console.print(f"[dim]Verifique se o plano '{plan_name}' existe e as versões são válidas.[/]")
        raise SystemExit(1)

    if json_output:
        console.print_json(data={
            "plan_name": plan_name,
            "version_a": diff.version_a,
            "version_b": diff.version_b,
            "has_changes": diff.has_changes,
            "summary": diff.summary,
            "steps_added": len(diff.steps_added),
            "steps_removed": len(diff.steps_removed),
            "steps_modified": len(diff.steps_modified),
            "config_changes": list(diff.config_changes.keys()),
            "meta_changes": list(diff.meta_changes.keys()),
        })
        return

    _format_diff_output(console, diff, plan_name, verbose)


@click.command("save")
@click.argument("plan_file", type=click.Path(exists=True))
@click.option(
    "--name", "-n",
    required=True,
    help="Nome do plano (será convertido para slug).",
)
@click.option(
    "--description", "-d",
    default="",
    help="Descrição da versão.",
)
@click.option(
    "--source", "-s",
    type=click.Choice(["llm", "manual", "import"]),
    default="manual",
    help="Origem do plano.",
)
@click.option(
    "--tag", "-t",
    multiple=True,
    help="Tags para categorização (pode usar múltiplas vezes).",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Saída em formato JSON.",
)
@click.pass_context
def plan_save(
    ctx: click.Context,
    plan_file: str,
    name: str,
    description: str,
    source: str,
    tag: tuple[str, ...],
    json_output: bool,
) -> None:
    """
    Salva uma nova versão de um plano.

    PLAN_FILE é o caminho do arquivo JSON do plano.

    Se o plano não existir, cria versão 1.
    Se existir, incrementa a versão.

    Exemplos:

        aqa plan save ./plan.json --name "my-api-tests"

        aqa plan save ./plan.json -n "my-tests" -d "Added auth steps" -t production
    """
    console: Console = ctx.obj["console"]
    store = _get_store()

    # Carrega o plano
    try:
        plan_path = Path(plan_file)
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        console.print(f"[red]Erro ao carregar plano: {e}[/]")
        raise SystemExit(1)

    # Salva versão
    version = store.save(
        plan_name=name,
        plan=plan,
        source=source,  # type: ignore
        description=description,
        tags=list(tag) if tag else None,
    )

    if json_output:
        console.print_json(data={
            "success": True,
            "plan_name": name,
            "version": version.version,
            "created_at": version.created_at,
        })
        return

    console.print()
    console.print(f"[green]✓[/] Plano salvo como [cyan]{name}[/] versão [bold]v{version.version}[/]")
    if description:
        console.print(f"  [dim]Descrição: {description}[/]")
    console.print()


@click.command("show")
@click.argument("plan_name")
@click.option(
    "--version", "-v",
    type=int,
    default=None,
    help="Versão específica (default: versão atual).",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Saída em formato JSON (plano completo).",
)
@click.option(
    "--summary",
    is_flag=True,
    help="Mostra apenas resumo, não o plano completo.",
)
@click.pass_context
def plan_show_version(
    ctx: click.Context,
    plan_name: str,
    version: int | None,
    json_output: bool,
    summary: bool,
) -> None:
    """
    Exibe uma versão do plano.

    PLAN_NAME é o nome do plano.

    Exemplos:

        aqa plan show my-api-tests

        aqa plan show my-api-tests --version 1

        aqa plan show my-api-tests --json-output
    """
    console: Console = ctx.obj["console"]
    store = _get_store()

    plan_version = store.get_version(plan_name, version)

    if plan_version is None:
        console.print(f"[red]Plano '{plan_name}' não encontrado.[/]")
        if version:
            console.print(f"[dim]Versão {version} pode não existir.[/]")
        raise SystemExit(1)

    if json_output:
        console.print_json(data={
            "plan_name": plan_name,
            "version": plan_version.version,
            "created_at": plan_version.created_at,
            "source": plan_version.source,
            "llm_provider": plan_version.llm_provider,
            "llm_model": plan_version.llm_model,
            "description": plan_version.description,
            "plan": plan_version.plan,
        })
        return

    # Header
    console.print()
    version_str = f"v{plan_version.version}"
    console.print(Panel.fit(
        f"[bold]{plan_name}[/] [dim]{version_str}[/]\n"
        f"[dim]Criado em: {plan_version.created_at[:19].replace('T', ' ')}[/]\n"
        f"[dim]Origem: {plan_version.source}[/]"
        + (f"\n[dim]Modelo: {plan_version.llm_provider} {plan_version.llm_model}[/]"
           if plan_version.llm_provider else ""),
        border_style="cyan",
    ))

    if plan_version.description:
        console.print(f"\n[italic]{plan_version.description}[/]")

    if summary:
        # Mostra apenas resumo
        plan = plan_version.plan
        steps = plan.get("steps", [])
        console.print(f"\n[bold]Steps:[/] {len(steps)}")

        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="dim")
        table.add_column("Nome")
        table.add_column("Método")
        table.add_column("Endpoint")

        for step in steps[:15]:
            action = step.get("action", {})
            table.add_row(
                step.get("id", "?"),
                (step.get("name", "?")[:35] + "...") if len(step.get("name", "")) > 35 else step.get("name", "?"),
                action.get("method", "-"),
                action.get("endpoint", "-"),
            )

        if len(steps) > 15:
            table.add_row("...", f"[dim]+{len(steps) - 15} mais[/]", "", "")

        console.print(table)
    else:
        # Mostra plano completo com syntax highlighting
        console.print()
        plan_json = json.dumps(plan_version.plan, indent=2, ensure_ascii=False)
        syntax = Syntax(plan_json, "json", theme="monokai", line_numbers=True)
        console.print(syntax)


# =============================================================================
# GRUPO DE COMANDOS - PLANVERSION
# =============================================================================


@register_command
@click.group()
@click.pass_context
def planversion(ctx: click.Context) -> None:
    """
    📋 Gerenciamento de versões de planos de teste.

    \b
    Exemplos:
      aqa planversion list                    # Lista todos os planos
      aqa planversion versions my-plan        # Mostra versões de um plano
      aqa planversion diff my-plan 1 2        # Compara versões 1 e 2
      aqa planversion save plan.json          # Salva como nova versão
      aqa planversion show my-plan            # Exibe versão atual
    """
    pass


# Registra os subcomandos no grupo
planversion.add_command(plan_list, name="list")
planversion.add_command(plan_versions, name="versions")
planversion.add_command(plan_diff, name="diff")
planversion.add_command(plan_save, name="save")
planversion.add_command(plan_show_version, name="show")
