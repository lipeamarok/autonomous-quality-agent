"""
================================================================================
Rota: /workspace
================================================================================

Gerenciamento de workspace AQA.

## Funcionalidades:

- Inicializar novo workspace
- Verificar status do workspace atual
- Criar estrutura de diretórios padrão
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from ..schemas.workspace import (
    WorkspaceInitRequest,
    WorkspaceInitResponse,
    WorkspaceStatusResponse,
)


router = APIRouter()


# Constantes de estrutura do workspace
AQA_WORKSPACE_DIR = ".aqa"
AQA_CONFIG_FILE = "config.yaml"
AQA_PLANS_DIR = "plans"
AQA_REPORTS_DIR = "reports"


def _get_workspace_path(base_path: str | None = None) -> Path:
    """Retorna caminho do workspace."""
    if base_path:
        return Path(base_path) / AQA_WORKSPACE_DIR
    return Path.cwd() / AQA_WORKSPACE_DIR


def _create_default_config() -> str:
    """Cria conteúdo do config.yaml padrão."""
    return """# AQA Workspace Configuration
# Gerado automaticamente pelo aqa init

# URL base padrão para testes
base_url: https://api.example.com

# Configurações do LLM
llm:
  provider: openai  # openai, xai, anthropic
  model: gpt-4o
  temperature: 0.2

# Configurações do Runner
runner:
  timeout_ms: 30000
  max_parallel: 10
  retry_attempts: 3

# Configurações de output
output:
  format: text  # text, json
  save_reports: true
"""


@router.post(
    "/init",
    response_model=WorkspaceInitResponse,
    summary="Inicializar Workspace",
    description="""
Cria a estrutura de diretórios do workspace AQA.

## Estrutura criada:

```
.aqa/
├── config.yaml    # Configurações do projeto
├── plans/         # Planos de teste gerados
└── reports/       # Relatórios de execução
```
    """,
)
async def init_workspace(
    request: WorkspaceInitRequest,
) -> WorkspaceInitResponse:
    """
    Inicializa um workspace AQA.
    """
    workspace_path = _get_workspace_path(request.path)
    already_existed = workspace_path.exists()

    # Verifica se já existe e force não está habilitado
    if already_existed and not request.force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "E4003",
                "message": f"Workspace já existe em {workspace_path}. Use force=true para sobrescrever.",
            },
        )

    created_files: list[str] = []

    try:
        # Cria diretório principal
        workspace_path.mkdir(parents=True, exist_ok=True)
        created_files.append(str(workspace_path))

        # Cria subdiretórios
        plans_path = workspace_path / AQA_PLANS_DIR
        plans_path.mkdir(exist_ok=True)
        created_files.append(str(plans_path))

        reports_path = workspace_path / AQA_REPORTS_DIR
        reports_path.mkdir(exist_ok=True)
        created_files.append(str(reports_path))

        # Cria config.yaml
        config_path = workspace_path / AQA_CONFIG_FILE
        if not config_path.exists() or request.force:
            config_path.write_text(_create_default_config())
            created_files.append(str(config_path))

        return WorkspaceInitResponse(
            success=True,
            workspace_path=str(workspace_path.absolute()),
            created_files=created_files,
            already_existed=already_existed,
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "E4004",
                "message": f"Sem permissão para criar workspace em {workspace_path}",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "E5001",
                "message": f"Erro ao criar workspace: {e}",
            },
        )


@router.get(
    "/status",
    response_model=WorkspaceStatusResponse,
    summary="Status do Workspace",
    description="Retorna informações sobre o workspace atual.",
)
async def workspace_status() -> WorkspaceStatusResponse:
    """
    Retorna status do workspace atual.
    """
    workspace_path = _get_workspace_path()

    if not workspace_path.exists():
        return WorkspaceStatusResponse(
            success=True,
            initialized=False,
            workspace_path=None,
            plans_count=0,
            history_count=0,
            config=None,
        )

    # Conta planos
    plans_path = workspace_path / AQA_PLANS_DIR
    plans_count = 0
    if plans_path.exists():
        plans_count = len(list(plans_path.glob("*.json")))

    # Conta histórico
    # TODO: usar ExecutionHistory.count()
    history_count = 0

    # Lê config
    config = None
    config_path = workspace_path / AQA_CONFIG_FILE
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except Exception:
            pass

    return WorkspaceStatusResponse(
        success=True,
        initialized=True,
        workspace_path=str(workspace_path.absolute()),
        plans_count=plans_count,
        history_count=history_count,
        config=config,
    )
