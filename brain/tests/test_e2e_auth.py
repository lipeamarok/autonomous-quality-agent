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

## Serviços de teste (com fallback):

1. httpbingo.org - Clone open-source do httpbin (primário)
2. postman-echo.com - Serviço da Postman (fallback 1)  
3. httpbin.org - Original, frequentemente instável (fallback 2)

## Como rodar:

```bash
pytest tests/test_e2e_auth.py -v
pytest tests/test_e2e_auth.py -v -k "basic_auth"
```

## Requisitos:

- Rust toolchain instalado (cargo)
- Conexão com internet (para serviço HTTP de teste)
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
# CONFIGURAÇÃO DE SERVIÇO HTTP DE TESTE COM FALLBACK
# =============================================================================

# Type alias para configuração de serviço HTTP de auth
HttpAuthServiceConfig = dict[str, str | bool]

# Lista de serviços HTTP de teste em ordem de preferência
# Cada entrada contém URLs e paths específicos para testes de auth
#
# ## Serviços HTTP de teste (com fallback):
#
# 1. postman-echo.com - Serviço da Postman (primário, mais estável com runner)
#    NOTA: Headers são retornados em lowercase (x-api-key em vez de X-Api-Key)
#    NOTA: Não suporta endpoints /basic-auth/{user}/{pass} e /bearer
# 2. httpbin.org - Original (fallback quando disponível)
# 3. httpbingo.org - Clone open-source do httpbin (fallback 2)
#
# IMPORTANTE:
# - postman-echo.com é o primário porque funciona corretamente com o runner Rust
# - httpbingo.org retorna 402 Payment Required para o runner Rust/reqwest,
#   embora responda 200 para Python/urllib (problema de User-Agent ou rate limit)
# - httpbin.org é frequentemente instável (timeouts)
# - Testes de Basic Auth e Bearer são skipped quando o serviço não suporta
HTTP_AUTH_SERVICES: list[HttpAuthServiceConfig] = [
    {
        "name": "postman-echo.com",
        "base_url": "https://postman-echo.com",
        "health_path": "/get",
        "basic_auth_path": "/basic-auth",  # Postman usa path diferente
        "bearer_path": "/get",  # Postman não tem /bearer específico
        "headers_path": "/headers",
        "get_path": "/get",
        "post_path": "/post",
        "hidden_basic_auth_path": "/basic-auth",
        "supports_basic_auth": False,  # Postman não tem Basic Auth como httpbin
        "supports_bearer": False,  # Não valida bearer especificamente
        "supports_hidden_basic_auth": False,
        "headers_as_arrays": False,
        "headers_lowercase": True,  # postman-echo retorna headers em lowercase
    },
    {
        "name": "httpbin.org",
        "base_url": "https://httpbin.org",
        "health_path": "/get",
        "basic_auth_path": "/basic-auth/{user}/{passwd}",
        "bearer_path": "/bearer",
        "headers_path": "/headers",
        "get_path": "/get",
        "post_path": "/post",
        "hidden_basic_auth_path": "/hidden-basic-auth/{user}/{passwd}",
        "supports_basic_auth": True,
        "supports_bearer": True,
        "supports_hidden_basic_auth": True,
        "headers_as_arrays": False,  # httpbin retorna headers como strings
    },
    {
        "name": "httpbingo.org",
        "base_url": "https://httpbingo.org",
        "health_path": "/get",
        "basic_auth_path": "/basic-auth/{user}/{passwd}",
        "bearer_path": "/bearer",
        "headers_path": "/headers",
        "get_path": "/get",
        "post_path": "/post",
        "hidden_basic_auth_path": "/hidden-basic-auth/{user}/{passwd}",
        "supports_basic_auth": True,
        "supports_bearer": True,
        "supports_hidden_basic_auth": True,
        "headers_as_arrays": True,  # httpbingo retorna headers como arrays
    },
]


def _check_service_available(base_url: str, health_path: str, timeout: float = 5.0) -> bool:
    """
    Verifica se um serviço HTTP está disponível.
    
    Args:
        base_url: URL base do serviço
        health_path: Path para verificar disponibilidade
        timeout: Timeout em segundos
        
    Returns:
        True se o serviço responde com 200, False caso contrário
    """
    try:
        url = f"{base_url}{health_path}"
        request = urllib.request.Request(url, method="GET")
        request.add_header("User-Agent", "AQA-Test/1.0")
        
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def get_available_auth_service() -> HttpAuthServiceConfig:
    """
    Retorna o primeiro serviço HTTP de teste de auth disponível.
    
    Testa cada serviço em ordem de preferência e retorna
    o primeiro que responder.
    
    Returns:
        Dicionário com configuração do serviço disponível
        
    Raises:
        pytest.skip: Se nenhum serviço estiver disponível
    """
    for service in HTTP_AUTH_SERVICES:
        base_url = str(service["base_url"])
        health_path = str(service["health_path"])
        if _check_service_available(base_url, health_path):
            return service
    
    # Nenhum serviço disponível
    pytest.skip(
        "Nenhum serviço HTTP de teste disponível. "
        f"Tentados: {', '.join(str(s['name']) for s in HTTP_AUTH_SERVICES)}"
    )


# Cache do serviço disponível para evitar múltiplas verificações
_cached_auth_service: HttpAuthServiceConfig | None = None


def get_auth_service() -> HttpAuthServiceConfig:
    """
    Retorna o serviço HTTP de teste de auth (com cache).
    
    Verifica disponibilidade apenas na primeira chamada.
    """
    global _cached_auth_service
    if _cached_auth_service is None:
        _cached_auth_service = get_available_auth_service()
        print(f"\n[INFO] Usando serviço HTTP de teste para auth: {_cached_auth_service['name']}")
    return _cached_auth_service


def make_header_assertion(
    service: HttpAuthServiceConfig,
    header_name: str,
    expected_value: str,
    operator: str = "eq",
) -> dict[str, Any]:
    """
    Cria uma assertion de header compatível com o formato do serviço.
    
    Diferenças entre serviços:
    - httpbingo.org: retorna headers como arrays {"Header": ["value"]}
    - httpbin.org: retorna headers preservando case {"Header": "value"}
    - postman-echo.com: retorna headers em lowercase {"header": "value"}
    
    NOTA: O runner não suporta bracket notation para propriedades (["prop"]),
    apenas para índices de array ([0]). Usamos dot notation.
    
    Args:
        service: Configuração do serviço HTTP
        header_name: Nome do header (ex: "X-Api-Key", "Authorization")
        expected_value: Valor esperado do header
        operator: Operador de comparação (default: "eq")
        
    Returns:
        Dict com a assertion configurada corretamente para o serviço
    """
    # Ajusta o nome do header baseado no serviço
    if service.get("headers_lowercase", False):
        # postman-echo.com retorna todos os headers em lowercase
        adjusted_header = header_name.lower()
    else:
        adjusted_header = header_name
    
    if service.get("headers_as_arrays", False):
        # Para serviços que retornam headers como arrays, usamos [0] para pegar o primeiro valor
        # Usamos dot notation para o nome do header + [0] para o índice do array
        return {
            "type": "json_body",
            "path": f"$.headers.{adjusted_header}[0]",
            "operator": operator,
            "value": expected_value,
        }
    else:
        # Usamos dot notation simples
        return {
            "type": "json_body",
            "path": f"$.headers.{adjusted_header}",
            "operator": operator,
            "value": expected_value,
        }


@pytest.fixture(scope="module")
def http_auth_service() -> HttpAuthServiceConfig:
    """
    Fixture que fornece o serviço HTTP de teste de auth disponível.
    
    Scope é 'module' para verificar disponibilidade apenas uma vez
    por módulo de teste.
    """
    return get_auth_service()


# Mantido para compatibilidade com testes existentes
@pytest.fixture(scope="module")
def httpbin_available(http_auth_service: HttpAuthServiceConfig) -> bool:
    """
    Fixture que verifica se um serviço HTTP de teste está disponível.

    Agora usa o sistema de fallback - sempre retorna True se algum serviço estiver up.
    """
    return True  # Se chegou aqui, http_auth_service já garantiu que há serviço


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

    # Verifica se cargo está disponível
    try:
        cargo_check = subprocess.run(
            ["cargo", "--version"],
            capture_output=True,
            text=True,
        )
        if cargo_check.returncode != 0:
            pytest.skip("Cargo não está disponível")
    except FileNotFoundError:
        pytest.skip("Cargo não está instalado")

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

    Usa serviço HTTP de teste com fallback automático.
    O endpoint /basic-auth/{user}/{passwd} retorna 200
    se as credenciais estiverem corretas, 401 caso contrário.
    """

    def test_basic_auth_with_correct_credentials(
        self,
        compiled_runner: Path,
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa Basic Auth com credenciais corretas.

        O endpoint /basic-auth/testuser/testpass aceita:
        - Authorization: Basic dGVzdHVzZXI6dGVzdHBhc3M=
        """
        if not http_auth_service.get("supports_basic_auth"):
            pytest.skip(f"{http_auth_service['name']} não suporta Basic Auth")

        # Credenciais de teste
        username = "testuser"
        password = "testpass"
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        
        # Monta o path de basic auth (alguns serviços usam path diferente)
        basic_auth_path = http_auth_service["basic_auth_path"].format(
            user=username, passwd=password
        )

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-basic-auth",
                "name": f"Test Basic Auth Flow ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "basic-auth-request",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": basic_auth_path,
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
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa Basic Auth com credenciais incorretas.

        Deve retornar 401 Unauthorized.
        """
        if not http_auth_service.get("supports_basic_auth"):
            pytest.skip(f"{http_auth_service['name']} não suporta Basic Auth")
            
        username = "testuser"
        password = "wrongpass"
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        
        # O path espera as credenciais corretas, mas enviamos as erradas
        basic_auth_path = http_auth_service["basic_auth_path"].format(
            user="testuser", passwd="testpass"
        )

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-basic-auth-fail",
                "name": f"Test Basic Auth Failure ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "basic-auth-wrong",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": basic_auth_path,
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

    Usa serviço HTTP de teste com endpoint /bearer que valida
    o header Authorization: Bearer <token>
    """

    def test_bearer_token_accepted(
        self,
        compiled_runner: Path,
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa Bearer token sendo aceito.

        O endpoint /bearer retorna 200 se houver um token Bearer válido.
        """
        if not http_auth_service.get("supports_bearer"):
            pytest.skip(f"{http_auth_service['name']} não suporta Bearer Auth")
            
        token = "my-test-token-12345"

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-bearer-auth",
                "name": f"Test Bearer Auth Flow ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
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
                        "path": http_auth_service["bearer_path"],
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
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa requisição sem Bearer token.

        O endpoint /bearer retorna 401 se não houver token.
        """
        if not http_auth_service.get("supports_bearer"):
            pytest.skip(f"{http_auth_service['name']} não suporta Bearer Auth")
            
        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-bearer-missing",
                "name": f"Test Bearer Missing Token ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "bearer-no-token",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": http_auth_service["bearer_path"],
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
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa extração de token de uma resposta e uso em request subsequente.

        Fluxo:
        1. Faz POST para /post simulando login
        2. Extrai "token" do response body
        3. Usa o token extraído em request para /bearer
        """
        if not http_auth_service.get("supports_bearer"):
            pytest.skip(f"{http_auth_service['name']} não suporta Bearer Auth")
            
        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-token-propagation",
                "name": f"Test Token Extraction and Propagation ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
                "timeout_ms": 30000,
            },
            "steps": [
                {
                    "id": "simulate-login",
                    "action": "http_request",
                    "params": {
                        "method": "POST",
                        "path": http_auth_service["post_path"],
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
                        "path": http_auth_service["bearer_path"],
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

    Usa endpoint /headers do serviço HTTP de teste que ecoa todos os headers recebidos.
    """

    def test_api_key_in_header(
        self,
        compiled_runner: Path,
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa API Key sendo enviada no header.

        Verifica que o header X-API-Key é propagado corretamente.
        """
        api_key = "my-secret-api-key-12345"

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-api-key-header",
                "name": f"Test API Key in Header ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
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
                        "path": http_auth_service["headers_path"],
                        "headers": {
                            "X-Api-Key": "${api_key}",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "assertions": [
                        make_header_assertion(http_auth_service, "X-Api-Key", api_key),
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
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa múltiplos headers de autenticação simultaneamente.

        Verifica que X-API-Key e Authorization podem coexistir.
        """
        api_key = "api-key-123"
        bearer_token = "bearer-token-456"

        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test-multiple-auth",
                "name": f"Test Multiple Auth Headers ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
                "timeout_ms": 30000,
                "variables": {},
            },
            "steps": [
                {
                    "id": "multi-auth-request",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "path": http_auth_service["headers_path"],
                        "headers": {
                            "X-Api-Key": api_key,
                            "Authorization": f"Bearer {bearer_token}",
                        },
                    },
                    "expect": {
                        "status": 200,
                    },
                    "assertions": [
                        make_header_assertion(http_auth_service, "X-Api-Key", api_key),
                        make_header_assertion(
                            http_auth_service, "Authorization", f"Bearer {bearer_token}"
                        ),
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
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa que steps gerados para Bearer Auth funcionam no Runner.

        Fluxo:
        1. Detecta segurança em spec OpenAPI
        2. Gera steps de autenticação
        3. Injeta headers nos steps base
        4. Executa e valida
        """
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
                    "path": http_auth_service["headers_path"],
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
                "name": f"Test Generated Auth Flow ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
                "timeout_ms": 30000,
                "variables": {},
            },
            "steps": injected_steps,
        }

        # Adiciona assertion para verificar header
        plan["steps"][0]["assertions"] = [
            make_header_assertion(
                http_auth_service, "Authorization", f"Bearer {test_token}"
            ),
        ]

        report = run_plan_with_runner(compiled_runner, plan)

        assert report.get("summary", {}).get("passed", 0) >= 1
        assert report.get("summary", {}).get("failed", 0) == 0

    def test_api_key_detection_and_injection(
        self,
        compiled_runner: Path,
        http_auth_service: dict[str, Any],
    ) -> None:
        """
        Testa detecção de API Key e injeção em steps.
        """
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
                    "path": http_auth_service["headers_path"],
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
                "name": f"Test API Key Injection ({http_auth_service['name']})",
                "created_at": "2024-12-05T00:00:00Z",
            },
            "config": {
                "base_url": http_auth_service["base_url"],
                "timeout_ms": 30000,
                "variables": {},
            },
            "steps": injected_steps,
        }

        plan["steps"][0]["assertions"] = [
            make_header_assertion(http_auth_service, "X-Api-Key", api_key_value),
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
