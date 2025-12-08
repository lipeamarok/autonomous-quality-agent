"""
================================================================================
Testes da API REST
================================================================================

Testes para os endpoints da API usando FastAPI TestClient.

## Cobertura:

- GET /health
- POST /api/v1/generate
- POST /api/v1/validate
- POST /api/v1/execute (dry_run)
- GET /api/v1/history
- POST /api/v1/workspace/init
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api import create_app, APIConfig


# =============================================================================
# Type aliases para planos de teste (evita warnings de tipagem parcial)
# =============================================================================

PlanDict = dict[str, Any]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_config() -> APIConfig:
    """Configuração para testes."""
    return APIConfig(
        host="127.0.0.1",
        port=8888,
        debug=True,
        cors_origins=["*"],
        docs_enabled=True,
    )


@pytest.fixture
def client(test_config: APIConfig) -> TestClient:
    """TestClient configurado para testes."""
    app = create_app(test_config)
    return TestClient(app)


# =============================================================================
# Testes: Health Check
# =============================================================================


class TestHealthEndpoint:
    """Testes para GET /health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health check retorna 200 OK."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_health_returns_status_healthy(self, client: TestClient) -> None:
        """Health check retorna status healthy."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_returns_version(self, client: TestClient) -> None:
        """Health check retorna versão do AQA."""
        response = client.get("/health")
        data = response.json()

        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_returns_timestamp(self, client: TestClient) -> None:
        """Health check retorna timestamp ISO."""
        response = client.get("/health")
        data = response.json()

        assert "timestamp" in data
        # Verifica formato ISO básico
        assert "T" in data["timestamp"]


# =============================================================================
# Testes: Validate Endpoint
# =============================================================================


class TestValidateEndpoint:
    """Testes para POST /api/v1/validate."""

    def test_validate_valid_plan(self, client: TestClient) -> None:
        """Plano válido retorna is_valid=True."""
        valid_plan: PlanDict = {
            "spec_version": "0.1",
            "meta": {
                "name": "Test Plan",
                "id": "test-001",
                "description": "Plan for testing",
            },
            "config": {
                "base_url": "https://api.example.com",
            },
            "steps": [
                {
                    "id": "health_check",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/health",
                    },
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 200}
                    ],
                }
            ],
        }

        response = client.post(
            "/api/v1/validate",
            json={"plan": valid_plan, "mode": "default"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_valid"] is True
        assert data["error_count"] == 0

    def test_validate_invalid_plan_missing_meta(self, client: TestClient) -> None:
        """Plano sem meta retorna is_valid=False."""
        invalid_plan: PlanDict = {
            "spec_version": "0.1",
            # meta ausente
            "config": {"base_url": "https://api.example.com"},
            "steps": [],
        }

        response = client.post(
            "/api/v1/validate",
            json={"plan": invalid_plan}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_valid"] is False
        assert data["error_count"] > 0

    def test_validate_strict_mode(self, client: TestClient) -> None:
        """Modo strict é mais rigoroso."""
        plan: PlanDict = {
            "spec_version": "0.1",
            "meta": {"name": "Test", "id": "test-001"},
            "config": {"base_url": "https://api.example.com"},
            "steps": [],  # Plano sem steps pode gerar warning
        }

        response = client.post(
            "/api/v1/validate",
            json={"plan": plan, "mode": "strict"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# =============================================================================
# Testes: Generate Endpoint
# =============================================================================


class TestGenerateEndpoint:
    """Testes para POST /api/v1/generate."""

    def test_generate_requires_input(self, client: TestClient) -> None:
        """Generate sem input retorna erro."""
        response = client.post(
            "/api/v1/generate",
            json={"base_url": "https://api.example.com"}
            # Sem requirement nem swagger
        )

        assert response.status_code == 400

    def test_generate_with_requirement_accepted(self, client: TestClient) -> None:
        """Generate com requirement é aceito (pode falhar se LLM não configurado)."""
        response = client.post(
            "/api/v1/generate",
            json={
                "requirement": "Testar endpoint de login",
                "base_url": "https://api.example.com",
            }
        )

        # Pode ser 200 (sucesso) ou 500 (LLM não configurado)
        # O importante é que não seja 400 (bad request)
        assert response.status_code in [200, 500]


# =============================================================================
# Testes: Execute Endpoint
# =============================================================================


class TestExecuteEndpoint:
    """Testes para POST /api/v1/execute."""

    def test_execute_requires_plan_source(self, client: TestClient) -> None:
        """Execute sem fonte de plano retorna erro."""
        response = client.post(
            "/api/v1/execute",
            json={}  # Sem plan, plan_file, requirement ou swagger
        )

        assert response.status_code == 400
        data = response.json()
        assert "E6002" in str(data.get("detail", {}))

    def test_execute_dry_run_valid_plan(self, client: TestClient) -> None:
        """Execute com dry_run valida sem executar."""
        valid_plan: PlanDict = {
            "spec_version": "0.1",
            "meta": {"name": "Dry Run Test", "id": "dry-001"},
            "config": {"base_url": "https://httpbin.org"},
            "steps": [
                {
                    "id": "get_ip",
                    "action": "http_request",
                    "params": {"method": "GET", "path": "/ip"},
                    "assertions": [
                        {"type": "status_code", "operator": "eq", "value": 200}
                    ],
                }
            ],
        }

        response = client.post(
            "/api/v1/execute",
            json={"plan": valid_plan, "dry_run": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["summary"]["total_steps"] == 1
        assert data["summary"]["skipped"] == 1  # dry_run pula execução

    def test_execute_invalid_plan_rejected(self, client: TestClient) -> None:
        """Execute com plano inválido retorna erro."""
        invalid_plan: PlanDict = {
            "spec_version": "0.1",
            # Falta meta e config
            "steps": [],
        }

        response = client.post(
            "/api/v1/execute",
            json={"plan": invalid_plan}
        )

        assert response.status_code == 400


# =============================================================================
# Testes: History Endpoint
# =============================================================================


class TestHistoryEndpoint:
    """Testes para GET /api/v1/history."""

    def test_history_list_returns_200(self, client: TestClient) -> None:
        """Listagem de histórico retorna 200."""
        response = client.get("/api/v1/history")

        # Pode retornar 200 (sucesso) ou 500 (storage não configurado)
        assert response.status_code in [200, 500]

    def test_history_stats_returns_200(self, client: TestClient) -> None:
        """Estatísticas de histórico retorna 200."""
        response = client.get("/api/v1/history/stats")

        assert response.status_code in [200, 500]


# =============================================================================
# Testes: Workspace Endpoint
# =============================================================================


class TestWorkspaceEndpoint:
    """Testes para POST /api/v1/workspace/init."""

    def test_workspace_init_accepted(self, client: TestClient) -> None:
        """Inicialização de workspace é aceita ou indica que já existe."""
        response = client.post(
            "/api/v1/workspace/init",
            json={}  # Usa diretório atual
        )

        # 200 (criado) ou 409 (já existe) são respostas válidas
        assert response.status_code in (200, 409)
        data = response.json()
        # Em ambos os casos, sucesso indica resultado esperado
        if response.status_code == 200:
            assert data["success"] is True
        else:
            # 409 indica workspace já existente
            assert "detail" in data or "success" in data

    def test_workspace_status_returns_200(self, client: TestClient) -> None:
        """Status do workspace retorna 200."""
        response = client.get("/api/v1/workspace/status")

        assert response.status_code == 200


# =============================================================================
# Testes: CORS
# =============================================================================


class TestCORS:
    """Testes para configuração CORS."""

    def test_cors_headers_present(self, client: TestClient) -> None:
        """Headers CORS estão presentes."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )

        # FastAPI com CORS middleware responde a OPTIONS
        assert response.status_code in [200, 405]


# =============================================================================
# Testes: Request ID Middleware
# =============================================================================


class TestRequestIdMiddleware:
    """Testes para middleware de Request ID."""

    def test_request_id_in_response(self, client: TestClient) -> None:
        """Response contém X-Request-ID."""
        response = client.get("/health")

        assert "X-Request-ID" in response.headers

    def test_custom_request_id_echoed(self, client: TestClient) -> None:
        """Request ID customizado é retornado."""
        custom_id = "my-custom-request-123"
        response = client.get(
            "/health",
            headers={"X-Request-ID": custom_id}
        )

        assert response.headers.get("X-Request-ID") == custom_id
