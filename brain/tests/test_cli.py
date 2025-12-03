"""
================================================================================
Testes de Integração do CLI
================================================================================

Testes para os comandos do CLI `aqa`.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

# Adiciona o diretório brain ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.main import cli
from src.cli.utils import get_runner_path, get_runner_search_paths, load_config


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """CliRunner para testar comandos Click."""
    return CliRunner()


@pytest.fixture
def valid_plan() -> dict[str, Any]:
    """Plano UTDL válido para testes."""
    return {
        "spec_version": "0.1",
        "meta": {
            "name": "Test Plan",
        },
        "config": {
            "base_url": "https://api.example.com",
        },
        "steps": [
            {
                "id": "test_step",
                "action": "http_request",
                "params": {
                    "method": "GET",
                    "path": "/health",
                },
                "assertions": [
                    {
                        "type": "status_code",
                        "operator": "eq",
                        "value": 200,
                    }
                ],
            }
        ],
    }


@pytest.fixture
def temp_plan_file(valid_plan: dict[str, Any]) -> str:
    """Cria um arquivo temporário com plano válido."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(valid_plan, f)
        return f.name


# =============================================================================
# TESTES DE HELP E VERSION
# =============================================================================


class TestCliHelp:
    """Testes do help e version."""

    def test_help_shows_commands(self, runner: CliRunner) -> None:
        """Verifica que o help mostra os comandos disponíveis."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.output
        assert "generate" in result.output
        assert "validate" in result.output
        assert "run" in result.output

    def test_version_shows_version(self, runner: CliRunner) -> None:
        """Verifica que --version mostra a versão."""
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.3.0" in result.output

    def test_global_flags_in_help(self, runner: CliRunner) -> None:
        """Verifica flags globais no help."""
        result = runner.invoke(cli, ["--help"])

        assert "--verbose" in result.output
        assert "--quiet" in result.output
        assert "--json" in result.output


# =============================================================================
# TESTES DO COMANDO VALIDATE
# =============================================================================


class TestValidateCommand:
    """Testes do comando validate."""

    def test_validate_valid_plan(
        self, runner: CliRunner, temp_plan_file: str
    ) -> None:
        """Valida plano válido com sucesso."""
        result = runner.invoke(cli, ["validate", temp_plan_file])

        assert result.exit_code == 0
        assert "✅" in result.output or "Válido" in result.output

    def test_validate_invalid_json(self, runner: CliRunner) -> None:
        """Detecta JSON inválido."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{invalid json}")
            temp_file = f.name

        try:
            result = runner.invoke(cli, ["validate", temp_file])

            assert result.exit_code == 1
            assert "JSON" in result.output or "inválido" in result.output
        finally:
            os.unlink(temp_file)

    def test_validate_json_output(
        self, runner: CliRunner, temp_plan_file: str
    ) -> None:
        """Modo --json retorna JSON estruturado."""
        result = runner.invoke(cli, ["--json", "validate", temp_plan_file])

        assert result.exit_code == 0
        # Deve ser JSON válido
        try:
            output = json.loads(result.output)
            assert "success" in output
            assert "files" in output
        except json.JSONDecodeError:
            pytest.fail("Output não é JSON válido")

    def test_validate_missing_file(self, runner: CliRunner) -> None:
        """Erro quando arquivo não existe."""
        result = runner.invoke(cli, ["validate", "nonexistent.json"])

        assert result.exit_code != 0


# =============================================================================
# TESTES DO COMANDO INIT
# =============================================================================


class TestInitCommand:
    """Testes do comando init."""

    def test_init_creates_workspace(self, runner: CliRunner) -> None:
        """init cria estrutura .aqa/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["init", tmpdir])

            assert result.exit_code == 0

            # Verifica estrutura criada
            aqa_dir = Path(tmpdir) / ".aqa"
            assert aqa_dir.exists()
            assert (aqa_dir / "config.yaml").exists()
            assert (aqa_dir / "plans").exists()
            assert (aqa_dir / "reports").exists()

    def test_init_existing_fails_without_force(self, runner: CliRunner) -> None:
        """init falha em workspace existente sem --force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Cria workspace primeiro
            (Path(tmpdir) / ".aqa").mkdir()

            result = runner.invoke(cli, ["init", tmpdir])

            assert result.exit_code == 1 or "já existe" in result.output.lower()

    def test_init_with_force_overwrites(self, runner: CliRunner) -> None:
        """init --force sobrescreve workspace existente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Cria workspace vazio primeiro
            aqa_dir = Path(tmpdir) / ".aqa"
            aqa_dir.mkdir()

            result = runner.invoke(cli, ["init", "--force", tmpdir])

            assert result.exit_code == 0
            assert (aqa_dir / "config.yaml").exists()


# =============================================================================
# TESTES DE UTILITÁRIOS
# =============================================================================


class TestUtils:
    """Testes das funções utilitárias."""

    def test_get_runner_search_paths(self) -> None:
        """get_runner_search_paths retorna lista não vazia."""
        paths = get_runner_search_paths()

        assert isinstance(paths, list)
        assert len(paths) > 0

    def test_get_runner_path_with_override(self) -> None:
        """get_runner_path aceita override."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name

        try:
            result = get_runner_path(temp_file)
            assert result == Path(temp_file)
        finally:
            os.unlink(temp_file)

    def test_get_runner_path_from_env(self) -> None:
        """get_runner_path usa AQA_RUNNER_PATH."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name

        try:
            with patch.dict(os.environ, {"AQA_RUNNER_PATH": temp_file}):
                result = get_runner_path()
                assert result == Path(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_returns_empty_when_no_config(self) -> None:
        """load_config retorna dict vazio quando não há config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = load_config()
                assert config == {}
            finally:
                os.chdir(original_cwd)


# =============================================================================
# TESTES DE MODOS QUIET E VERBOSE
# =============================================================================


class TestOutputModes:
    """Testes dos modos de saída."""

    def test_quiet_mode_suppresses_output(
        self, runner: CliRunner, temp_plan_file: str
    ) -> None:
        """Modo --quiet suprime saída."""
        result = runner.invoke(cli, ["--quiet", "validate", temp_plan_file])

        # Deve ter menos output que modo normal
        assert result.exit_code == 0
        # Em modo quiet, não deve haver emoji ou decoração
        assert "🔍" not in result.output

    def test_verbose_mode_works(
        self, runner: CliRunner, temp_plan_file: str
    ) -> None:
        """Modo --verbose funciona."""
        result = runner.invoke(cli, ["--verbose", "validate", temp_plan_file])

        assert result.exit_code == 0
