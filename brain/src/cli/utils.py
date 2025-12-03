"""
================================================================================
Utilitários do CLI
================================================================================

Funções auxiliares compartilhadas entre os comandos do CLI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_config() -> dict[str, Any]:
    """
    Carrega configuração do workspace .aqa/config.yaml.

    Busca o arquivo de configuração subindo na hierarquia de diretórios
    a partir do diretório atual.

    ## Retorna:
        Dict com a configuração, ou dict vazio se não encontrar.

    ## Exemplo:
        ```python
        config = load_config()
        model = config.get("model", "gpt-4")
        base_url = config.get("base_url", "https://api.example.com")
        ```
    """
    # Procura .aqa/config.yaml subindo na hierarquia
    current = Path.cwd()
    
    while current != current.parent:
        config_path = current / ".aqa" / "config.yaml"
        if config_path.exists():
            try:
                content = config_path.read_text(encoding="utf-8")
                loaded = yaml.safe_load(content)
                if isinstance(loaded, dict):
                    return dict(loaded)  # type: ignore[arg-type]
                return {}
            except Exception:
                return {}
        current = current.parent

    # Não encontrou, retorna vazio
    return {}


def get_default_model() -> str:
    """
    Retorna o modelo LLM padrão a usar.

    ## Prioridade:
    1. Variável de ambiente AQA_MODEL
    2. Fallback para gpt-4

    ## Retorna:
        Nome do modelo (ex: "gpt-4", "claude-3-opus")
    """
    return os.environ.get("AQA_MODEL", "gpt-4")


def get_runner_path() -> Path | None:
    """
    Localiza o binário do Runner.

    ## Busca em:
    1. Variável de ambiente AQA_RUNNER_PATH
    2. ./runner/target/release/runner (produção)
    3. ./runner/target/debug/runner (desenvolvimento)
    4. runner no PATH do sistema

    ## Retorna:
        Path para o binário, ou None se não encontrar.
    """
    # 1. Variável de ambiente
    if env_path := os.environ.get("AQA_RUNNER_PATH"):
        path = Path(env_path)
        if path.exists():
            return path

    # 2. Caminho relativo (release)
    release_path = Path("runner/target/release/runner")
    if os.name == "nt":
        release_path = release_path.with_suffix(".exe")
    if release_path.exists():
        return release_path

    # 3. Caminho relativo (debug)
    debug_path = Path("runner/target/debug/runner")
    if os.name == "nt":
        debug_path = debug_path.with_suffix(".exe")
    if debug_path.exists():
        return debug_path

    # 4. Não encontrou
    return None


def format_duration(ms: int) -> str:
    """
    Formata duração em milissegundos para string legível.

    ## Exemplos:
        - 50 → "50ms"
        - 1500 → "1.5s"
        - 65000 → "1m 5s"
    """
    if ms < 1000:
        return f"{ms}ms"
    
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}m {remaining_seconds}s"
