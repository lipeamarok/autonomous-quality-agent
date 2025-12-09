"""
================================================================================
Comando: aqa plan — Gerar Plano UTDL
================================================================================

Este comando gera planos de teste UTDL a partir de especificações OpenAPI/Swagger
ou descrições em linguagem natural.

## Uso:

```bash
# Gerar a partir de OpenAPI
aqa plan --swagger https://api.example.com/openapi.json

# Gerar a partir de arquivo local
aqa plan --swagger ./openapi.yaml

# Gerar com casos negativos
aqa plan --swagger ./api.yaml --include-negative

# Gerar com autenticação automática
aqa plan --swagger ./api.yaml --include-auth

# Modo interativo
aqa plan --interactive

# Especificar endpoints
aqa plan --swagger ./api.yaml --endpoints /users --endpoints /orders

# Salvar em arquivo específico
aqa plan --swagger ./api.yaml -o ./plans/test-plan.json
```
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table

from ..registry import register_command


def _generate_plan_from_spec(
    spec: dict[str, Any],
    *,
    original_spec: dict[str, Any] | None = None,
    include_negative: bool = False,
    include_auth: bool = False,
    endpoints_filter: list[str] | None = None,
) -> dict[str, Any]:
    """
    Gera um plano UTDL a partir de uma spec OpenAPI normalizada.

    ## Parâmetros:
        spec: Spec normalizada (output de parse_openapi)
        original_spec: Spec original (necessária para detecção de segurança)
        include_negative: Se True, inclui casos negativos
        include_auth: Se True, inclui step de autenticação
        endpoints_filter: Lista de paths para filtrar (None = todos)

    ## Retorna:
        Plano UTDL completo
    """
    from ...ingestion.negative_cases import generate_negative_cases, negative_cases_to_utdl_steps
    from ...ingestion.security import create_authenticated_plan_steps, detect_security

    base_url = spec.get("base_url", "")
    title = spec.get("title", "API Test Plan")
    endpoints = spec.get("endpoints", [])

    # Filtra endpoints se especificado
    if endpoints_filter:
        endpoints = [e for e in endpoints if e["path"] in endpoints_filter]

    # Gera steps positivos
    positive_steps: list[dict[str, Any]] = []
    step_counter = 1

    for endpoint in endpoints:
        path = endpoint["path"]
        method = endpoint["method"]
        summary = endpoint.get("summary", "")

        # Formato UTDL correto
        step: dict[str, Any] = {
            "id": f"step-{step_counter:03d}",
            "description": f"{method} {path}" + (f" - {summary}" if summary else ""),
            "action": "http_request",
            "depends_on": [],
            "params": {
                "method": method,
                "path": path,
            },
            "assertions": [
                {
                    "type": "status_code",
                    "operator": "eq",
                    "value": 200 if method == "GET" else 201 if method == "POST" else 200,
                }
            ],
            "extract": [],
        }

        # Adiciona body para métodos que precisam
        if method in ("POST", "PUT", "PATCH"):
            request_body = endpoint.get("request_body")
            if request_body and request_body.get("schema"):
                step["params"]["body"] = _generate_sample_body(request_body["schema"])

        positive_steps.append(step)
        step_counter += 1

    # Gera steps negativos se solicitado
    negative_steps: list[dict[str, Any]] = []
    if include_negative:
        neg_result = generate_negative_cases(spec, max_cases_per_field=2)
        negative_steps = negative_cases_to_utdl_steps(neg_result.cases)
        # Ajusta IDs
        for i, step in enumerate(negative_steps):
            step["id"] = f"neg-{i + 1:03d}"

    # Junta todos os steps
    all_steps = positive_steps + negative_steps

    # Adiciona autenticação se solicitado
    final_steps: list[dict[str, Any]] = all_steps
    security_info = None

    if include_auth and original_spec:
        # Usa a spec original para detectar segurança
        security_analysis = detect_security(original_spec)

        if security_analysis.has_security:
            # Cria steps autenticados
            final_steps = create_authenticated_plan_steps(
                original_spec,
                all_steps,
            )
            security_info = security_analysis

    # Monta o plano
    plan: dict[str, Any] = {
        "spec_version": "0.1",
        "meta": {
            "id": f"plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "name": f"Test Plan: {title}",
            "description": f"Plano de teste gerado automaticamente para {title}",
            "created_at": datetime.now().isoformat() + "Z",
            "tags": ["auto-generated"],
        },
        "config": {
            "base_url": base_url,
            "variables": {},
        },
        "steps": final_steps,
    }

    # Adiciona info de segurança ao meta se detectada
    if security_info and security_info.primary_scheme:
        plan["meta"]["security"] = {
            "type": security_info.primary_scheme.security_type.value,
            "scheme": security_info.primary_scheme.name,
        }

    return plan


def _generate_sample_body(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Gera um body de exemplo a partir de um JSON Schema.

    ## Parâmetros:
        schema: JSON Schema do request body

    ## Retorna:
        Dicionário com valores de exemplo
    """
    body: dict[str, Any] = {}

    properties = schema.get("properties", {})
    # required = set(schema.get("required", []))  # Reserved for future validation

    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type", "string")
        field_format = field_schema.get("format")

        # Gera valor de exemplo baseado no tipo
        if field_type == "string":
            if field_format == "email":
                body[field_name] = "test@example.com"
            elif field_format == "uuid":
                body[field_name] = "123e4567-e89b-12d3-a456-426614174000"
            elif field_format == "date":
                body[field_name] = "2024-01-01"
            elif field_format == "date-time":
                body[field_name] = "2024-01-01T00:00:00Z"
            elif field_format == "uri":
                body[field_name] = "https://example.com"
            elif field_name.lower() == "password":
                body[field_name] = "SecureP@ss123"
            elif field_name.lower() in ("name", "username"):
                body[field_name] = "test_user"
            else:
                body[field_name] = f"sample_{field_name}"

        elif field_type == "integer":
            if field_name.lower() in ("age", "count", "quantity"):
                body[field_name] = 25
            else:
                body[field_name] = 1

        elif field_type == "number":
            body[field_name] = 1.0

        elif field_type == "boolean":
            body[field_name] = True

        elif field_type == "array":
            items_schema = field_schema.get("items", {})
            if items_schema.get("type") == "object":
                body[field_name] = [_generate_sample_body(items_schema)]
            else:
                body[field_name] = ["sample"]

        elif field_type == "object":
            body[field_name] = _generate_sample_body(field_schema)

    return body


@register_command
@click.command()
@click.option(
    "--swagger", "-s",
    type=str,
    help="URL ou caminho do arquivo OpenAPI/Swagger.",
)
@click.option(
    "--output", "-o",
    type=click.Path(dir_okay=False),
    help="Caminho para salvar o plano gerado.",
)
@click.option(
    "--include-negative", "-n",
    is_flag=True,
    help="Incluir casos de teste negativos.",
)
@click.option(
    "--include-auth", "-a",
    is_flag=True,
    help="Incluir step de autenticação (detecta automaticamente do Swagger).",
)
@click.option(
    "--endpoints", "-e",
    multiple=True,
    help="Filtrar endpoints específicos (pode usar múltiplas vezes).",
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    help="Modo interativo com perguntas guiadas.",
)
@click.option(
    "--llm-mode",
    type=click.Choice(["real", "mock"]),
    default=None,
    help="Modo do LLM: 'real' (usa API) ou 'mock' (respostas de teste).",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Saída em formato JSON (sem formatação Rich).",
)
@click.pass_context
def plan(
    ctx: click.Context,
    swagger: str | None,
    output: str | None,
    include_negative: bool,
    include_auth: bool,
    endpoints: tuple[str, ...],
    interactive: bool,
    llm_mode: str | None,
    json_output: bool,
) -> None:
    """
    Gera um plano de teste UTDL a partir de uma especificação OpenAPI/Swagger.

    O plano gerado inclui steps para testar todos os endpoints documentados
    na especificação, com valores de exemplo gerados automaticamente.

    Use --interactive para modo guiado com perguntas.

    Exemplos:

        aqa plan --swagger https://api.example.com/openapi.json

        aqa plan --swagger ./api.yaml --include-negative -o plan.json

        aqa plan --interactive
    """
    console: Console = ctx.obj["console"]

    # Modo interativo
    if interactive:
        swagger, output, include_negative, include_auth = _interactive_plan_mode(console)

    # Valida que swagger foi fornecido
    if not swagger:
        console.print(
            "[red]❌ Erro: forneça --swagger ou use --interactive[/red]"
        )
        raise SystemExit(1)

    # Carrega e parseia a spec
    try:
        from ...ingestion.swagger import parse_openapi
        import json as json_module
        from pathlib import Path as PathLib

        original_spec: dict[str, Any] = {}

        if not json_output:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Carregando especificação OpenAPI...", total=None)

                # Carrega spec original para detecção de segurança
                if swagger.startswith(("http://", "https://")):
                    import requests
                    resp = requests.get(swagger, timeout=30)
                    resp.raise_for_status()
                    original_spec = resp.json()
                else:
                    path = PathLib(swagger)
                    with path.open(encoding="utf-8") as f:
                        if path.suffix in (".yaml", ".yml"):
                            import yaml
                            original_spec = yaml.safe_load(f)
                        else:
                            original_spec = json_module.load(f)

                spec = parse_openapi(swagger, validate_spec=True, strict=False)
                progress.update(task, description="[green]✓[/] Especificação carregada")
        else:
            # Carrega spec original
            if swagger.startswith(("http://", "https://")):
                import requests
                resp = requests.get(swagger, timeout=30)
                resp.raise_for_status()
                original_spec = resp.json()
            else:
                path = PathLib(swagger)
                with path.open(encoding="utf-8") as f:
                    if path.suffix in (".yaml", ".yml"):
                        import yaml
                        original_spec = yaml.safe_load(f)
                    else:
                        original_spec = json_module.load(f)

            spec = parse_openapi(swagger, validate_spec=True, strict=False)

    except Exception as e:
        if json_output:
            console.print_json(data={"success": False, "error": str(e)})
        else:
            console.print(f"[red]❌ Erro ao carregar Swagger: {e}[/]")
        raise SystemExit(1)

    # Gera o plano
    try:
        endpoints_filter = list(endpoints) if endpoints else None
        generated_plan = _generate_plan_from_spec(
            spec,
            original_spec=original_spec,
            include_negative=include_negative,
            include_auth=include_auth,
            endpoints_filter=endpoints_filter,
        )

    except Exception as e:
        if json_output:
            console.print_json(data={"success": False, "error": str(e)})
        else:
            console.print(f"[red]❌ Erro ao gerar plano: {e}[/]")
        raise SystemExit(1)

    # Salva ou exibe
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(generated_plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if json_output:
            console.print_json(data={
                "success": True,
                "output": str(output_path),
                "steps_count": len(generated_plan["steps"]),
            })
        else:
            console.print(f"\n[green]✓[/] Plano salvo em: [cyan]{output_path}[/]")

    else:
        if json_output:
            console.print_json(data=generated_plan)
        else:
            # Exibe resumo
            console.print()
            console.print(Panel.fit(
                f"[bold]Plano Gerado: {generated_plan['meta']['name']}[/]\n"
                f"[dim]Base URL: {generated_plan['config']['base_url']}[/]",
                border_style="cyan",
            ))

            # Tabela de steps
            table = Table(title="Steps", show_header=True, header_style="bold")
            table.add_column("ID", style="dim")
            table.add_column("Nome")
            table.add_column("Método", justify="center")
            table.add_column("Endpoint")
            table.add_column("Expected", justify="center")

            for step in generated_plan["steps"][:20]:  # Limita a 20
                action = step.get("action", {})
                expected = step.get("expected", {})

                table.add_row(
                    step["id"],
                    step["name"][:40] + "..." if len(step["name"]) > 40 else step["name"],
                    action.get("method", "-"),
                    action.get("endpoint", "-"),
                    str(expected.get("status_code", "-")),
                )

            if len(generated_plan["steps"]) > 20:
                table.add_row("...", f"[dim]+{len(generated_plan['steps']) - 20} mais[/]", "", "", "")

            console.print(table)

            # Dica
            console.print()
            console.print("[dim]Use -o FILE para salvar o plano em um arquivo.[/]")
            console.print("[dim]Use --json-output para obter o JSON completo.[/]")


def _interactive_plan_mode(
    console: Console,
) -> tuple[str, str | None, bool, bool]:
    """
    Modo interativo com perguntas guiadas para o comando plan.

    Retorna tupla: (swagger, output, include_negative, include_auth)
    """
    console.print()
    console.print(Panel(
        "[cyan]🧪 Modo Interativo — Geração de Plano de Testes[/cyan]\n\n"
        "Vou te guiar para criar seu plano de testes a partir de um Swagger.",
        border_style="cyan",
    ))
    console.print()

    # Pergunta 1: Swagger
    swagger = Prompt.ask(
        "[yellow]?[/yellow] Caminho ou URL do arquivo OpenAPI/Swagger",
        default="openapi.yaml",
    )

    # Valida se existe (se for arquivo local)
    if not swagger.startswith(("http://", "https://")):
        if not Path(swagger).exists():
            console.print(f"[red]❌ Arquivo não encontrado: {swagger}[/red]")
            raise SystemExit(1)

    # Pergunta 2: Casos negativos?
    include_negative = Confirm.ask(
        "[yellow]?[/yellow] Incluir casos negativos (invalid input, missing fields)?",
        default=True,
    )

    # Pergunta 3: Auth?
    include_auth = Confirm.ask(
        "[yellow]?[/yellow] Detectar e incluir autenticação automaticamente?",
        default=True,
    )

    # Pergunta 4: Retries?
    # (Não há opção de retry no plan, mas podemos sugerir)

    # Pergunta 5: Output
    output = Prompt.ask(
        "[yellow]?[/yellow] Arquivo de saída",
        default="plan.json",
    )

    console.print()
    console.print("[dim]─" * 50 + "[/dim]")
    console.print()

    return swagger, output, include_negative, include_auth
