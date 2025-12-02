"""
Módulo de Integração com o Runner.

Este módulo executa planos UTDL chamando o Runner Rust via subprocess.
Funciona como a "cola" entre o Brain (Python) e o Runner (Rust).

Funcionalidades:
- Serialização automática do plano para arquivo temporário
- Execução do Runner com timeout configurável
- Parsing do relatório de execução JSON
- Limpeza automática de arquivos temporários
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..validator import Plan


@dataclass
class StepResult:
    """
    Resultado da execução de um único step.

    Attributes:
        step_id: Identificador do step executado
        status: Status da execução ("success" ou "failed")
        duration_ms: Tempo de execução em milissegundos
        error: Mensagem de erro, se houver falha
    """

    step_id: str
    status: str
    duration_ms: float
    error: str | None = None


@dataclass
class RunnerResult:
    """
    Resultado da execução de um plano completo.

    Contém informações agregadas sobre a execução, incluindo
    estatísticas de sucesso/falha e resultados individuais de cada step.

    Attributes:
        plan_id: ID único do plano executado
        plan_name: Nome legível do plano
        total_steps: Número total de steps
        passed: Número de steps que passaram
        failed: Número de steps que falharam
        skipped: Número de steps pulados
        total_duration_ms: Tempo total de execução em ms
        steps: Lista de resultados individuais
        raw_report: Relatório JSON bruto do Runner
    """

    plan_id: str
    plan_name: str
    total_steps: int
    passed: int
    failed: int
    skipped: int
    total_duration_ms: float
    steps: list[StepResult] = field(default_factory=list)  # type: ignore[var-annotated]
    raw_report: dict[str, Any] = field(default_factory=dict)  # type: ignore[var-annotated]

    @property
    def success(self) -> bool:
        """Retorna True se nenhum step falhou."""
        return self.failed == 0

    def summary(self) -> str:
        """
        Gera um resumo formatado da execução.

        Returns:
            String multilinha com status, contadores e duração
        """
        status = "✓ PASSOU" if self.success else "✗ FALHOU"
        return (
            f"{status} | {self.plan_name}\n"
            f"Steps: {self.passed}/{self.total_steps} passaram, "
            f"{self.failed} falharam, {self.skipped} pulados\n"
            f"Duração: {self.total_duration_ms:.2f}ms"
        )


def run_plan(
    plan: Plan,
    runner_path: str | None = None,
    timeout: int = 60,
) -> RunnerResult:
    """
    Executa um plano UTDL usando o Runner Rust.

    Esta função:
    1. Serializa o plano para um arquivo temporário
    2. Executa o binário do Runner com os argumentos apropriados
    3. Lê e parseia o relatório de saída
    4. Limpa os arquivos temporários

    Args:
        plan: Objeto Plan validado
        runner_path: Caminho para o executável do Runner.
            Se None, procura automaticamente em target/release ou target/debug.
        timeout: Timeout de execução em segundos

    Returns:
        RunnerResult com detalhes da execução

    Raises:
        RuntimeError: Se o Runner não for encontrado, timeout, ou falha no parse

    Example:
        >>> plan = Plan(...)
        >>> result = run_plan(plan)
        >>> if result.success:
        ...     print("Todos os testes passaram!")
    """
    # Determina o caminho do Runner
    if runner_path is None:
        # Tenta release primeiro, depois debug
        project_root = Path(__file__).parent.parent.parent.parent.parent
        release_path = project_root / "runner" / "target" / "release" / "runner.exe"
        debug_path = project_root / "runner" / "target" / "debug" / "runner.exe"

        if release_path.exists():
            runner_path = str(release_path)
        elif debug_path.exists():
            runner_path = str(debug_path)
        else:
            raise RuntimeError(
                "Runner não encontrado. Por favor, compile o Runner primeiro:\n"
                "  cd runner && cargo build --release"
            )

    # Escreve o plano em arquivo temporário
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as plan_file:
        plan_file.write(plan.to_json())
        plan_path = plan_file.name

    # Cria arquivo temporário para o relatório
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as report_file:
        report_path = report_file.name

    try:
        # Executa o Runner
        subprocess.run(
            [
                runner_path,
                "execute",
                "--file",
                plan_path,
                "--output",
                report_path,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Não lança exceção em exit code não-zero
        )

        # Lê o relatório
        report_text = Path(report_path).read_text(encoding="utf-8")
        report: dict[str, Any] = json.loads(report_text)

        # Parseia os resultados
        return _parse_report(report)

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Runner excedeu timeout de {timeout} segundos") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Falha ao parsear relatório do Runner: {exc}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"Executável do Runner não encontrado: {runner_path}") from exc
    finally:
        # Limpa arquivos temporários
        Path(plan_path).unlink(missing_ok=True)
        Path(report_path).unlink(missing_ok=True)


def _parse_report(report: dict[str, Any]) -> RunnerResult:
    """
    Parseia o relatório JSON do Runner para um RunnerResult.

    Args:
        report: Dicionário com o relatório bruto do Runner

    Returns:
        Objeto RunnerResult com os dados estruturados
    """
    plan_info: dict[str, Any] = report.get("plan", {})
    summary: dict[str, Any] = report.get("summary", {})

    steps: list[StepResult] = []
    for step_result in report.get("results", []):
        steps.append(
            StepResult(
                step_id=step_result.get("step_id", "unknown"),
                status=step_result.get("status", "unknown"),
                duration_ms=step_result.get("duration_ms", 0),
                error=step_result.get("error"),
            )
        )

    return RunnerResult(
        plan_id=plan_info.get("id", "unknown"),
        plan_name=plan_info.get("name", "Plano Desconhecido"),
        total_steps=summary.get("total", len(steps)),
        passed=summary.get("passed", 0),
        failed=summary.get("failed", 0),
        skipped=summary.get("skipped", 0),
        total_duration_ms=summary.get("total_duration_ms", 0),
        steps=steps,
        raw_report=report,
    )
