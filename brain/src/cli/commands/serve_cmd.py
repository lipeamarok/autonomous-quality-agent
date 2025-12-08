"""
================================================================================
Comando: aqa serve — Inicia servidor API
================================================================================

Este comando inicia o servidor FastAPI para expor a API REST do AQA.

## Uso:

```bash
# Iniciar servidor padrão
aqa serve

# Com porta customizada
aqa serve --port 3000

# Modo desenvolvimento com reload
aqa serve --reload --debug

# Bind em host específico
aqa serve --host 127.0.0.1 --port 8080
```

## Endpoints disponíveis:

- GET  /health              - Health check
- POST /api/v1/generate     - Gerar plano UTDL
- POST /api/v1/validate     - Validar plano UTDL
- POST /api/v1/execute      - Executar plano
- GET  /api/v1/history      - Histórico de execuções
- POST /api/v1/workspace/init - Inicializar workspace
- WS   /ws/execute          - Streaming de execução

## Documentação interativa:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel

from ..registry import register_command


@register_command
@click.command()
@click.option(
    "--host",
    "-h",
    type=str,
    default="0.0.0.0",
    help="Host para bind do servidor (padrão: 0.0.0.0)"
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=8000,
    help="Porta do servidor (padrão: 8000)"
)
@click.option(
    "--reload",
    is_flag=True,
    help="Modo desenvolvimento com auto-reload"
)
@click.option(
    "--debug",
    is_flag=True,
    help="Modo debug (mostra erros detalhados)"
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=1,
    help="Número de workers (padrão: 1, não usar com --reload)"
)
@click.option(
    "--no-docs",
    is_flag=True,
    help="Desabilitar documentação interativa (/docs, /redoc)"
)
@click.pass_context
def serve(
    ctx: click.Context,
    host: str,
    port: int,
    reload: bool,
    debug: bool,
    workers: int,
    no_docs: bool,
) -> None:
    """
    🚀 Inicia servidor API do AQA.

    Expõe as funcionalidades do AQA via REST API e WebSocket,
    permitindo integração com interfaces gráficas ou outros sistemas.

    \b
    Exemplos:
      aqa serve                    # Inicia na porta 8000
      aqa serve --port 3000        # Porta customizada
      aqa serve --reload --debug   # Modo desenvolvimento
      aqa serve --workers 4        # Múltiplos workers (produção)

    \b
    Documentação:
      Swagger UI: http://localhost:PORT/docs
      ReDoc:      http://localhost:PORT/redoc
    """
    console: Console = ctx.obj.get("console", Console())
    quiet = ctx.obj.get("quiet", False)

    # Configura ambiente
    import os
    os.environ["AQA_API_HOST"] = host
    os.environ["AQA_API_PORT"] = str(port)
    os.environ["AQA_API_DEBUG"] = "true" if debug else "false"
    os.environ["AQA_API_DOCS"] = "false" if no_docs else "true"

    # Banner de início
    if not quiet:
        _print_banner(console, host, port, reload, debug)

    # Inicia servidor
    try:
        import uvicorn

        uvicorn.run(
            "src.api.app:get_app",
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            factory=True,
            log_level="debug" if debug else "info",
            access_log=debug,
        )

    except ImportError:
        console.print(
            "[red]Erro:[/red] uvicorn não está instalado.\n"
            "Execute: pip install uvicorn[standard]",
            style="red"
        )
        raise SystemExit(1)

    except Exception as e:
        console.print(f"[red]Erro ao iniciar servidor:[/red] {e}")
        raise SystemExit(1)


def _print_banner(
    console: Console,
    host: str,
    port: int,
    reload: bool,
    debug: bool,
) -> None:
    """Imprime banner de início do servidor."""
    mode = "🔧 Development" if reload else "🚀 Production"
    debug_str = "enabled" if debug else "disabled"

    # Determina URL de acesso
    if host == "0.0.0.0":
        access_url = f"http://localhost:{port}"
    else:
        access_url = f"http://{host}:{port}"

    banner = f"""
[bold cyan]╔══════════════════════════════════════════════════════════════╗
║            🧪 AQA — Autonomous Quality Agent API             ║
╚══════════════════════════════════════════════════════════════╝[/bold cyan]

[bold]Mode:[/bold] {mode}
[bold]Debug:[/bold] {debug_str}

[bold green]Endpoints:[/bold green]
  • API:      {access_url}/api/v1
  • Health:   {access_url}/health
  • Docs:     {access_url}/docs
  • ReDoc:    {access_url}/redoc
  • OpenAPI:  {access_url}/openapi.json
  • WS:       ws://localhost:{port}/ws/execute

[dim]Pressione Ctrl+C para encerrar[/dim]
"""

    console.print(Panel(
        banner.strip(),
        border_style="cyan",
        padding=(0, 2),
    ))
