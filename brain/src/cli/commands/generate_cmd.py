"""
================================================================================
Comando: aqa generate — Gera Plano UTDL
================================================================================

Este comando gera um plano de teste UTDL usando o LLM.

## Fontes de requisitos:
- `--swagger FILE` → Extrai endpoints de spec OpenAPI
- `--requirement TEXT` → Descrição em linguagem natural
- `--interactive` → Modo guiado com perguntas

## Uso:

```bash
# A partir de OpenAPI
aqa generate --swagger api.yaml --output plan.json

# A partir de descrição
aqa generate --requirement "Testar login com credenciais válidas e inválidas"

# Modo interativo
aqa generate --interactive

# Com modelo específico
aqa generate --swagger api.yaml --model gpt-4-turbo
```
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm

from ...generator import UTDLGenerator
from ...ingestion import parse_openapi
from ...ingestion.swagger import spec_to_requirement_text
from ..utils import load_config, get_default_model


@click.command()
@click.option(
    "--swagger", "-s",
    type=click.Path(exists=True),
    help="Arquivo OpenAPI/Swagger (YAML ou JSON)"
)
@click.option(
    "--requirement", "-r",
    type=str,
    help="Descrição em linguagem natural do que testar"
)
@click.option(
    "--base-url", "-u",
    type=str,
    help="URL base da API (sobrescreve config.yaml)"
)
@click.option(
    "--model", "-m",
    type=str,
    help="Modelo LLM (sobrescreve config.yaml)"
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Arquivo de saída (padrão: stdout)"
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    help="Modo interativo com perguntas guiadas"
)
@click.option(
    "--llm-mode",
    type=click.Choice(["real", "mock"]),
    default=None,
    help="Modo do LLM: 'real' (usa API) ou 'mock' (respostas de teste).",
)
@click.option(
    "--include-negative", "-n",
    is_flag=True,
    help="Incluir casos de teste negativos (campos inválidos, tipos errados, etc.)"
)
@click.option(
    "--include-auth", "-a",
    is_flag=True,
    help="Detectar e incluir step de autenticação automaticamente"
)
@click.pass_context
def generate(
    ctx: click.Context,
    swagger: str | None,
    requirement: str | None,
    base_url: str | None,
    model: str | None,
    output: str | None,
    interactive: bool,
    llm_mode: str | None,
    include_negative: bool,
    include_auth: bool,
) -> None:
    """
    Gera um plano de teste UTDL usando IA.

    Requer --swagger ou --requirement para especificar o que testar.
    Use --interactive para modo guiado com perguntas.
    O plano é impresso no stdout ou salvo em --output.
    """
    console: Console = ctx.obj["console"]
    verbose: bool = ctx.obj["verbose"]

    # Configura modo LLM se especificado
    if llm_mode:
        import os
        os.environ["AQA_LLM_MODE"] = llm_mode

    # Modo interativo
    if interactive:
        swagger, requirement, base_url, output = _interactive_mode(console)

    # Valida que pelo menos uma fonte foi fornecida
    if not swagger and not requirement:
        console.print(
            "[red]❌ Erro: forneça --swagger ou --requirement[/red]"
        )
        raise SystemExit(1)

    # Carrega configuração do workspace
    config = load_config()

    # Resolve valores (CLI > config > default)
    final_model = model or config.get("model") or get_default_model()
    final_base_url = base_url or config.get("base_url", "https://api.example.com")

    # Obtém texto do requisito
    if swagger:
        console.print(f"📖 Parseando spec OpenAPI: [cyan]{swagger}[/cyan]")
        spec = parse_openapi(swagger)
        original_spec = spec  # Guarda spec original para security detection
        requirement_text = spec_to_requirement_text(spec)
        # Usa base_url da spec se disponível
        if "base_url" in spec and spec["base_url"]:
            final_base_url = spec["base_url"]
    else:
        spec = None
        original_spec = None
        requirement_text = requirement  # type: ignore

    if verbose:
        console.print(f"[dim]Base URL: {final_base_url}[/dim]")
        console.print(f"[dim]Model: {final_model}[/dim]")
        console.print(f"[dim]LLM Mode: {llm_mode or 'real'}[/dim]")
        if include_negative:
            console.print("[dim]Incluindo casos negativos[/dim]")
        if include_auth:
            console.print("[dim]Detectando autenticação[/dim]")

    # Verifica se está em modo mock
    from ...llm import get_llm_provider
    llm_provider = get_llm_provider(mode=llm_mode)
    provider_name = llm_provider.name
    is_mock = provider_name == "mock"

    # Gera plano com progress spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        if is_mock:
            task = progress.add_task(
                "[cyan]🧠 Gerando plano com MockLLM (modo teste)...[/cyan]",
                total=None
            )
        else:
            task = progress.add_task(
                f"[cyan]🧠 Gerando plano com {final_model}...[/cyan]",
                total=None
            )

        try:
            if is_mock:
                # Usa MockLLMProvider diretamente
                response = llm_provider.generate(str(requirement_text))
                import json
                plan_dict = json.loads(response.content)
                # Converte para objeto Plan
                from ...validator.models import Plan
                plan_dict["config"] = plan_dict.get("config", {})
                plan_dict["config"]["base_url"] = final_base_url
                plan = Plan(**plan_dict)
            else:
                # UTDLGenerator usa 'provider' e não 'model' (detecta automaticamente)
                generator = UTDLGenerator()
                plan = generator.generate(str(requirement_text), final_base_url)
            progress.update(task, completed=True)

        except ValueError as e:
            progress.stop()
            console.print(f"[red]❌ Erro de geração: {e}[/red]")
            raise SystemExit(1)
        except Exception as e:
            progress.stop()
            console.print(f"[red]❌ Erro inesperado: {e}[/red]")
            if verbose:
                console.print_exception()
            raise SystemExit(1)

    # Aplica casos negativos se solicitado
    if include_negative and spec:
        from ...ingestion.negative_cases import generate_negative_cases, negative_cases_to_utdl_steps
        console.print("[cyan]🔍 Gerando casos negativos...[/cyan]")
        neg_result = generate_negative_cases(spec, max_cases_per_field=2)
        negative_steps = negative_cases_to_utdl_steps(neg_result.cases)
        # Adiciona ao plano existente
        for i, neg_step in enumerate(negative_steps):
            neg_step["id"] = f"neg-{i + 1:03d}"
        # Converter para Step objects e adicionar
        from ...validator.models import Step
        for neg_step in negative_steps:
            plan.steps.append(Step(**neg_step))
        console.print(f"[green]  ✓ {len(negative_steps)} casos negativos adicionados[/green]")

    # Aplica autenticação se solicitado
    if include_auth and original_spec:
        from ...ingestion.security import detect_security
        console.print("[cyan]🔐 Detectando esquemas de segurança...[/cyan]")
        security_analysis = detect_security(original_spec)
        if security_analysis.has_security:
            console.print(f"[green]  ✓ Segurança detectada: {security_analysis.primary_scheme.security_type.value if security_analysis.primary_scheme else 'unknown'}[/green]")
            # Nota: create_authenticated_plan_steps espera dicts, não objetos
            # Por simplicidade, apenas logamos; integração completa requer refatoração
            console.print("[yellow]  ⚠ Autenticação detectada. Use 'aqa plan' para integração completa.[/yellow]")
        else:
            console.print("[dim]  Nenhum esquema de segurança detectado[/dim]")

    # Output do plano
    json_output = plan.to_json()

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output, encoding="utf-8")

        console.print()
        console.print(Panel(
            f"[green]✅ Plano salvo em: {output_path}[/green]\n\n"
            f"[dim]Nome: {plan.meta.name}[/dim]\n"
            f"[dim]Steps: {len(plan.steps)}[/dim]",
            title="Plano Gerado",
            border_style="green",
        ))
    else:
        # Imprime no stdout (para piping)
        print(json_output)

        # Resumo no stderr
        error_console = Console(stderr=True)
        error_console.print(
            f"[green]✅ Plano gerado: {plan.meta.name} ({len(plan.steps)} steps)[/green]"
        )


def _interactive_mode(
    console: Console,
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Modo interativo com perguntas guiadas.

    Retorna tupla: (swagger, requirement, base_url, output)
    """
    console.print()
    console.print(Panel(
        "[cyan]🧪 Modo Interativo — Geração de Plano de Testes[/cyan]\n\n"
        "Vou te guiar passo a passo para criar seu plano de testes.",
        border_style="cyan",
    ))
    console.print()

    # Pergunta 1: Swagger ou descrição?
    source_choice = Prompt.ask(
        "[yellow]?[/yellow] Como você quer definir os testes",
        choices=["swagger", "descricao"],
        default="swagger",
    )

    swagger: str | None = None
    requirement: str | None = None

    if source_choice == "swagger":
        swagger = Prompt.ask(
            "[yellow]?[/yellow] Caminho para o arquivo OpenAPI/Swagger",
            default="openapi.yaml",
        )
        # Valida se existe
        if not Path(swagger).exists():
            console.print(f"[red]❌ Arquivo não encontrado: {swagger}[/red]")
            raise SystemExit(1)
    else:
        requirement = Prompt.ask(
            "[yellow]?[/yellow] Descreva o que você quer testar"
        )
        if not requirement.strip():
            console.print("[red]❌ Descrição não pode ser vazia[/red]")
            raise SystemExit(1)

    # Pergunta 2: Base URL
    base_url = Prompt.ask(
        "[yellow]?[/yellow] URL base da API",
        default="http://localhost:8000",
    )

    # Pergunta 3: Casos negativos?
    include_negative = Confirm.ask(
        "[yellow]?[/yellow] Incluir casos negativos (invalid input, missing fields)?",
        default=True,
    )

    # Pergunta 4: Retries?
    include_retries = Confirm.ask(
        "[yellow]?[/yellow] Adicionar política de retry para falhas?",
        default=True,
    )

    # Pergunta 5: Output
    output = Prompt.ask(
        "[yellow]?[/yellow] Arquivo de saída",
        default="plan.json",
    )

    # Monta requirement adicional baseado nas opções
    if requirement and (include_negative or include_retries):
        extras: list[str] = []
        if include_negative:
            extras.append("casos negativos (inputs inválidos, campos obrigatórios faltando)")
        if include_retries:
            extras.append("política de retry com backoff exponencial")

        requirement = f"{requirement}. Inclua também: {', '.join(extras)}."

    console.print()
    console.print("[dim]─" * 50 + "[/dim]")
    console.print()

    return swagger, requirement, base_url, output
