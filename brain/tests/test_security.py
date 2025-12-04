"""
Testes para o módulo de detecção de segurança.

Testa:
- Detecção de diferentes tipos de security schemes
- Geração de steps de autenticação
- Injeção de headers em steps existentes
- Detecção automática de endpoints de login
- Geração de fluxos completos de autenticação
"""

import sys
from pathlib import Path
from typing import Any

# Adiciona o diretório brain ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.security import (
    SecurityAnalysis,
    SecurityScheme,
    SecurityType,
    create_authenticated_plan_steps,
    detect_security,
    find_login_endpoint,
    generate_auth_steps,
    generate_complete_auth_flow,
    get_auth_header_for_scheme,
    inject_auth_into_steps,
    security_to_text,
)


class TestDetectSecurity:
    """Testes para detect_security."""

    def test_no_security_schemes(self) -> None:
        """Spec sem security schemes retorna análise vazia."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }

        result = detect_security(spec)

        assert not result.has_security
        assert len(result.schemes) == 0
        assert result.primary_scheme is None

    def test_detect_api_key_header(self) -> None:
        """Detecta API Key no header."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "apiKey": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                        "description": "API Key de acesso",
                    }
                }
            },
        }

        result = detect_security(spec)

        assert result.has_security
        assert "apiKey" in result.schemes
        scheme = result.schemes["apiKey"]
        assert scheme.security_type == SecurityType.API_KEY
        assert scheme.details["location"] == "header"
        assert scheme.details["param_name"] == "X-API-Key"

    def test_detect_api_key_query(self) -> None:
        """Detecta API Key na query string."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "apiKey": {
                        "type": "apiKey",
                        "in": "query",
                        "name": "api_key",
                    }
                }
            },
        }

        result = detect_security(spec)
        scheme = result.schemes["apiKey"]

        assert scheme.details["location"] == "query"
        assert scheme.details["param_name"] == "api_key"

    def test_detect_bearer_jwt(self) -> None:
        """Detecta HTTP Bearer (JWT)."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    }
                }
            },
        }

        result = detect_security(spec)

        assert result.has_security
        scheme = result.schemes["bearerAuth"]
        assert scheme.security_type == SecurityType.HTTP_BEARER
        assert scheme.details["bearer_format"] == "JWT"

    def test_detect_basic_auth(self) -> None:
        """Detecta HTTP Basic Auth."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "basicAuth": {
                        "type": "http",
                        "scheme": "basic",
                    }
                }
            },
        }

        result = detect_security(spec)
        scheme = result.schemes["basicAuth"]

        assert scheme.security_type == SecurityType.HTTP_BASIC

    def test_detect_oauth2_password(self) -> None:
        """Detecta OAuth2 Password Grant."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "oauth2": {
                        "type": "oauth2",
                        "flows": {
                            "password": {
                                "tokenUrl": "/oauth/token",
                                "scopes": {
                                    "read": "Read access",
                                    "write": "Write access",
                                },
                            }
                        },
                    }
                }
            },
        }

        result = detect_security(spec)
        scheme = result.schemes["oauth2"]

        assert scheme.security_type == SecurityType.OAUTH2_PASSWORD
        assert scheme.details["token_url"] == "/oauth/token"
        assert "read" in scheme.details["scopes"]

    def test_detect_oauth2_client_credentials(self) -> None:
        """Detecta OAuth2 Client Credentials."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "oauth2": {
                        "type": "oauth2",
                        "flows": {
                            "clientCredentials": {
                                "tokenUrl": "/oauth/token",
                                "scopes": {},
                            }
                        },
                    }
                }
            },
        }

        result = detect_security(spec)
        scheme = result.schemes["oauth2"]

        assert scheme.security_type == SecurityType.OAUTH2_CLIENT_CREDENTIALS

    def test_detect_global_security_requirements(self) -> None:
        """Detecta requisitos de segurança globais."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"}
                }
            },
            "security": [{"bearerAuth": []}],
        }

        result = detect_security(spec)

        assert len(result.global_requirements) == 1
        assert result.global_requirements[0].scheme_name == "bearerAuth"

    def test_detect_endpoint_security_requirements(self) -> None:
        """Detecta requisitos de segurança por endpoint."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"}
                }
            },
            "paths": {
                "/admin": {
                    "get": {
                        "security": [{"bearerAuth": ["admin"]}],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        result = detect_security(spec)

        assert "GET /admin" in result.endpoint_requirements
        req = result.endpoint_requirements["GET /admin"][0]
        assert req.scheme_name == "bearerAuth"
        assert "admin" in req.scopes

    def test_primary_scheme_priority(self) -> None:
        """Bearer JWT tem prioridade sobre API Key."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                    "bearerAuth": {"type": "http", "scheme": "bearer"},
                }
            },
        }

        result = detect_security(spec)

        assert result.primary_scheme is not None
        assert result.primary_scheme.security_type == SecurityType.HTTP_BEARER

    def test_swagger_2_security_definitions(self) -> None:
        """Detecta security em Swagger 2.0 (securityDefinitions)."""
        spec: dict[str, Any] = {
            "swagger": "2.0",
            "securityDefinitions": {
                "apiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                }
            },
        }

        result = detect_security(spec)

        assert result.has_security
        assert "apiKey" in result.schemes


class TestGenerateAuthSteps:
    """Testes para generate_auth_steps."""

    def test_no_auth_when_no_security(self) -> None:
        """Não gera steps quando não há segurança."""
        analysis = SecurityAnalysis()

        steps = generate_auth_steps(analysis)

        assert len(steps) == 0

    def test_api_key_step(self) -> None:
        """Gera step de configuração para API Key."""
        scheme = SecurityScheme(
            name="apiKey",
            security_type=SecurityType.API_KEY,
            details={"location": "header", "param_name": "X-API-Key"},
        )
        analysis = SecurityAnalysis(
            schemes={"apiKey": scheme},
            has_security=True,
            primary_scheme=scheme,
        )

        steps = generate_auth_steps(analysis, credentials={"api_key": "test-key"})

        assert len(steps) == 1
        assert steps[0].step["id"] == "auth-setup"
        assert "X-API-Key" in steps[0].usage_header

    def test_bearer_login_step(self) -> None:
        """Gera step de login para Bearer JWT."""
        scheme = SecurityScheme(
            name="bearerAuth",
            security_type=SecurityType.HTTP_BEARER,
            details={"bearer_format": "JWT"},
        )
        analysis = SecurityAnalysis(
            schemes={"bearerAuth": scheme},
            has_security=True,
            primary_scheme=scheme,
        )

        steps = generate_auth_steps(
            analysis,
            login_endpoint="/api/login",
            credentials={"username": "user", "password": "pass"},
        )

        assert len(steps) == 1
        step = steps[0].step
        assert step["id"] == "auth-login"
        assert step["action"]["method"] == "POST"
        assert step["action"]["endpoint"] == "/api/login"
        assert step["action"]["body"]["username"] == "user"
        assert "access_token" in [e["name"] for e in step["extract"]]

    def test_oauth2_password_step(self) -> None:
        """Gera step para OAuth2 Password Grant."""
        scheme = SecurityScheme(
            name="oauth2",
            security_type=SecurityType.OAUTH2_PASSWORD,
            details={"token_url": "/oauth/token", "scopes": {}},
        )
        analysis = SecurityAnalysis(
            schemes={"oauth2": scheme},
            has_security=True,
            primary_scheme=scheme,
        )

        steps = generate_auth_steps(analysis)

        assert len(steps) == 1
        step = steps[0].step
        assert step["action"]["endpoint"] == "/oauth/token"
        assert step["action"]["body"]["grant_type"] == "password"

    def test_oauth2_client_credentials_step(self) -> None:
        """Gera step para OAuth2 Client Credentials."""
        scheme = SecurityScheme(
            name="oauth2",
            security_type=SecurityType.OAUTH2_CLIENT_CREDENTIALS,
            details={"token_url": "/oauth/token", "scopes": {}},
        )
        analysis = SecurityAnalysis(
            schemes={"oauth2": scheme},
            has_security=True,
            primary_scheme=scheme,
        )

        steps = generate_auth_steps(analysis)

        assert len(steps) == 1
        step = steps[0].step
        assert step["action"]["body"]["grant_type"] == "client_credentials"


class TestGetAuthHeaderForScheme:
    """Testes para get_auth_header_for_scheme."""

    def test_api_key_header(self) -> None:
        """Retorna header correto para API Key."""
        scheme = SecurityScheme(
            name="apiKey",
            security_type=SecurityType.API_KEY,
            details={"location": "header", "param_name": "X-API-Key"},
        )

        header = get_auth_header_for_scheme(scheme)

        assert "X-API-Key" in header
        assert header["X-API-Key"] == "${api_key}"

    def test_bearer_header(self) -> None:
        """Retorna header correto para Bearer."""
        scheme = SecurityScheme(
            name="bearer",
            security_type=SecurityType.HTTP_BEARER,
            details={},
        )

        header = get_auth_header_for_scheme(scheme)

        assert "Authorization" in header
        assert header["Authorization"] == "Bearer ${access_token}"


class TestInjectAuthIntoSteps:
    """Testes para inject_auth_into_steps."""

    def test_inject_header_into_http_steps(self) -> None:
        """Injeta header em steps HTTP."""
        steps: list[dict[str, Any]] = [
            {
                "id": "step-1",
                "action": {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/users",
                },
            },
            {
                "id": "step-2",
                "action": {
                    "type": "http",
                    "method": "POST",
                    "endpoint": "/users",
                    "headers": {"Content-Type": "application/json"},
                },
            },
        ]

        auth_header = {"Authorization": "Bearer token123"}
        result = inject_auth_into_steps(steps, auth_header)

        # Step 1: deve ter header adicionado
        assert result[0]["action"]["headers"]["Authorization"] == "Bearer token123"

        # Step 2: deve manter header existente e adicionar auth
        assert result[1]["action"]["headers"]["Content-Type"] == "application/json"
        assert result[1]["action"]["headers"]["Authorization"] == "Bearer token123"

    def test_does_not_modify_non_http_steps(self) -> None:
        """Não modifica steps que não são HTTP."""
        steps: list[dict[str, Any]] = [
            {
                "id": "step-1",
                "action": {
                    "type": "context",
                    "set": {"key": "value"},
                },
            },
        ]

        auth_header = {"Authorization": "Bearer token123"}
        result = inject_auth_into_steps(steps, auth_header)

        # Step não HTTP não deve ter headers
        assert "headers" not in result[0]["action"]

    def test_does_not_modify_original_steps(self) -> None:
        """Não modifica os steps originais."""
        steps: list[dict[str, Any]] = [
            {"id": "step-1", "action": {"type": "http", "endpoint": "/test"}},
        ]

        auth_header = {"Authorization": "Bearer token"}
        inject_auth_into_steps(steps, auth_header)

        # Original não deve ser modificado
        assert "headers" not in steps[0]["action"]


class TestSecurityToText:
    """Testes para security_to_text."""

    def test_no_security_text(self) -> None:
        """Gera texto para API sem segurança."""
        analysis = SecurityAnalysis()

        text = security_to_text(analysis)

        assert "não requer autenticação" in text.lower()

    def test_api_key_text(self) -> None:
        """Gera texto para API com API Key."""
        scheme = SecurityScheme(
            name="apiKey",
            security_type=SecurityType.API_KEY,
            description="Chave de API",
            details={"location": "header", "param_name": "X-API-Key"},
        )
        analysis = SecurityAnalysis(
            schemes={"apiKey": scheme},
            has_security=True,
        )

        text = security_to_text(analysis)

        assert "apiKey" in text
        assert "header" in text.lower()
        assert "X-API-Key" in text

    def test_oauth2_text(self) -> None:
        """Gera texto para API com OAuth2."""
        scheme = SecurityScheme(
            name="oauth2",
            security_type=SecurityType.OAUTH2_PASSWORD,
            details={"token_url": "/oauth/token", "scopes": {}},
        )
        analysis = SecurityAnalysis(
            schemes={"oauth2": scheme},
            has_security=True,
        )

        text = security_to_text(analysis)

        assert "oauth2" in text.lower()
        assert "/oauth/token" in text


# =============================================================================
# TESTES DE DETECÇÃO DE ENDPOINT DE LOGIN
# =============================================================================


class TestFindLoginEndpoint:
    """Testes para find_login_endpoint."""

    def test_find_auth_login_endpoint(self) -> None:
        """Encontra endpoint /auth/login."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
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
                                                "refresh_token": {"type": "string"},
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    }
                },
                "/users": {
                    "get": {"responses": {"200": {"description": "OK"}}}
                },
            },
        }

        result = find_login_endpoint(spec)

        assert result is not None
        assert result.path == "/auth/login"
        assert result.method == "POST"
        assert result.confidence > 0.5

    def test_find_token_endpoint(self) -> None:
        """Encontra endpoint /token."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "paths": {
                "/token": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "properties": {
                                            "email": {"type": "string"},
                                            "password": {"type": "string"},
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {"200": {}},
                    }
                },
            },
        }

        result = find_login_endpoint(spec)

        assert result is not None
        assert result.path == "/token"

    def test_find_oauth_token_endpoint(self) -> None:
        """Encontra endpoint /oauth/token."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "paths": {
                "/oauth/token": {
                    "post": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "properties": {
                                                "token": {"type": "string"},
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

        result = find_login_endpoint(spec)

        assert result is not None
        assert result.path == "/oauth/token"

    def test_no_login_endpoint(self) -> None:
        """Retorna None quando não há endpoint de login."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "paths": {
                "/users": {"get": {"responses": {"200": {}}}},
                "/products": {"get": {"responses": {"200": {}}}},
            },
        }

        result = find_login_endpoint(spec)

        assert result is None

    def test_extracts_token_path(self) -> None:
        """Extrai JSONPath correto para o token."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
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
                                                "jwt_access_token": {"type": "string"},
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

        result = find_login_endpoint(spec)

        assert result is not None
        assert "jwt_access_token" in result.token_path


class TestGenerateCompleteAuthFlow:
    """Testes para generate_complete_auth_flow."""

    def test_no_auth_when_no_security(self) -> None:
        """Retorna vazio quando não há segurança."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "paths": {"/users": {"get": {}}},
        }

        auth_steps, auth_headers = generate_complete_auth_flow(spec)

        assert len(auth_steps) == 0
        assert len(auth_headers) == 0

    def test_generates_bearer_auth_flow(self) -> None:
        """Gera fluxo completo para Bearer JWT."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                    }
                }
            },
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
                        "responses": {"200": {}},
                    }
                },
            },
        }

        auth_steps, auth_headers = generate_complete_auth_flow(spec)

        assert len(auth_steps) == 1
        assert auth_steps[0].step["action"]["endpoint"] == "/auth/login"
        assert "Authorization" in auth_headers

    def test_uses_login_endpoint_override(self) -> None:
        """Usa endpoint de login fornecido manualmente."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"}
                }
            },
            "paths": {},
        }

        auth_steps, _ = generate_complete_auth_flow(
            spec, login_endpoint_override="/custom/login"
        )

        assert len(auth_steps) == 1
        assert auth_steps[0].step["action"]["endpoint"] == "/custom/login"


class TestCreateAuthenticatedPlanSteps:
    """Testes para create_authenticated_plan_steps."""

    def test_returns_original_when_no_auth(self) -> None:
        """Retorna steps originais quando não há auth."""
        spec: dict[str, Any] = {"openapi": "3.0.0", "paths": {}}
        base_steps: list[dict[str, Any]] = [{"id": "step-1", "action": {"type": "http"}}]

        result = create_authenticated_plan_steps(spec, base_steps)

        assert result == base_steps

    def test_prepends_auth_step(self) -> None:
        """Adiciona step de auth no início."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
                }
            },
            "paths": {},
        }
        base_steps: list[dict[str, Any]] = [
            {"id": "step-1", "action": {"type": "http", "endpoint": "/users"}}
        ]

        result = create_authenticated_plan_steps(spec, base_steps)

        # Primeiro step deve ser auth
        assert result[0]["id"] == "auth-setup"
        # Segundo step deve ser o original
        assert result[1]["id"] == "step-1"

    def test_injects_auth_headers(self) -> None:
        """Injeta headers de auth nos steps HTTP."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"}
                }
            },
            "paths": {
                "/login": {
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
                        "responses": {"200": {}},
                    }
                }
            },
        }
        base_steps: list[dict[str, Any]] = [
            {"id": "step-1", "action": {"type": "http", "endpoint": "/users"}}
        ]

        result = create_authenticated_plan_steps(spec, base_steps)

        # Verifica que o step HTTP tem header de Authorization
        http_step = result[-1]
        assert "headers" in http_step["action"]
        assert "Authorization" in http_step["action"]["headers"]
