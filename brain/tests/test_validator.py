"""
Testes Unitários para os Modelos Validadores UTDL.

Este módulo contém testes para garantir que os modelos Pydantic
validam corretamente planos UTDL, incluindo:
- Validação de tipos e valores
- Detecção de dependências inválidas
- Detecção de ciclos no grafo de dependências
- Serialização/deserialização
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Adiciona o diretório brain ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validator import Assertion, Config, Meta, Plan, Step


class TestAssertion:
    """Testes para o modelo Assertion."""

    def test_valid_status_code_assertion(self) -> None:
        """Testa criação de assertion de status_code válida."""
        assertion = Assertion(type="status_code", operator="eq", value=200)
        assert assertion.type == "status_code"
        assert assertion.operator == "eq"
        assert assertion.value == 200

    def test_valid_json_body_assertion_with_path(self) -> None:
        """Testa assertion json_body com path JSONPath."""
        assertion = Assertion(
            type="json_body",
            operator="eq",
            value="test",
            path="data.name",
        )
        assert assertion.path == "data.name"

    def test_invalid_assertion_type(self) -> None:
        """Testa que tipo inválido levanta ValidationError."""
        with pytest.raises(ValidationError):
            Assertion(type="invalid_type", operator="eq", value=200)  # type: ignore[arg-type]


class TestStep:
    """Testes para o modelo Step."""

    def test_valid_step(self) -> None:
        """Testa criação de step válido."""
        step = Step(
            id="step_1",
            action="http_request",
            params={"method": "GET", "path": "/test"},
        )
        assert step.id == "step_1"
        assert step.action == "http_request"

    def test_empty_id_raises_error(self) -> None:
        """Testa que ID vazio levanta ValidationError."""
        with pytest.raises(ValidationError):
            Step(
                id="",
                action="http_request",
                params={"method": "GET", "path": "/test"},
            )

    def test_invalid_action_raises_error(self) -> None:
        """Testa que ação inválida levanta ValidationError."""
        with pytest.raises(ValidationError):
            Step(
                id="step_1",
                action="invalid_action",  # type: ignore[arg-type]
                params={},
            )


class TestPlan:
    """Testes para o modelo Plan."""

    def test_valid_minimal_plan(self) -> None:
        """Testa criação de plano mínimo válido."""
        plan = Plan(
            meta=Meta(name="Plano de Teste"),
            config=Config(base_url="https://api.example.com"),
            steps=[
                Step(
                    id="step_1",
                    action="http_request",
                    params={"method": "GET", "path": "/health"},
                )
            ],
        )
        assert plan.spec_version == "0.1"
        assert plan.meta.name == "Plano de Teste"

    def test_unknown_dependency_raises_error(self) -> None:
        """Testa que dependência de step inexistente levanta erro."""
        with pytest.raises(ValidationError) as exc_info:
            Plan(
                meta=Meta(name="Plano de Teste"),
                config=Config(base_url="https://api.example.com"),
                steps=[
                    Step(
                        id="step_1",
                        action="http_request",
                        params={"method": "GET", "path": "/health"},
                        depends_on=["nonexistent_step"],
                    )
                ],
            )
        assert "desconhecido" in str(exc_info.value).lower()

    def test_circular_dependency_raises_error(self) -> None:
        """Testa que dependência circular levanta erro."""
        with pytest.raises(ValidationError) as exc_info:
            Plan(
                meta=Meta(name="Plano de Teste"),
                config=Config(base_url="https://api.example.com"),
                steps=[
                    Step(
                        id="step_a",
                        action="http_request",
                        params={"method": "GET", "path": "/a"},
                        depends_on=["step_b"],
                    ),
                    Step(
                        id="step_b",
                        action="http_request",
                        params={"method": "GET", "path": "/b"},
                        depends_on=["step_a"],
                    )
                ],
            )
        assert "circular" in str(exc_info.value).lower()

    def test_to_json_returns_valid_json(self) -> None:
        """Testa que to_json() retorna JSON válido."""
        plan = Plan(
            meta=Meta(name="Plano de Teste"),
            config=Config(base_url="https://api.example.com"),
            steps=[
                Step(
                    id="step_1",
                    action="http_request",
                    params={"method": "GET", "path": "/health"},
                )
            ],
        )
        json_str = plan.to_json()
        assert '"spec_version": "0.1"' in json_str
        assert '"name": "Plano de Teste"' in json_str
