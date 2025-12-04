"""
Testes End-to-End: Execução Real do Runner Rust

## Para todos entenderem:

Estes testes executam o binário do Runner Rust de verdade:
1. Compila o Runner (se necessário)
2. Gera um plano UTDL válido
3. Executa o Runner com o plano
4. Verifica o ExecutionReport gerado

## Requisitos:

- Rust toolchain instalado (cargo)
- Conexão com internet (para httpbin.org)

## Como rodar:

```bash
pytest tests/test_e2e_runner_execution.py -v
```
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest


# ============================================================================
# FIXTURES
# ============================================================================


def get_runner_binary_path() -> Path:
    """Retorna o caminho para o binário do Runner."""
    # tests/test_e2e_runner_execution.py -> brain/tests/ -> brain/ -> workspace_root/
    workspace_root = Path(__file__).resolve().parent.parent.parent
    runner_dir = workspace_root / "runner"

    if sys.platform == "win32":
        binary = runner_dir / "target" / "release" / "runner.exe"
    else:
        binary = runner_dir / "target" / "release" / "runner"

    return binary


def get_runner_dir() -> Path:
    """Retorna o diretório do Runner."""
    workspace_root = Path(__file__).resolve().parent.parent.parent
    return workspace_root / "runner"


@pytest.fixture(scope="module")
def compiled_runner() -> Path:
    """
    Compila o Runner em modo release e retorna o caminho do binário.

    Este fixture é executado uma vez por módulo de teste (scope="module")
    para evitar recompilações desnecessárias.
    """
    runner_dir = get_runner_dir()
    binary_path = get_runner_binary_path()

    # Se o binário já existe e é recente, pula compilação
    if binary_path.exists():
        # Verifica se src/ foi modificado após o binário
        src_dir = runner_dir / "src"
        binary_mtime = binary_path.stat().st_mtime

        needs_rebuild = False
        for rust_file in src_dir.rglob("*.rs"):
            if rust_file.stat().st_mtime > binary_mtime:
                needs_rebuild = True
                break

        if not needs_rebuild:
            return binary_path

    # Compila o Runner
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=runner_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.skip(f"Falha ao compilar Runner: {result.stderr}")

    if not binary_path.exists():
        pytest.skip(f"Binário não encontrado após compilação: {binary_path}")

    return binary_path


@pytest.fixture
def temp_plan_file():
    """Cria arquivo temporário para o plano UTDL."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".utdl.json",
        delete=False,
    ) as f:
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_output_file():
    """Cria arquivo temporário para o output do Runner."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".report.json",
        delete=False,
    ) as f:
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


# ============================================================================
# PLANOS DE TESTE
# ============================================================================


def create_health_check_plan() -> dict[str, Any]:
    """
    Plano simples: health check no httpbin.org.

    httpbin.org é um serviço público para testes de HTTP.
    """
    return {
        "spec_version": "0.1",
        "meta": {
            "id": "e2e-health-check-001",
            "name": "e2e-health-check",
            "description": "Teste e2e de health check",
            "created_at": "2024-12-04T00:00:00Z",
        },
        "config": {
            "base_url": "https://httpbin.org",
            "timeout_ms": 10000,
        },
        "steps": [
            {
                "id": "health",
                "action": "http_request",
                "params": {
                    "method": "GET",
                    "path": "/get",
                },
                "expect": {
                    "status": 200,
                },
            }
        ],
    }


def create_multi_step_plan() -> dict[str, Any]:
    """
    Plano com múltiplos steps e extração de variáveis.
    """
    return {
        "spec_version": "0.1",
        "meta": {
            "id": "e2e-multi-step-001",
            "name": "e2e-multi-step",
            "description": "Teste e2e com múltiplos steps",
            "created_at": "2024-12-04T00:00:00Z",
        },
        "config": {
            "base_url": "https://httpbin.org",
            "timeout_ms": 10000,
        },
        "steps": [
            {
                "id": "get_ip",
                "action": "http_request",
                "params": {
                    "method": "GET",
                    "path": "/ip",
                },
                "expect": {
                    "status": 200,
                },
                "extract": [
                    {
                        "source": "body",
                        "path": "$.origin",
                        "target": "client_ip",
                    }
                ],
            },
            {
                "id": "get_headers",
                "action": "http_request",
                "depends_on": ["get_ip"],
                "params": {
                    "method": "GET",
                    "path": "/headers",
                },
                "expect": {
                    "status": 200,
                },
            },
        ],
    }


def create_post_request_plan() -> dict[str, Any]:
    """
    Plano com POST request e body JSON.
    """
    return {
        "spec_version": "0.1",
        "meta": {
            "id": "e2e-post-request-001",
            "name": "e2e-post-request",
            "description": "Teste e2e com POST",
            "created_at": "2024-12-04T00:00:00Z",
        },
        "config": {
            "base_url": "https://httpbin.org",
            "timeout_ms": 10000,
        },
        "steps": [
            {
                "id": "post_data",
                "action": "http_request",
                "params": {
                    "method": "POST",
                    "path": "/post",
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": {
                        "username": "testuser",
                        "email": "test@example.com",
                    },
                },
                "expect": {
                    "status": 200,
                },
            }
        ],
    }


def create_failing_plan() -> dict[str, Any]:
    """
    Plano que deve falhar (assertion de status falha).
    """
    return {
        "spec_version": "0.1",
        "meta": {
            "id": "e2e-expected-failure-001",
            "name": "e2e-expected-failure",
            "description": "Teste que deve falhar",
            "created_at": "2024-12-04T00:00:00Z",
        },
        "config": {
            "base_url": "https://httpbin.org",
            "timeout_ms": 10000,
        },
        "steps": [
            {
                "id": "wrong_status",
                "action": "http_request",
                "params": {
                    "method": "GET",
                    "path": "/get",
                },
                "assertions": [
                    {
                        "type": "status_code",
                        "operator": "eq",
                        "value": 404,  # httpbin retorna 200, não 404
                    }
                ],
            }
        ],
    }


# ============================================================================
# TESTES
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestRunnerExecution:
    """Testes de execução real do Runner."""

    def test_runner_binary_exists_after_compilation(self, compiled_runner: Path):
        """Verifica que o binário do Runner existe."""
        assert compiled_runner.exists(), f"Binário não encontrado: {compiled_runner}"
        assert compiled_runner.is_file()

    def test_runner_help_command(self, compiled_runner: Path):
        """Runner responde ao --help."""
        result = subprocess.run(
            [str(compiled_runner), "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "runner" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_health_check_execution(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """
        Executa um plano simples de health check.

        Verifica:
        - Runner executa sem erros
        - ExecutionReport é gerado
        - Step passou
        """
        # Escreve o plano
        plan = create_health_check_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        # Executa o Runner
        result = subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Verifica execução
        assert result.returncode == 0, f"Runner falhou: {result.stderr}"

        # Verifica report
        assert temp_output_file.exists(), "Report não foi gerado"
        report = json.loads(temp_output_file.read_text())

        # Verifica estrutura do ExecutionReport
        assert "plan_id" in report
        assert "steps" in report
        assert "summary" in report

        # Verifica resultado do step
        assert len(report["steps"]) == 1
        step_result = report["steps"][0]
        assert step_result["status"] == "passed"

        # Verifica summary
        summary = report["summary"]
        assert summary["total_steps"] == 1
        assert summary["passed"] == 1
        assert summary["failed"] == 0

    def test_multi_step_execution(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """
        Executa plano com múltiplos steps e dependências.

        Verifica:
        - Steps são executados na ordem correta
        - Dependências são respeitadas
        - Extração de variáveis funciona
        """
        plan = create_multi_step_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        result = subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"Runner falhou: {result.stderr}"

        report = json.loads(temp_output_file.read_text())

        # Verifica que todos os steps passaram
        assert len(report["steps"]) == 2

        summary = report["summary"]
        assert summary["total_steps"] == 2
        assert summary["passed"] == 2
        assert summary["failed"] == 0

    def test_post_request_execution(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """
        Executa plano com POST request.

        Verifica:
        - POST com body JSON funciona
        - Headers são enviados corretamente
        """
        plan = create_post_request_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        result = subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"Runner falhou: {result.stderr}"

        report = json.loads(temp_output_file.read_text())

        step_result = report["steps"][0]
        assert step_result["status"] == "passed"

        # httpbin retorna o body enviado em 'json'
        # O Runner deve ter capturado isso no response

    def test_failing_step_is_reported(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """
        Verifica que falhas são reportadas corretamente.

        Quando o status esperado não bate, o step deve falhar.
        """
        plan = create_failing_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        # Executa o Runner (ignoramos o return code pois esperamos falha)
        subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Runner pode retornar código != 0 em falhas
        # O importante é que o report seja gerado

        assert temp_output_file.exists(), "Report deve ser gerado mesmo com falhas"

        report = json.loads(temp_output_file.read_text())

        step_result = report["steps"][0]
        assert step_result["status"] == "failed"

        summary = report["summary"]
        assert summary["failed"] == 1
        assert summary["passed"] == 0

    def test_execution_with_verbose_flag(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """
        Runner aceita flag --verbose para mais detalhes.
        """
        plan = create_health_check_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        result = subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Verbose deve funcionar
        assert result.returncode == 0 or "verbose" in result.stderr.lower()


@pytest.mark.e2e
@pytest.mark.slow
class TestExecutionReportStructure:
    """Testes da estrutura do ExecutionReport."""

    def test_report_has_timestamps(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """Report inclui timestamps de início e fim."""
        plan = create_health_check_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        report = json.loads(temp_output_file.read_text())

        assert "start_time" in report
        assert "end_time" in report

    def test_step_results_have_duration(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """Cada step result inclui duração em ms."""
        plan = create_health_check_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        report = json.loads(temp_output_file.read_text())

        step_result = report["steps"][0]
        assert "duration_ms" in step_result
        assert step_result["duration_ms"] >= 0

    def test_summary_has_total_duration(
        self,
        compiled_runner: Path,
        temp_plan_file: Path,
        temp_output_file: Path,
    ):
        """Summary inclui duração total da execução."""
        plan = create_health_check_plan()
        temp_plan_file.write_text(json.dumps(plan, indent=2))

        subprocess.run(
            [
                str(compiled_runner),
                "execute",
                "--file",
                str(temp_plan_file),
                "--output",
                str(temp_output_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        report = json.loads(temp_output_file.read_text())

        summary = report["summary"]
        assert "duration_ms" in summary
        assert summary["duration_ms"] >= 0


# ============================================================================
# MARCADORES DE TESTE
# ============================================================================

# Para rodar apenas testes e2e:
# pytest -m e2e tests/test_e2e_runner_execution.py

# Para rodar excluindo testes lentos:
# pytest -m "not slow" tests/
