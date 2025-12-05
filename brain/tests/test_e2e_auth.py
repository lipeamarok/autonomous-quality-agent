"""
================================================================================
Testes End-to-End: Fluxos de Autenticação
================================================================================

## Para todos entenderem:

Estes testes validam fluxos completos de autenticação:
1. Detecta security schemes em OpenAPI specs
2. Gera steps de autenticação automaticamente
3. Executa o Runner com planos autenticados
4. Verifica que tokens são extraídos e propagados corretamente

## Serviços de teste:

- httpbin.org: Suporta Basic Auth, Bearer e headers customizados
- Mocks locais para OAuth2 (quando httpbin não suporta)

## Como rodar:

```bash
pytest tests/test_e2e_auth.py -v
pytest tests/test_e2e_auth.py -v -k "basic_auth"
```

## Requisitos:

- Rust toolchain instalado (cargo)
- Conexão com internet (para httpbin.org)
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

import pytest

# Adiciona o diretório brain ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.security import (                   #type: ignore
    SecurityType,
    detect_security,
    get_auth_header_for_scheme,
    inject_auth_into_steps,
    sanitize_for_logging,
    REDACTED_VALUE,
)


# =============================================================================
# CONSTANTES
# =============================================================================

HTTPBIN_BASE_URL = "https://httpbin.org"
HTTPBIN_TIMEOUT_SECONDS = 5


def check_httpbin_available() -> bool:
    """
    Verifica se httpbin.org está disponível.

    ## Retorna:
        True se o serviço está acessível, False caso contrário.
    """
    try:
        req = urllib.request.Request(
            f"{HTTPBIN_BASE_URL}/get",
            headers={"User-Agent": "AQA-Test/1.0"},
        )
        with urllib.request.urlopen(req, timeout=HTTPBIN_TIMEOUT_SECONDS) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@pytest.fixture(scope="module")
def httpbin_available() -> bool:
    """
    Fixture que verifica se httpbin.org está disponível.

    Usada para pular testes E2E quando o serviço está fora do ar.
    """
    return check_httpbin_available()


# =============================================================================
# FIXTURES
# =============================================================================


def get_runner_binary_path() -> Path:
    """Retorna o caminho para o binário do Runner."""
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


def run_plan_with_runner(binary_path: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """
    Executa um plano UTDL usando o Runner e retorna o ExecutionReport.

    ## Parâmetros:
        binary_path: Caminho para o binário do Runner
        plan: Plano UTDL a executar

    ## Retorna:
        ExecutionReport como dict

    ## Raises:
        pytest.fail: Se a execução falhar (erro do Runner, não assertion)
    """
    # Cria arquivo temporário para o plano
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".utdl.json",
        delete=False,
    ) as plan_file:
        json.dump(plan, plan_file, indent=2)
        plan_path = Path(plan_file.name)

    # Cria arquivo temporário para o output
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".report.json",
        delete=False,
    ) as output_file:
        output_path = Path(output_file.name)

    try:
        # Usa o formato correto do Runner: execute --file <plan> --output <output>
        result = subprocess.run(
            [
                str(binary_path),
                "execute",
                "--file",
                str(plan_path),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # O Runner retorna 0 mesmo quando steps falham.
        # Código != 0 significa erro do Runner (parse, load, etc)
        if result.returncode != 0:
            # Verifica se o report existe (o Runner pode ter falhado depois de gerar)
            if not output_path.exists():
                pytest.fail(f"Runner falhou: {result.stderr}\nStdout: {result.stdout}")

        # Lê o ExecutionReport do arquivo de output
        if not output_path.exists():
            pytest.fail(f"Report não foi gerado em {output_path}")

        report = json.loads(output_path.read_text())
        return report

    finally:
        plan_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


# =============================================================================
# TESTES E2E: BASIC AUTH
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestE2EBasicAuth:
    """
    Testes E2E para HTTP Basic Authentication.

    Usa httpbin.org/basic-auth/{user}/{passwd} que retorna 200
    se as credenciais estiverem corretas, 401 caso contrário.
    """

    def test_basic_auth_with_correct_credentials(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa Basic Auth com credenciais corretas.

        httpbin.org/basic-auth/testuser/testpass aceita:
        - Authorization: Basic dGVzdHVzZXI6dGVzdHBhc3M=
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")

        # Credenciais de teste
        username = "testuser"
        password = "testpass"
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-basic-auth",
                "name": "Test Basic Auth Flow",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "basic-auth-request",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": f"/basic-auth/{username}/{password}",
                        "headers": {
                            "Authorization": f"Basic {encoded}",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "assertions": [
                        {
                            "type": "json_body",
                            "path": "$.authenticated",
                            "operator": "eq",
                            "value": True,
                        },
                        {
                            "type": "json_body",
                            "path": "$.user",
                            "operator": "eq",
                            "value": username,
                        },
                    ],
                },
            ],
        }

        report = run_plan_with_runner(compiled_runner, plan)

        # Verifica resultado
        assert report.get("summary", {}).get("passed", 0) >= 1
        assert report.get("summary", {}).get("failed", 0) == 0

    def test_basic_auth_with_wrong_credentials(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa Basic Auth com credenciais incorretas.

        Deve retornar 401 Unauthorized.
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        username = "testuser"
        password = "wrongpass"
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-basic-auth-fail",
                "name": "Test Basic Auth Failure",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "basic-auth-wrong",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/basic-auth/testuser/testpass",
                        "headers": {
                            "Authorization": f"Basic {encoded}",
                        },
                    },
                    "expect": {
                        "status": 401,  # Esperamos falha de auth
                    },
                },
            ],
        }

        report = run_plan_with_runner(compiled_runner, plan)

        # O step deve passar porque esperamos 401
        assert report.get("summary", {}).get("passed", 0) >= 1


@pytest.mark.e2e
@pytest.mark.slow
class TestE2EBearerAuth:
    """
    Testes E2E para Bearer Token Authentication.

    Usa httpbin.org/bearer que valida o header Authorization: Bearer <token>
    """

    def test_bearer_token_accepted(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa Bearer token sendo aceito.

        httpbin.org/bearer retorna 200 se houver um token Bearer válido.
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        token = "my-test-token-12345"

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-bearer-auth",
                "name": "Test Bearer Auth Flow",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
                "variables": {
                    "access_token": token,
                },
            },
            "steps": [
                {
                    "id": "bearer-auth-request",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/bearer",
                        "headers": {
                            "Authorization": "Bearer ${access_token}",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "assertions": [
                        {
                            "type": "json_body",
                            "path": "$.authenticated",
                            "operator": "eq",
                            "value": True,
                        },
                        {
                            "type": "json_body",
                            "path": "$.token",
                            "operator": "eq",
                            "value": token,
                        },
                    ],
                },
            ],
        }

        report = run_plan_with_runner(compiled_runner, plan)

        assert report.get("summary", {}).get("passed", 0) >= 1
        assert report.get("summary", {}).get("failed", 0) == 0

    def test_bearer_token_missing(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa requisição sem Bearer token.

        httpbin.org/bearer retorna 401 se não houver token.
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-bearer-missing",
                "name": "Test Bearer Missing Token",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "bearer-no-token",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/bearer",
                    },
                    "expect": {
                        "status": 401,
                    },
                },
            ],
        }

        report = run_plan_with_runner(compiled_runner, plan)

        # Esperamos 401, então o step deve passar
        assert report.get("summary", {}).get("passed", 0) >= 1

    def test_token_extraction_and_propagation(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa extração de token de uma resposta e uso em request subsequente.

        Fluxo:
        1. Faz POST para httpbin.org/post simulando login
        2. Extrai "token" do response body
        3. Usa o token extraído em request para /bearer
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-token-propagation",
                "name": "Test Token Extraction and Propagation",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "simulate-login",
                    "action": "http_request",
                    "params": {
                        "method": "POST",
                        "path": "/post",
                        "headers": {
                            "Content-Type": "application/json",
                        },
                        "body": {
                            "username": "testuser",
                            "password": "testpass",
                            "token": "extracted-token-xyz",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "extract": [
                        {
                            "source": "body",
                            "path": "$.json.token",
                            "target": "access_token",
                        },
                    ],
                },
                {
                    "id": "use-extracted-token",
                    "depends_on": ["simulate-login"],
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/bearer",
                        "headers": {
                            "Authorization": "Bearer ${access_token}",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "assertions": [
                        {
                            "type": "json_body",
                            "path": "$.authenticated",
                            "operator": "eq",
                            "value": True,
                        },
                        {
                            "type": "json_body",
                            "path": "$.token",
                            "operator": "eq",
                            "value": "extracted-token-xyz",
                        },
                    ],
                },
            ],
        }

        report = run_plan_with_runner(compiled_runner, plan)

        # Ambos os steps devem passar
        assert report.get("summary", {}).get("passed", 0) >= 2
        assert report.get("summary", {}).get("failed", 0) == 0


@pytest.mark.e2e
@pytest.mark.slow
class TestE2EApiKeyAuth:
    """
    Testes E2E para API Key Authentication.

    Usa httpbin.org/headers que ecoa todos os headers recebidos.
    """

    def test_api_key_in_header(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa API Key sendo enviada no header.

        Verifica que o header X-API-Key é propagado corretamente.
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        api_key = "my-secret-api-key-12345"

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-api-key-header",
                "name": "Test API Key in Header",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
                "variables": {
                    "api_key": api_key,
                },
            },
            "steps": [
                {
                    "id": "api-key-request",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/headers",
                        "headers": {
                            "X-Api-Key": "${api_key}",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "assertions": [
                        {
                            "type": "json_body",
                            "path": "$.headers.X-Api-Key",
                            "operator": "eq",
                            "value": api_key,
                        },
                    ],
                },
            ],
        }

        report = run_plan_with_runner(compiled_runner, plan)

        assert report.get("summary", {}).get("passed", 0) >= 1
        assert report.get("summary", {}).get("failed", 0) == 0

    def test_multiple_auth_headers(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa múltiplos headers de autenticação simultaneamente.

        Verifica que X-API-Key e Authorization podem coexistir.
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        api_key = "api-key-123"
        bearer_token = "bearer-token-456"

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-multiple-auth",
                "name": "Test Multiple Auth Headers",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
                "variables": {},
            },
            "steps": [
                {
                    "id": "multi-auth-request",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": "/headers",
                        "headers": {
                            "X-Api-Key": api_key,
                            "Authorization": f"Bearer {bearer_token}",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "assertions": [
                        {
                            "type": "json_body",
                            "path": "$.headers.X-Api-Key",
                            "operator": "eq",
                            "value": api_key,
                        },
                        {
                            "type": "json_body",
                            "path": "$.headers.Authorization",
                            "operator": "eq",
                            "value": f"Bearer {bearer_token}",
                        },
                    ],
                },
            ],
        }

        report = run_plan_with_runner(compiled_runner, plan)

        assert report.get("summary", {}).get("passed", 0) >= 1
        assert report.get("summary", {}).get("failed", 0) == 0


class TestE2EAuthFlowGeneration:
    """
    Testes E2E para geração automática de fluxos de autenticação.

    Valida que o módulo security.py gera steps corretos que funcionam
    quando executados pelo Runner.
    """

    def test_generated_bearer_flow_executes(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa que steps gerados para Bearer Auth funcionam no Runner.

        Fluxo:
        1. Detecta segurança em spec OpenAPI
        2. Gera steps de autenticação
        3. Injeta headers nos steps base
        4. Executa e valida
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        # Spec OpenAPI com Bearer Auth
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    }
                }
            },
            "security": [{"bearerAuth": []}],
            "paths": {
                "/auth/login": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "properties": {
                                            "username": {"type": "string"},
                                            "password": {"type": "string"},
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "properties": {
                                                "access_token": {"type": "string"},
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    }
                },
            },
        }

        # Detecta segurança
        analysis = detect_security(spec)
        assert analysis.has_security
        assert analysis.primary_scheme is not None
        assert analysis.primary_scheme.security_type == SecurityType.HTTP_BEARER

        # Gera header de auth
        auth_header = get_auth_header_for_scheme(analysis.primary_scheme)
        assert "Authorization" in auth_header

        # Steps base (sem auth) - formato UTDL correto
        base_steps: list[dict[str, Any]] = [
            {
                "id": "get-data",
                "action": "http_request",
                "params": {
                    "method": "GET",
                    "path": "/headers",
                },
                "expect": {"status": 200},
            },
        ]

        # Simula token já obtido (para teste sem endpoint real de login)
        test_token = "test-jwt-token-for-e2e"

        # Cria plano com token pré-configurado e headers injetados
        injected_steps = inject_auth_into_steps(
            base_steps,
            {"Authorization": f"Bearer {test_token}"},
        )

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-generated-auth",
                "name": "Test Generated Auth Flow",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
                "variables": {},
            },
            "steps": injected_steps,
        }

        # Adiciona assertion para verificar header
        plan["steps"][0]["assertions"] = [
            {
                "type": "json_body",
                "path": "$.headers.Authorization",
                "operator": "eq",
                "value": f"Bearer {test_token}",
            },
        ]

        report = run_plan_with_runner(compiled_runner, plan)

        assert report.get("summary", {}).get("passed", 0) >= 1
        assert report.get("summary", {}).get("failed", 0) == 0

    def test_api_key_detection_and_injection(
        self,
        compiled_runner: Path,
        httpbin_available: bool,
    ) -> None:
        """
        Testa detecção de API Key e injeção em steps.
        """
        if not httpbin_available:
            pytest.skip("httpbin.org não está disponível")
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "components": {
                "securitySchemes": {
                    "apiKey": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-Api-Key",
                    }
                }
            },
        }

        analysis = detect_security(spec)
        assert analysis.has_security
        assert analysis.primary_scheme is not None
        assert analysis.primary_scheme.security_type == SecurityType.API_KEY

        auth_header = get_auth_header_for_scheme(analysis.primary_scheme)
        assert "X-Api-Key" in auth_header

        # Substitui variável por valor real para teste
        api_key_value = "real-api-key-for-test"

        base_steps: list[dict[str, Any]] = [
            {
                "id": "get-data",
                "action": "http_request",
                "params": {
                    "method": "GET",
                    "path": "/headers",
                },
                "expect": {"status": 200},
            },
        ]

        injected_steps = inject_auth_into_steps(
            base_steps,
            {"X-Api-Key": api_key_value},
        )

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-api-key-injection",
                "name": "Test API Key Injection",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": "https://httpbin.org",
                "timeout_ms": 30000,
                "variables": {},
            },
            "steps": injected_steps,
        }

        plan["steps"][0]["assertions"] = [
            {
                "type": "json_body",
                "path": "$.headers.X-Api-Key",
                "operator": "eq",
                "value": api_key_value,
            },
        ]

        report = run_plan_with_runner(compiled_runner, plan)

        assert report.get("summary", {}).get("passed", 0) >= 1


# =============================================================================
# TESTES DE SANITIZAÇÃO DE LOGS
# =============================================================================


class TestSanitizeForLogging:
    """
    Testes para a função de sanitização de dados sensíveis.
    """

    def test_sanitizes_password_field(self) -> None:
        """Mascara campos de senha."""
        data = {"username": "testuser", "password": "secret123"}

        result = sanitize_for_logging(data)

        assert result["username"] == "testuser"
        assert result["password"] == REDACTED_VALUE

    def test_sanitizes_token_fields(self) -> None:
        """Mascara campos de token."""
        data = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "rt_abc123",
            "user_id": "12345",
        }

        result = sanitize_for_logging(data)

        assert result["access_token"] == REDACTED_VALUE
        assert result["refresh_token"] == REDACTED_VALUE
        assert result["user_id"] == "12345"

    def test_sanitizes_api_key_fields(self) -> None:
        """Mascara campos de API Key."""
        data = {
            "api_key": "sk-1234567890",
            "apikey": "key-abcdef",
            "API_KEY": "KEY-XYZ",
            "name": "My App",
        }

        result = sanitize_for_logging(data)

        assert result["api_key"] == REDACTED_VALUE
        assert result["apikey"] == REDACTED_VALUE
        assert result["API_KEY"] == REDACTED_VALUE
        assert result["name"] == "My App"

    def test_sanitizes_authorization_header(self) -> None:
        """Mascara header Authorization."""
        data = {
            "headers": {
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIs...",
                "Content-Type": "application/json",
            }
        }

        result = sanitize_for_logging(data)

        assert result["headers"]["Authorization"] == REDACTED_VALUE
        assert result["headers"]["Content-Type"] == "application/json"

    def test_sanitizes_nested_structures(self) -> None:
        """Mascara campos sensíveis em estruturas aninhadas."""
        data: dict[str, Any] = {
            "request": {
                "body": {
                    "credentials": {
                        "username": "user",
                        "password": "pass123",
                    }
                },
                "headers": {
                    "Authorization": "Bearer token",
                },
            },
            "response": {
                "data": {
                    "access_token": "new-token",
                },
            },
        }

        result = sanitize_for_logging(data)

        assert result["request"]["body"]["credentials"]["username"] == "user"
        assert result["request"]["body"]["credentials"]["password"] == REDACTED_VALUE
        assert result["request"]["headers"]["Authorization"] == REDACTED_VALUE
        assert result["response"]["data"]["access_token"] == REDACTED_VALUE

    def test_sanitizes_list_of_dicts(self) -> None:
        """Mascara campos sensíveis em listas de dicionários."""
        data = {
            "users": [
                {"name": "User 1", "password": "pass1"},
                {"name": "User 2", "password": "pass2"},
            ]
        }

        result = sanitize_for_logging(data)

        assert result["users"][0]["name"] == "User 1"
        assert result["users"][0]["password"] == REDACTED_VALUE
        assert result["users"][1]["password"] == REDACTED_VALUE

    def test_handles_non_dict_input(self) -> None:
        """Trata inputs que não são dicionários."""
        assert sanitize_for_logging("string") == "string"
        assert sanitize_for_logging(123) == 123
        assert sanitize_for_logging(None) is None
        assert sanitize_for_logging([1, 2, 3]) == [1, 2, 3]

    def test_preserves_original_dict(self) -> None:
        """Não modifica o dicionário original."""
        original = {"password": "secret", "name": "test"}

        sanitize_for_logging(original)

        assert original["password"] == "secret"

    def test_sanitizes_secret_field(self) -> None:
        """Mascara campos que contêm 'secret'."""
        data = {
            "client_secret": "cs_12345",
            "secret_key": "sk_abcde",
            "the_secret": "shh",
            "description": "Not a secret",
        }

        result = sanitize_for_logging(data)

        assert result["client_secret"] == REDACTED_VALUE
        assert result["secret_key"] == REDACTED_VALUE
        assert result["the_secret"] == REDACTED_VALUE
        assert result["description"] == "Not a secret"

    def test_sanitizes_credential_field(self) -> None:
        """Mascara campos que contêm 'credential'."""
        data = {
            "credentials": "user:pass",
            "user_credential": "cred123",
            "public_info": "visible",
        }

        result = sanitize_for_logging(data)

        assert result["credentials"] == REDACTED_VALUE
        assert result["user_credential"] == REDACTED_VALUE
        assert result["public_info"] == "visible"
