"""
================================================================================
Utilitários do CLI
================================================================================

Funções auxiliares compartilhadas entre os comandos do CLI.
"""

from __future__ import annotations

import os
import shutil
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


def get_runner_path(runner_path_override: str | None = None) -> Path | None:
    """
    Localiza o binário do Runner com suporte cross-platform.

    ## Ordem de Busca:
    1. Parâmetro runner_path_override (passado via --runner-path)
    2. Variável de ambiente AQA_RUNNER_PATH
    3. ./runner/target/release/runner (produção - local)
    4. ./runner/target/debug/runner (desenvolvimento - local)
    5. ~/.cargo/bin/runner (cargo install)
    6. /usr/local/bin/runner (instalação global Unix)
    7. runner no PATH do sistema (via shutil.which)

    ## Parâmetros:
        runner_path_override: Caminho explícito passado pelo usuário

    ## Retorna:
        Path para o binário, ou None se não encontrar.
    """
    binary_name = "runner.exe" if os.name == "nt" else "runner"

    # 1. Override passado pelo usuário
    if runner_path_override:
        path = Path(runner_path_override)
        if path.exists() and path.is_file():
            return path
        # Pode ser um diretório
        if path.is_dir():
            candidate = path / binary_name
            if candidate.exists():
                return candidate

    # 2. Variável de ambiente
    if env_path := os.environ.get("AQA_RUNNER_PATH"):
        path = Path(env_path)
        if path.exists():
            return path

    # 3. Caminho relativo (release)
    release_path = Path("runner/target/release") / binary_name
    if release_path.exists():
        return release_path.resolve()

    # 4. Caminho relativo (debug)
    debug_path = Path("runner/target/debug") / binary_name
    if debug_path.exists():
        return debug_path.resolve()

    # 5. Cargo bin directory
    cargo_home = os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))
    cargo_bin = Path(cargo_home) / "bin" / binary_name
    if cargo_bin.exists():
        return cargo_bin

    # 6. Global install locations (Unix)
    if os.name != "nt":
        for global_path in [
            Path("/usr/local/bin/runner"),
            Path("/usr/bin/runner"),
        ]:
            if global_path.exists():
                return global_path

    # 7. Sistema PATH
    which_result = shutil.which("runner")
    if which_result:
        return Path(which_result)

    # Não encontrou
    return None


def get_runner_search_paths() -> list[str]:
    """
    Lista todos os caminhos onde o Runner é buscado.

    Útil para diagnóstico quando o Runner não é encontrado.

    ## Retorna:
        Lista de caminhos pesquisados.
    """
    binary_name = "runner.exe" if os.name == "nt" else "runner"
    paths: list[str] = []

    paths.append("$AQA_RUNNER_PATH (env)")
    paths.append(f"./runner/target/release/{binary_name}")
    paths.append(f"./runner/target/debug/{binary_name}")

    cargo_home = os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))
    paths.append(f"{cargo_home}/bin/{binary_name}")

    if os.name != "nt":
        paths.append("/usr/local/bin/runner")
        paths.append("/usr/bin/runner")

    paths.append("PATH (via which)")

    return paths


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
