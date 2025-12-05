"""
================================================================================
Testes: Sistema de Erros Unificados
================================================================================

Testes para o módulo de erros estruturados, incluindo:
- ErrorCodes: Códigos de erro padronizados
- StructuredError: Erros com contexto rico
- ExecutionLimits: Validação de limites
"""

from __future__ import annotations

import pytest
from typing import Any

from src.errors import (
    ErrorCode,
    ErrorCodes,
    ErrorCategory,
    Severity,
    StructuredError,
    ValidationError,
    ConfigurationError,
    GenerationError,
    ExecutionLimits,
    LimitViolation,
    validate_plan_limits,
    format_error,
    format_errors_for_json,
    format_errors_for_cli,
)


# =============================================================================
# TESTES: ErrorCode
# =============================================================================


class TestErrorCode:
    """Testes para ErrorCode."""

    def test_error_code_formatted(self) -> None:
        """Código deve ser formatado como E1001."""
        code = ErrorCodes.EMPTY_PLAN
        assert code.formatted == "E1001"

    def test_error_code_category(self) -> None:
        """Categoria deve ser extraída do código."""
        assert ErrorCodes.EMPTY_PLAN.category == ErrorCategory.VALIDATION
        assert ErrorCodes.RUNNER_NOT_FOUND.category == ErrorCategory.CONFIGURATION
        assert ErrorCodes.INTERNAL_ERROR.category == ErrorCategory.INTERNAL

    def test_error_code_severity(self) -> None:
        """Severidade padrão deve estar correta."""
        assert ErrorCodes.EMPTY_PLAN.severity == Severity.ERROR
        assert ErrorCodes.UNKNOWN_ACTION.severity == Severity.WARNING

    def test_get_by_code(self) -> None:
        """Busca por código numérico."""
        code = ErrorCodes.get_by_code(1001)
        assert code is not None
        assert code.name == "EMPTY_PLAN"

    def test_get_by_name(self) -> None:
        """Busca por nome."""
        code = ErrorCodes.get_by_name("CIRCULAR_DEPENDENCY")
        assert code is not None
        assert code.code == 1006


# =============================================================================
# TESTES: StructuredError
# =============================================================================


class TestStructuredError:
    """Testes para StructuredError."""

    def test_structured_error_creation(self) -> None:
        """Cria erro estruturado com todos os campos."""
        error = StructuredError(
            code=ErrorCodes.UNKNOWN_DEPENDENCY,
            message="Step 'step2' depende de 'step_inexistente'",
            path="$.steps[1].depends_on[0]",
            suggestion="Verifique o ID da dependência",
            context={"step_id": "step2"},
        )

        assert error.code == ErrorCodes.UNKNOWN_DEPENDENCY
        assert "step2" in error.message
        assert error.path == "$.steps[1].depends_on[0]"
        assert error.suggestion is not None

    def test_structured_error_str(self) -> None:
        """Representação string inclui código e path."""
        error = StructuredError(
            code=ErrorCodes.EMPTY_PLAN,
            message="Plano vazio",
            path="$.steps",
        )

        result = str(error)
        assert "E1001" in result
        assert "$.steps" in result

    def test_to_dict(self) -> None:
        """Converte para dicionário."""
        error = StructuredError(
            code=ErrorCodes.CIRCULAR_DEPENDENCY,
            message="Ciclo detectado",
            path="$.steps",
            suggestion="Remova o ciclo",
            context={"cycle": ["a", "b", "a"]},
        )

        result = error.to_dict()

        assert result["code"] == "E1006"
        assert result["name"] == "CIRCULAR_DEPENDENCY"
        assert result["path"] == "$.steps"
        assert result["suggestion"] == "Remova o ciclo"
        assert result["context"]["cycle"] == ["a", "b", "a"]


# =============================================================================
# TESTES: ValidationError (helpers)
# =============================================================================


class TestValidationErrorHelpers:
    """Testes para helpers de ValidationError."""

    def test_missing_field(self) -> None:
        """Cria erro de campo ausente."""
        error = ValidationError.missing_field(
            field_name="action",
            path="$.steps[0]",
            parent_type="step",
        )

        assert error.code == ErrorCodes.MISSING_REQUIRED_FIELD
        assert "action" in error.message
        assert error.path == "$.steps[0]"

    def test_unknown_dependency_with_suggestions(self) -> None:
        """Erro de dependência inclui sugestões."""
        error = ValidationError.unknown_dependency(
            step_id="step2",
            dependency_id="step_1",
            path="$.steps[1].depends_on[0]",
            available_ids=["step1", "step3", "step4"],
        )

        assert error.code == ErrorCodes.UNKNOWN_DEPENDENCY
        assert "step1" in error.suggestion  # Sugestão similar

    def test_circular_dependency(self) -> None:
        """Erro de ciclo inclui os steps envolvidos."""
        error = ValidationError.circular_dependency(
            cycle=["step1", "step2", "step1"],
            path="$.steps",
        )

        assert error.code == ErrorCodes.CIRCULAR_DEPENDENCY
        assert "step1 → step2 → step1" in error.message

    def test_duplicate_id(self) -> None:
        """Erro de ID duplicado inclui índices."""
        error = ValidationError.duplicate_id(
            step_id="login",
            first_index=0,
            second_index=5,
        )

        assert error.code == ErrorCodes.DUPLICATE_STEP_ID
        assert "steps[0]" in error.message
        assert "steps[5]" in error.message


# =============================================================================
# TESTES: ExecutionLimits
# =============================================================================


class TestExecutionLimits:
    """Testes para ExecutionLimits."""

    def test_default_limits(self) -> None:
        """Limites padrão estão corretos."""
        limits = ExecutionLimits()

        assert limits.max_steps == 100
        assert limits.max_parallel == 10
        assert limits.max_retries_total == 50
        assert limits.max_execution_secs == 300
        assert limits.max_step_timeout_secs == 30

    def test_strict_limits(self) -> None:
        """Limites strict são mais restritivos."""
        limits = ExecutionLimits.strict()

        assert limits.max_steps == 10
        assert limits.max_parallel == 2

    def test_relaxed_limits(self) -> None:
        """Limites relaxed são mais permissivos."""
        limits = ExecutionLimits.relaxed()

        assert limits.max_steps == 500
        assert limits.max_parallel == 50

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Carrega limites de variáveis de ambiente."""
        monkeypatch.setenv("RUNNER_MAX_STEPS", "50")
        monkeypatch.setenv("RUNNER_MAX_PARALLEL", "5")

        limits = ExecutionLimits.from_env()

        assert limits.max_steps == 50
        assert limits.max_parallel == 5

    def test_to_dict(self) -> None:
        """Converte para dicionário."""
        limits = ExecutionLimits()
        result = limits.to_dict()

        assert "max_steps" in result
        assert "max_parallel" in result
        assert result["max_steps"] == 100


# =============================================================================
# TESTES: validate_plan_limits
# =============================================================================


class TestValidatePlanLimits:
    """Testes para validate_plan_limits."""

    def test_plan_within_limits(self) -> None:
        """Plano dentro dos limites não gera violações."""
        plan: dict[str, Any] = {
            "steps": [
                {"id": f"step{i}", "action": {"type": "http_request"}}
                for i in range(5)
            ]
        }

        violations = validate_plan_limits(plan)

        assert len(violations) == 0

    def test_plan_exceeds_max_steps(self) -> None:
        """Detecta plano com muitos steps."""
        limits = ExecutionLimits(max_steps=10)
        plan: dict[str, Any] = {
            "steps": [
                {"id": f"step{i}", "action": {"type": "http_request"}}
                for i in range(15)
            ]
        }

        violations = validate_plan_limits(plan, limits)

        # Verifica que max_steps está entre as violações
        steps_violation = next(
            (v for v in violations if v.limit_name == "max_steps"),
            None,
        )
        assert steps_violation is not None
        assert steps_violation.actual_value == 15
        assert steps_violation.limit_value == 10

    def test_plan_exceeds_max_retries(self) -> None:
        """Detecta plano com muitos retries."""
        limits = ExecutionLimits(max_retries_total=10)
        plan: dict[str, Any] = {
            "steps": [
                {
                    "id": f"step{i}",
                    "action": {"type": "http_request"},
                    "retry": {"max_attempts": 5},
                }
                for i in range(5)  # 5 * 5 = 25 retries
            ]
        }

        violations = validate_plan_limits(plan, limits)

        retry_violation = next(
            (v for v in violations if v.limit_name == "max_retries_total"),
            None,
        )
        assert retry_violation is not None
        assert retry_violation.actual_value == 25

    def test_plan_exceeds_parallel(self) -> None:
        """Detecta plano com muitos steps paralelos."""
        limits = ExecutionLimits(max_parallel=2)
        plan: dict[str, Any] = {
            "steps": [
                {"id": f"step{i}", "action": {"type": "http_request"}}
                for i in range(5)  # 5 steps sem dependências
            ]
        }

        violations = validate_plan_limits(plan, limits)

        parallel_violation = next(
            (v for v in violations if v.limit_name == "max_parallel"),
            None,
        )
        assert parallel_violation is not None
        assert parallel_violation.severity == Severity.WARNING

    def test_limit_violation_to_structured_error(self) -> None:
        """LimitViolation converte para StructuredError."""
        violation = LimitViolation(
            limit_name="max_steps",
            limit_value=100,
            actual_value=150,
            path="$.steps",
        )

        error = violation.to_structured_error()

        assert error.code == ErrorCodes.PLAN_EXCEEDS_MAX_STEPS
        assert "150 > 100" in error.message
        assert error.path == "$.steps"


# =============================================================================
# TESTES: Formatação de Erros
# =============================================================================


class TestErrorFormatting:
    """Testes para formatação de erros."""

    def test_format_error_basic(self) -> None:
        """Formata erro básico."""
        error = StructuredError(
            code=ErrorCodes.EMPTY_PLAN,
            message="Plano vazio",
        )

        result = format_error(error)

        assert "E1001" in result
        assert "Plano vazio" in result

    def test_format_error_with_path(self) -> None:
        """Formata erro com path."""
        error = StructuredError(
            code=ErrorCodes.UNKNOWN_DEPENDENCY,
            message="Dependência inválida",
            path="$.steps[0].depends_on[0]",
        )

        result = format_error(error)

        assert "$.steps[0].depends_on[0]" in result

    def test_format_error_with_suggestion(self) -> None:
        """Formata erro com sugestão."""
        error = StructuredError(
            code=ErrorCodes.MISSING_REQUIRED_FIELD,
            message="Campo ausente",
            suggestion="Adicione o campo obrigatório",
        )

        result = format_error(error)

        assert "Adicione" in result
        assert "💡" in result

    def test_format_errors_for_json(self) -> None:
        """Formata lista de erros para JSON."""
        errors = [
            StructuredError(
                code=ErrorCodes.EMPTY_PLAN,
                message="Erro 1",
            ),
            StructuredError(
                code=ErrorCodes.UNKNOWN_ACTION,
                message="Warning 1",
                severity=Severity.WARNING,
            ),
        ]

        result = format_errors_for_json(errors)

        assert result["success"] is False  # Tem erro
        assert len(result["errors"]) == 2
        assert result["summary"]["total"] == 2
        assert result["summary"]["by_severity"]["error"] == 1
        assert result["summary"]["by_severity"]["warning"] == 1

    def test_format_errors_for_cli_empty(self) -> None:
        """Lista vazia mostra mensagem de sucesso."""
        result = format_errors_for_cli([])
        assert "Nenhum erro" in result

    def test_format_errors_for_cli_grouped(self) -> None:
        """Agrupa erros por severidade."""
        errors = [
            StructuredError(code=ErrorCodes.EMPTY_PLAN, message="Erro"),
            StructuredError(
                code=ErrorCodes.UNKNOWN_ACTION,
                message="Warning",
                severity=Severity.WARNING,
            ),
        ]

        result = format_errors_for_cli(errors, group_by_severity=True)

        # Verifica que erros aparecem antes de warnings
        error_pos = result.find("ERROR")
        warning_pos = result.find("WARNING")
        assert error_pos < warning_pos


# =============================================================================
# TESTES: Integração com UTDLValidator
# =============================================================================


class TestValidatorIntegration:
    """Testes de integração com UTDLValidator."""

    def _make_valid_plan(self, num_steps: int = 5) -> dict[str, Any]:
        """Cria um plano válido para testes."""
        return {
            "spec_version": "0.1",
            "meta": {
                "name": "Test Plan",
                "description": "A test plan",
            },
            "config": {
                "base_url": "https://api.example.com",
            },
            "steps": [
                {
                    "id": f"step{i}",
                    "action": "http_request",
                    "params": {"method": "GET", "path": f"/test/{i}"},
                }
                for i in range(num_steps)
            ],
        }

    def test_validator_validates_limits(self) -> None:
        """Validator valida limites por padrão."""
        from src.errors import ExecutionLimits
        from src.validator import UTDLValidator

        limits = ExecutionLimits(max_steps=5)
        validator = UTDLValidator(
            validate_limits=True,
            execution_limits=limits,
        )

        # Plano com 10 steps, mas limite é 5
        plan = self._make_valid_plan(num_steps=10)

        result = validator.validate(plan)

        # Deve ter warning sobre limite excedido
        has_limit_warning = any("max_steps" in w for w in result.warnings)
        has_limit_error = any("max_steps" in e for e in result.errors)

        assert has_limit_warning or has_limit_error, f"Expected limit warning/error. Errors: {result.errors}, Warnings: {result.warnings}"

    def test_validator_structured_errors(self) -> None:
        """Validator popula structured_errors."""
        from src.errors import ExecutionLimits
        from src.validator import UTDLValidator

        limits = ExecutionLimits(max_steps=5)
        validator = UTDLValidator(
            validate_limits=True,
            execution_limits=limits,
        )

        # Plano com 10 steps, mas limite é 5
        plan = self._make_valid_plan(num_steps=10)

        result = validator.validate(plan)

        # structured_errors deve estar populado
        assert len(result.structured_errors) > 0, f"Expected structured_errors. Result: {result}"
        assert hasattr(result.structured_errors[0], "to_dict")

    def test_get_errors_with_paths(self) -> None:
        """get_errors_with_paths retorna erros com paths."""
        from src.errors import ExecutionLimits
        from src.validator import UTDLValidator

        limits = ExecutionLimits(max_steps=5)
        validator = UTDLValidator(
            validate_limits=True,
            execution_limits=limits,
        )

        # Plano com 10 steps, mas limite é 5
        plan = self._make_valid_plan(num_steps=10)

        result = validator.validate(plan)
        errors_with_paths = result.get_errors_with_paths()

        assert len(errors_with_paths) > 0
        assert "path" in errors_with_paths[0]
