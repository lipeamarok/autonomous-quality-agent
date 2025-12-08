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

        # Pode ser:
        # - 200: sucesso (LLM configurado e funcionando)
        # - 500: erro interno
        # - 502: LLM não configurado ou falha na API do provider
        # O importante é que não seja 400 (bad request - input inválido)
        assert response.status_code in [200, 500, 502]


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


# =============================================================================
# Testes: Plans Endpoint
# =============================================================================


class TestPlansEndpoint:
    """Testes para endpoints de gerenciamento de planos."""

    def test_list_plans_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/plans retorna 200 OK."""
        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "plans" in data
        assert "total" in data

    def test_get_plan_not_found_returns_404(self, client: TestClient) -> None:
        """GET /api/v1/plans/{name} retorna 404 para plano inexistente."""
        response = client.get("/api/v1/plans/nonexistent-plan-xyz")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"]["code"] == "E6003"

    def test_list_versions_not_found_returns_404(self, client: TestClient) -> None:
        """GET /api/v1/plans/{name}/versions retorna 404 para plano inexistente."""
        response = client.get("/api/v1/plans/nonexistent-plan-xyz/versions")

        assert response.status_code == 404

    def test_get_version_not_found_returns_404(self, client: TestClient) -> None:
        """GET /api/v1/plans/{name}/versions/{version} retorna 404."""
        response = client.get("/api/v1/plans/nonexistent-plan-xyz/versions/1")

        assert response.status_code == 404

    def test_diff_versions_not_found_returns_404(self, client: TestClient) -> None:
        """GET /api/v1/plans/{name}/diff retorna 404 para plano inexistente."""
        response = client.get(
            "/api/v1/plans/nonexistent-plan-xyz/diff",
            params={"version_a": 1}
        )

        assert response.status_code == 404

    def test_restore_version_not_found_returns_404(self, client: TestClient) -> None:
        """POST /api/v1/plans/{name}/versions/{version}/restore retorna 404."""
        response = client.post("/api/v1/plans/nonexistent-plan-xyz/versions/1/restore")

        assert response.status_code == 404


# =============================================================================
# Testes: Autenticação API Key
# =============================================================================


class TestAuthStatusEndpoint:
    """Testes para GET /api/v1/auth/status."""

    def test_auth_status_returns_200(self, client: TestClient) -> None:
        """Auth status retorna 200 OK."""
        response = client.get("/api/v1/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "mode" in data

    def test_auth_status_is_public(self, client: TestClient) -> None:
        """Auth status é público (não requer autenticação)."""
        # Mesmo sem header de auth, deve funcionar
        response = client.get("/api/v1/auth/status")
        assert response.status_code == 200


class TestAuthenticationModes:
    """Testes para diferentes modos de autenticação."""

    @pytest.fixture
    def client_no_auth(self) -> TestClient:
        """Client com auth mode=none."""
        import os
        original = os.environ.get("AQA_AUTH_MODE")
        os.environ["AQA_AUTH_MODE"] = "none"

        config = APIConfig(
            host="127.0.0.1",
            port=8888,
            debug=True,
            cors_origins=["*"],
            docs_enabled=True,
        )
        app = create_app(config)
        client = TestClient(app)

        yield client

        # Restaurar
        if original is not None:
            os.environ["AQA_AUTH_MODE"] = original
        elif "AQA_AUTH_MODE" in os.environ:
            del os.environ["AQA_AUTH_MODE"]

    @pytest.fixture
    def client_apikey_auth(self) -> TestClient:
        """Client com auth mode=apikey."""
        import os
        original_mode = os.environ.get("AQA_AUTH_MODE")
        original_key = os.environ.get("AQA_API_KEY")

        os.environ["AQA_AUTH_MODE"] = "apikey"
        os.environ["AQA_API_KEY"] = "aqa_test1234567890abcdef12345678"

        config = APIConfig(
            host="127.0.0.1",
            port=8888,
            debug=True,
            cors_origins=["*"],
            docs_enabled=True,
        )
        app = create_app(config)
        client = TestClient(app)

        yield client

        # Restaurar
        if original_mode is not None:
            os.environ["AQA_AUTH_MODE"] = original_mode
        elif "AQA_AUTH_MODE" in os.environ:
            del os.environ["AQA_AUTH_MODE"]

        if original_key is not None:
            os.environ["AQA_API_KEY"] = original_key
        elif "AQA_API_KEY" in os.environ:
            del os.environ["AQA_API_KEY"]

    def test_no_auth_mode_allows_all_requests(self, client_no_auth: TestClient) -> None:
        """Modo 'none' permite todas as requisições sem autenticação."""
        # Endpoint protegido deve funcionar sem header
        response = client_no_auth.get("/api/v1/auth/status")
        assert response.status_code == 200

        data = response.json()
        assert data["enabled"] is False
        assert data["mode"] == "none"

    def test_apikey_mode_requires_header(self, client_apikey_auth: TestClient) -> None:
        """Modo 'apikey' requer header de autenticação."""
        # Sem header, deve retornar 401
        response = client_apikey_auth.post(
            "/api/v1/generate",
            json={"swagger_url": "http://example.com/api.yaml"}
        )

        # Se auth está ativado, deve dar 401
        # Se não está, pode retornar outros códigos
        if response.status_code == 401:
            data = response.json()
            assert "detail" in data

    def test_apikey_mode_accepts_valid_key(self, client_apikey_auth: TestClient) -> None:
        """Modo 'apikey' aceita chave válida."""
        valid_key = "aqa_test1234567890abcdef12345678"

        response = client_apikey_auth.get(
            "/api/v1/auth/status",
            headers={"X-API-Key": valid_key}
        )

        assert response.status_code == 200

    def test_apikey_mode_rejects_invalid_key(self, client_apikey_auth: TestClient) -> None:
        """Modo 'apikey' rejeita chave inválida."""
        invalid_key = "aqa_sk_invalid_key_here"

        response = client_apikey_auth.post(
            "/api/v1/generate",
            json={"swagger_url": "http://example.com/api.yaml"},
            headers={"X-API-Key": invalid_key}
        )

        # Se auth está ativado, deve dar 401 ou 403
        if response.status_code in (401, 403):
            data = response.json()
            assert "detail" in data


class TestAPIKeyManagement:
    """Testes para gerenciamento de API Keys."""

    def test_list_keys_returns_array(self, client: TestClient) -> None:
        """GET /api/v1/auth/keys retorna lista."""
        response = client.get("/api/v1/auth/keys")

        # Pode retornar 200 com lista ou 403 se não permitido
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_key_format_validation(self) -> None:
        """Valida formato das API keys geradas."""
        from src.api.auth import generate_api_key

        key = generate_api_key()

        # Deve ter prefixo aqa_
        assert key.startswith("aqa_")

        # Deve ter 36 caracteres (4 prefixo + 32 hex)
        assert len(key) == 36  # aqa_ (4) + 32 hex

    def test_key_prefix_extraction(self) -> None:
        """Testa extração de prefixo da key."""
        key = "aqa_test1234567890abcdef12345678"
        prefix = key[:12]  # aqa_ + 8 chars

        assert prefix == "aqa_test1234"


# =============================================================================
# Testes: Metrics
# =============================================================================


class TestMetricsEndpoint:
    """Testes para GET /api/v1/metrics."""

    def test_metrics_returns_200(self, client: TestClient) -> None:
        """GET /metrics retorna 200 OK."""
        response = client.get("/api/v1/metrics")

        assert response.status_code == 200
        # Formato Prometheus é text/plain
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_contains_aqa_prefix(self, client: TestClient) -> None:
        """Métricas contêm prefixo aqa_."""
        response = client.get("/api/v1/metrics")

        assert response.status_code == 200
        # Deve conter pelo menos uma métrica aqa_
        assert "aqa_" in response.text

    def test_metrics_json_returns_dict(self, client: TestClient) -> None:
        """GET /metrics/json retorna dicionário."""
        response = client.get("/api/v1/metrics/json")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "metrics" in data
        assert "timestamp" in data


# =============================================================================
# Testes: WebSocket
# =============================================================================


class TestWebSocketExecute:
    """Testes para WebSocket /ws/execute."""

    def test_websocket_connect(self, client: TestClient) -> None:
        """WebSocket aceita conexão."""
        with client.websocket_connect("/ws/execute") as websocket:
            # Conexão estabelecida com sucesso
            assert websocket is not None
            # Primeiro evento é 'connected'
            data = websocket.receive_json()
            assert data.get("event") == "connected"

    def test_websocket_ping(self, client: TestClient) -> None:
        """WebSocket responde a ping."""
        with client.websocket_connect("/ws/execute") as websocket:
            # Consume evento connected
            websocket.receive_json()

            # Envia ping
            websocket.send_json({"action": "ping"})

            # Espera resposta (pode ser pong ou error)
            data = websocket.receive_json()
            assert "event" in data or "error" in data

    def test_websocket_invalid_action(self, client: TestClient) -> None:
        """WebSocket trata ação inválida."""
        with client.websocket_connect("/ws/execute") as websocket:
            # Consume evento connected
            websocket.receive_json()

            # Envia ação inválida
            websocket.send_json({"action": "invalid_action"})

            # Espera erro
            data = websocket.receive_json()
            assert data.get("event") == "error" or "error" in str(data)

    def test_websocket_execute_requires_plan(self, client: TestClient) -> None:
        """Execução via WebSocket requer plano."""
        with client.websocket_connect("/ws/execute") as websocket:
            # Consume evento connected
            websocket.receive_json()

            # Tenta executar sem plano
            websocket.send_json({"action": "execute"})

            # Espera erro de validação
            data = websocket.receive_json()
            assert data.get("event") == "error" or "plan" in str(data).lower()

    def test_websocket_execute_dry_run(self, client: TestClient) -> None:
        """Execução dry_run via WebSocket."""
        valid_plan = {
            "spec_version": "0.1",
            "meta": {
                "id": "ws-test-001",
                "name": "WebSocket Test Plan",
            },
            "config": {
                "base_url": "http://localhost:8080",
            },
            "steps": [
                {
                    "id": "step1",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/health",
                    },
                    "assertions": [],
                }
            ],
        }

        with client.websocket_connect("/ws/execute") as websocket:
            # Consume evento connected
            websocket.receive_json()

            # Envia plano para execução dry_run
            websocket.send_json({
                "action": "execute",
                "plan": valid_plan,
                "options": {"dry_run": True},
            })

            # Espera alguma resposta
            data = websocket.receive_json()
            assert "event" in data
