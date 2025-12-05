"""
================================================================================
Validação de Limites de Execução
================================================================================

Valida limites de plano ANTES de enviar ao Runner, evitando
que planos inválidos cheguem ao executor.

## Limites Padrão (compatíveis com Runner):

| Limite             | Padrão | Descrição                           |
|--------------------|--------|-------------------------------------|
| max_steps          | 100    | Máximo de steps por plano           |
| max_parallel       | 10     | Máximo de steps paralelos           |
| max_retries_total  | 50     | Máximo de retries no plano todo     |
| max_execution_secs | 300    | Timeout total de execução (5 min)   |
| max_step_timeout   | 30     | Timeout por step (segundos)         |

## Por que validar no Brain?

1. **Fail Fast**: Detecta problemas antes de executar
2. **Feedback imediato**: Usuário sabe o que corrigir
3. **Economia**: Não desperdiça recursos do Runner
4. **UX**: Mensagens de erro mais úteis
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .codes import ErrorCodes, Severity
from .structured import StructuredError


# =============================================================================
# LIMITES PADRÃO (compatíveis com Runner)
# =============================================================================

DEFAULT_MAX_STEPS = 100
DEFAULT_MAX_PARALLEL = 10
DEFAULT_MAX_RETRIES_TOTAL = 50
DEFAULT_MAX_EXECUTION_SECS = 300  # 5 minutos
DEFAULT_MAX_STEP_TIMEOUT_SECS = 30


@dataclass
class ExecutionLimits:
    """
    Configuração de limites de execução.

    Espelha os limites do Runner para validação antecipada.

    ## Atributos:

    - `max_steps`: Máximo de steps no plano
    - `max_parallel`: Máximo de steps paralelos
    - `max_retries_total`: Soma de max_attempts de todos os steps
    - `max_execution_secs`: Timeout total em segundos
    - `max_step_timeout_secs`: Timeout máximo por step

    ## Exemplo:

        >>> limits = ExecutionLimits.from_env()
        >>> violations = validate_plan_limits(plan, limits)
    """
    max_steps: int = DEFAULT_MAX_STEPS
    max_parallel: int = DEFAULT_MAX_PARALLEL
    max_retries_total: int = DEFAULT_MAX_RETRIES_TOTAL
    max_execution_secs: int = DEFAULT_MAX_EXECUTION_SECS
    max_step_timeout_secs: int = DEFAULT_MAX_STEP_TIMEOUT_SECS

    @classmethod
    def from_env(cls) -> "ExecutionLimits":
        """
        Carrega limites de variáveis de ambiente.

        Variáveis suportadas (mesmas do Runner):
        - RUNNER_MAX_STEPS
        - RUNNER_MAX_PARALLEL
        - RUNNER_MAX_RETRIES
        - RUNNER_MAX_EXECUTION_SECS
        - RUNNER_MAX_STEP_TIMEOUT
        """
        limits = cls()

        if val := os.environ.get("RUNNER_MAX_STEPS"):
            try:
                limits.max_steps = int(val)
            except ValueError:
                pass

        if val := os.environ.get("RUNNER_MAX_PARALLEL"):
            try:
                limits.max_parallel = int(val)
            except ValueError:
                pass

        if val := os.environ.get("RUNNER_MAX_RETRIES"):
            try:
                limits.max_retries_total = int(val)
            except ValueError:
                pass

        if val := os.environ.get("RUNNER_MAX_EXECUTION_SECS"):
            try:
                limits.max_execution_secs = int(val)
            except ValueError:
                pass

        if val := os.environ.get("RUNNER_MAX_STEP_TIMEOUT"):
            try:
                limits.max_step_timeout_secs = int(val)
            except ValueError:
                pass

        return limits

    @classmethod
    def strict(cls) -> "ExecutionLimits":
        """Limites restritivos para testes."""
        return cls(
            max_steps=10,
            max_parallel=2,
            max_retries_total=5,
            max_execution_secs=30,
            max_step_timeout_secs=5,
        )

    @classmethod
    def relaxed(cls) -> "ExecutionLimits":
        """Limites permissivos para desenvolvimento."""
        return cls(
            max_steps=500,
            max_parallel=50,
            max_retries_total=200,
            max_execution_secs=3600,  # 1 hora
            max_step_timeout_secs=120,
        )

    def to_dict(self) -> dict[str, int]:
        """Converte para dicionário."""
        return {
            "max_steps": self.max_steps,
            "max_parallel": self.max_parallel,
            "max_retries_total": self.max_retries_total,
            "max_execution_secs": self.max_execution_secs,
            "max_step_timeout_secs": self.max_step_timeout_secs,
        }


@dataclass
class LimitViolation:
    """
    Violação de limite detectada.

    ## Atributos:

    - `limit_name`: Nome do limite violado
    - `limit_value`: Valor do limite
    - `actual_value`: Valor encontrado no plano
    - `path`: Caminho JSON relacionado
    - `severity`: Severidade da violação
    """
    limit_name: str
    limit_value: int
    actual_value: int
    path: str = "$.steps"
    severity: Severity = Severity.ERROR

    def to_structured_error(self) -> StructuredError:
        """Converte para StructuredError."""
        code_map = {
            "max_steps": ErrorCodes.PLAN_EXCEEDS_MAX_STEPS,
            "max_parallel": ErrorCodes.PLAN_EXCEEDS_MAX_PARALLEL,
            "max_retries_total": ErrorCodes.PLAN_EXCEEDS_MAX_RETRIES,
            "max_execution_secs": ErrorCodes.PLAN_EXCEEDS_TIMEOUT,
        }

        code = code_map.get(self.limit_name, ErrorCodes.PLAN_EXCEEDS_MAX_STEPS)
        exceeded_by = self.actual_value - self.limit_value

        return StructuredError(
            code=code,
            message=f"{self.limit_name} excedido: {self.actual_value} > {self.limit_value}",
            path=self.path,
            suggestion=f"Reduza para no máximo {self.limit_value} (excede em {exceeded_by})",
            context={
                "limit": self.limit_value,
                "actual": self.actual_value,
                "exceeded_by": exceeded_by,
            },
            severity=self.severity,
        )


def validate_plan_limits(
    plan: dict[str, Any],
    limits: ExecutionLimits | None = None,
) -> list[LimitViolation]:
    """
    Valida um plano contra os limites de execução.

    ## Parâmetros:

    - `plan`: Plano UTDL (dict)
    - `limits`: Limites a usar (None = carrega do ambiente)

    ## Retorno:

    Lista de violações encontradas (vazia se OK).

    ## Exemplo:

        >>> violations = validate_plan_limits(plan)
        >>> if violations:
        ...     for v in violations:
        ...         print(f"{v.limit_name}: {v.actual_value} > {v.limit_value}")
    """
    if limits is None:
        limits = ExecutionLimits.from_env()

    violations: list[LimitViolation] = []
    steps = plan.get("steps", [])

    # =========================================================================
    # Validação: max_steps
    # =========================================================================

    if len(steps) > limits.max_steps:
        violations.append(LimitViolation(
            limit_name="max_steps",
            limit_value=limits.max_steps,
            actual_value=len(steps),
            path="$.steps",
        ))

    # =========================================================================
    # Validação: max_retries_total
    # =========================================================================

    total_retries: int = 0
    for step in steps:
        retry_config = step.get("retry", {})
        max_attempts: int = int(retry_config.get("max_attempts", 1)) if isinstance(retry_config, dict) else 1
        total_retries += max_attempts

    if total_retries > limits.max_retries_total:
        violations.append(LimitViolation(
            limit_name="max_retries_total",
            limit_value=limits.max_retries_total,
            actual_value=total_retries,
            path="$.steps[*].retry.max_attempts",
        ))

    # =========================================================================
    # Validação: max_parallel (estimativa)
    # =========================================================================

    # Conta steps sem dependências (podem executar em paralelo)
    parallel_start = sum(1 for step in steps if not step.get("depends_on"))

    if parallel_start > limits.max_parallel:
        violations.append(LimitViolation(
            limit_name="max_parallel",
            limit_value=limits.max_parallel,
            actual_value=parallel_start,
            path="$.steps[*].depends_on",
            severity=Severity.WARNING,  # Warning pois é estimativa
        ))

    # =========================================================================
    # Validação: max_execution_secs (estimativa)
    # =========================================================================

    # Estima tempo total: soma de timeouts * retries
    # Isso é uma estimativa conservadora (pior caso)
    estimated_time: float = 0.0
    for step in steps:
        # action pode ser string ou dict dependendo do formato do plano
        action_raw = step.get("action", {})
        action: dict[str, Any] = {} if isinstance(action_raw, str) else action_raw

        # Timeout do step
        timeout_ms = action.get("timeout_ms", limits.max_step_timeout_secs * 1000)
        step_timeout: float = float(timeout_ms) / 1000 if timeout_ms else limits.max_step_timeout_secs

        # Retries
        retry_config = step.get("retry", {})
        step_max_attempts: int = int(retry_config.get("max_attempts", 1)) if isinstance(retry_config, dict) else 1

        # Wait/Sleep
        action_type = action_raw if isinstance(action_raw, str) else action.get("type")
        if action_type in ("wait", "sleep"):
            duration_ms = action.get("duration_ms", 0)
            step_timeout = max(step_timeout, float(duration_ms) / 1000)

        estimated_time += step_timeout * step_max_attempts

    if estimated_time > limits.max_execution_secs:
        violations.append(LimitViolation(
            limit_name="max_execution_secs",
            limit_value=limits.max_execution_secs,
            actual_value=int(estimated_time),
            path="$.steps",
            severity=Severity.WARNING,  # Warning pois é estimativa
        ))

    return violations


def validate_step_limits(
    step: dict[str, Any],
    step_index: int,
    limits: ExecutionLimits | None = None,
) -> list[StructuredError]:
    """
    Valida um step individual contra limites.

    ## Parâmetros:

    - `step`: Step UTDL (dict)
    - `step_index`: Índice do step no array
    - `limits`: Limites a usar

    ## Retorno:

    Lista de erros/warnings encontrados.
    """
    if limits is None:
        limits = ExecutionLimits.from_env()

    errors: list[StructuredError] = []
    action = step.get("action", {})

    # Valida timeout do step
    timeout_ms = action.get("timeout_ms", 0)
    if timeout_ms > limits.max_step_timeout_secs * 1000:
        errors.append(StructuredError(
            code=ErrorCodes.EXECUTION_TIMEOUT_EXCEEDED,
            message=f"Step timeout ({timeout_ms}ms) excede limite ({limits.max_step_timeout_secs * 1000}ms)",
            path=f"$.steps[{step_index}].action.timeout_ms",
            suggestion=f"Reduza timeout para no máximo {limits.max_step_timeout_secs * 1000}ms",
            severity=Severity.WARNING,
        ))

    # Valida retries do step
    retry_config = step.get("retry", {})
    max_attempts = retry_config.get("max_attempts", 1)
    if max_attempts > 10:  # Limite razoável por step
        errors.append(StructuredError(
            code=ErrorCodes.MAX_RETRIES_EXCEEDED,
            message=f"Step tem muitos retries ({max_attempts})",
            path=f"$.steps[{step_index}].retry.max_attempts",
            suggestion="Considere no máximo 5-10 retries por step",
            severity=Severity.WARNING,
        ))

    return errors
