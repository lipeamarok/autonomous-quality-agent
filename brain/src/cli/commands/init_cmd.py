"""
================================================================================
Comando: aqa init — Inicializa Workspace
================================================================================

Este comando cria a estrutura inicial de um projeto AQA:

```
.aqa/
├── config.yaml          # Configurações (base_url, model, api_key)
├── plans/               # Planos UTDL gerados
│   └── .gitkeep
└── reports/             # Relatórios de execução
    └── .gitkeep
```

## Uso:

```bash
# Inicializa no diretório atual
aqa init

# Inicializa em diretório específico
aqa init ./meu-projeto

# Força reinicialização
aqa init --force
```
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

# Template do arquivo de configuração
CONFIG_TEMPLATE = """\
# =============================================================================
# AQA Configuration
# =============================================================================
# Este arquivo configura o Autonomous Quality Agent para este projeto.

# URL base da API a ser testada
base_url: https://api.example.com

# Modelo LLM a usar para geração de planos
# Opções: gpt-4, gpt-4-turbo, gpt-3.5-turbo, claude-3-opus, claude-3-sonnet
model: gpt-4

# Provedor LLM (detectado automaticamente pela API key)
# provider: openai

# Timeout para requisições HTTP (em segundos)
http_timeout: 30

# Modo de execução padrão: sequential ou parallel
execution_mode: sequential

# Diretório para salvar planos gerados
plans_dir: .aqa/plans

# Diretório para salvar relatórios
reports_dir: .aqa/reports

# Variáveis de contexto customizadas
# Estas variáveis ficam disponíveis em todos os planos via ${var_name}
variables:
  # api_key: "${env:API_KEY}"
  # auth_token: "${env:AUTH_TOKEN}"
"""


@click.command()
@click.argument(
    "directory",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Sobrescreve configuração existente"
)
@click.pass_context
def init(ctx: click.Context, directory: str, force: bool) -> None:
    """
    Inicializa um workspace AQA no diretório especificado.

    Cria a estrutura de diretórios .aqa/ com configuração padrão.
    Use --force para reinicializar um workspace existente.
    """
    console: Console = ctx.obj["console"]
    
    # Resolve o diretório
    target_dir = Path(directory).resolve()
    aqa_dir = target_dir / ".aqa"
    config_file = aqa_dir / "config.yaml"
    plans_dir = aqa_dir / "plans"
    reports_dir = aqa_dir / "reports"

    # Verifica se já existe
    if aqa_dir.exists() and not force:
        console.print(
            f"[yellow]⚠️  Workspace já existe em {aqa_dir}[/yellow]"
        )
        console.print("Use [bold]--force[/bold] para reinicializar.")
        raise SystemExit(1)

    # Cria estrutura de diretórios
    try:
        aqa_dir.mkdir(parents=True, exist_ok=True)
        plans_dir.mkdir(exist_ok=True)
        reports_dir.mkdir(exist_ok=True)

        # Cria arquivo de configuração
        config_file.write_text(CONFIG_TEMPLATE, encoding="utf-8")

        # Cria .gitkeep nos diretórios vazios
        (plans_dir / ".gitkeep").touch()
        (reports_dir / ".gitkeep").touch()

    except OSError as e:
        console.print(f"[red]❌ Erro ao criar diretórios: {e}[/red]")
        raise SystemExit(1)

    # Exibe resultado com árvore formatada
    tree = Tree(f"📁 [bold blue]{target_dir.name}[/bold blue]")
    aqa_tree = tree.add("📁 [cyan].aqa/[/cyan]")
    aqa_tree.add("📄 [green]config.yaml[/green]")
    
    plans_tree = aqa_tree.add("📁 [cyan]plans/[/cyan]")
    plans_tree.add("[dim].gitkeep[/dim]")
    
    reports_tree = aqa_tree.add("📁 [cyan]reports/[/cyan]")
    reports_tree.add("[dim].gitkeep[/dim]")

    console.print()
    console.print(Panel(
        tree,
        title="✅ Workspace inicializado",
        border_style="green",
    ))

    console.print()
    console.print("[bold]Próximos passos:[/bold]")
    console.print("  1. Edite [cyan].aqa/config.yaml[/cyan] com sua base_url")
    console.print("  2. Configure a variável de ambiente [cyan]OPENAI_API_KEY[/cyan]")
    console.print("  3. Execute [bold]aqa generate --swagger api.yaml[/bold]")
    console.print()
