"""
================================================================================
MÓDULO DE DETECÇÃO DE SEGURANÇA
================================================================================

Este módulo analisa especificações OpenAPI e detecta esquemas de segurança,
gerando automaticamente steps de autenticação quando necessário.

## Para todos entenderem:

APIs geralmente precisam de autenticação. Este módulo:
1. Detecta qual tipo de auth a API usa (JWT, API Key, OAuth, etc.)
2. Gera um step de login/autenticação automaticamente
3. Configura extração de token para propagar aos outros steps

## Tipos de segurança suportados:

1. **API Key**: Chave fixa no header ou query param
2. **HTTP Bearer (JWT)**: Token JWT no header Authorization
3. **HTTP Basic**: Username/password codificados em base64
4. **OAuth2**: Fluxos client_credentials, password, authorization_code
5. **OpenID Connect**: Baseado em OAuth2 com discovery

## Exemplo de uso:

```python
from brain.src.ingestion.swagger import parse_openapi
from brain.src.ingestion.security import detect_security, generate_auth_steps

spec = parse_openapi("./openapi.yaml", validate_spec=False)
security_info = detect_security(spec)
auth_steps = generate_auth_steps(security_info)
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# ENUMS E TIPOS
# =============================================================================


class SecurityType(Enum):
    """Tipos de segurança suportados pelo OpenAPI."""

    API_KEY = "apiKey"
    HTTP_BEARER = "http_bearer"
    HTTP_BASIC = "http_basic"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    OAUTH2_PASSWORD = "oauth2_password"
    OAUTH2_AUTHORIZATION_CODE = "oauth2_authorization_code"
    OPENID_CONNECT = "openIdConnect"
    NONE = "none"


class ApiKeyLocation(Enum):
    """Onde a API Key é enviada."""

    HEADER = "header"
    QUERY = "query"
    COOKIE = "cookie"


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class SecurityScheme:
    """
    Representa um esquema de segurança detectado.

    ## Atributos:
        name: Nome do scheme (ex: "bearerAuth", "apiKey")
        security_type: Tipo de segurança
        description: Descrição do scheme
        details: Detalhes específicos do tipo (location, scheme, flows, etc.)
    """

    name: str
    security_type: SecurityType
    description: str = ""
    details: dict[str, Any] = field(default_factory=lambda: {})


@dataclass
class SecurityRequirement:
    """
    Representa um requisito de segurança para um endpoint.

    ## Atributos:
        scheme_name: Nome do scheme requerido
        scopes: Escopos OAuth2 necessários (se aplicável)
    """

    scheme_name: str
    scopes: list[str] = field(default_factory=lambda: [])


@dataclass
class SecurityAnalysis:
    """
    Resultado da análise de segurança de uma spec.

    ## Atributos:
        schemes: Dicionário de schemes disponíveis
        global_requirements: Requisitos de segurança globais
        endpoint_requirements: Requisitos por endpoint
        has_security: Se a API requer alguma autenticação
        primary_scheme: Scheme principal (mais usado)
    """

    schemes: dict[str, SecurityScheme] = field(default_factory=lambda: {})
    global_requirements: list[SecurityRequirement] = field(default_factory=lambda: [])
    endpoint_requirements: dict[str, list[SecurityRequirement]] = field(default_factory=lambda: {})
    has_security: bool = False
    primary_scheme: SecurityScheme | None = None


@dataclass
class AuthStep:
    """
    Step de autenticação gerado.

    ## Atributos:
        step: Step UTDL completo
        extractions: Extrações necessárias (ex: token do response)
        variables: Variáveis a definir no contexto
        usage_header: Como usar o token nos próximos steps
    """

    step: dict[str, Any]
    extractions: list[dict[str, Any]] = field(default_factory=lambda: [])
    variables: dict[str, str] = field(default_factory=lambda: {})
    usage_header: dict[str, str] = field(default_factory=lambda: {})


# =============================================================================
# FUNÇÕES DE DETECÇÃO
# =============================================================================


def detect_security(spec: dict[str, Any]) -> SecurityAnalysis:
    """
    Analisa uma spec OpenAPI e detecta esquemas de segurança.

    ## Parâmetros:
        spec: Especificação OpenAPI (dict original, não normalizada)

    ## Retorna:
        SecurityAnalysis com todos os schemes e requisitos detectados

    ## Exemplo:
        >>> spec = {"openapi": "3.0.0", "components": {"securitySchemes": {...}}}
        >>> analysis = detect_security(spec)
        >>> if analysis.has_security:
        ...     print(f"API usa: {analysis.primary_scheme.security_type}")
    """
    result = SecurityAnalysis()

    # OpenAPI 3.x: components/securitySchemes
    # Swagger 2.x: securityDefinitions
    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    if not security_schemes:
        security_schemes = spec.get("securityDefinitions", {})

    if not security_schemes:
        return result

    # Processa cada scheme
    for name, scheme_def in security_schemes.items():
        scheme = _parse_security_scheme(name, scheme_def)
        if scheme:
            result.schemes[name] = scheme

    # Detecta requisitos globais
    global_security = spec.get("security", [])
    for req in global_security:
        for scheme_name, scopes in req.items():
            result.global_requirements.append(
                SecurityRequirement(scheme_name=scheme_name, scopes=scopes)
            )

    # Detecta requisitos por endpoint
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue

            endpoint_key = f"{method.upper()} {path}"
            endpoint_security = details.get("security", [])

            for req in endpoint_security:
                for scheme_name, scopes in req.items():
                    if endpoint_key not in result.endpoint_requirements:
                        result.endpoint_requirements[endpoint_key] = []
                    result.endpoint_requirements[endpoint_key].append(
                        SecurityRequirement(scheme_name=scheme_name, scopes=scopes)
                    )

    # Determina se há segurança e qual é o scheme principal
    result.has_security = bool(result.schemes)

    if result.schemes:
        # Prioriza: Bearer JWT > OAuth2 > API Key > Basic
        priority = [
            SecurityType.HTTP_BEARER,
            SecurityType.OAUTH2_PASSWORD,
            SecurityType.OAUTH2_CLIENT_CREDENTIALS,
            SecurityType.API_KEY,
            SecurityType.HTTP_BASIC,
        ]

        for sec_type in priority:
            for scheme in result.schemes.values():
                if scheme.security_type == sec_type:
                    result.primary_scheme = scheme
                    break
            if result.primary_scheme:
                break

        # Se nenhum prioritário, pega o primeiro
        if not result.primary_scheme and result.schemes:
            result.primary_scheme = next(iter(result.schemes.values()))

    return result


def _parse_security_scheme(name: str, scheme_def: dict[str, Any]) -> SecurityScheme | None:
    """
    Parseia uma definição de security scheme.

    ## Parâmetros:
        name: Nome do scheme
        scheme_def: Definição do scheme no OpenAPI

    ## Retorna:
        SecurityScheme ou None se tipo não suportado
    """
    scheme_type = scheme_def.get("type", "")
    description = scheme_def.get("description", "")

    if scheme_type == "apiKey":
        return SecurityScheme(
            name=name,
            security_type=SecurityType.API_KEY,
            description=description,
            details={
                "location": scheme_def.get("in", "header"),
                "param_name": scheme_def.get("name", "X-API-Key"),
            },
        )

    elif scheme_type == "http":
        http_scheme = scheme_def.get("scheme", "").lower()

        if http_scheme == "bearer":
            return SecurityScheme(
                name=name,
                security_type=SecurityType.HTTP_BEARER,
                description=description,
                details={
                    "bearer_format": scheme_def.get("bearerFormat", "JWT"),
                },
            )
        elif http_scheme == "basic":
            return SecurityScheme(
                name=name,
                security_type=SecurityType.HTTP_BASIC,
                description=description,
                details={},
            )

    elif scheme_type == "oauth2":
        flows = scheme_def.get("flows", {})

        if "clientCredentials" in flows:
            flow = flows["clientCredentials"]
            return SecurityScheme(
                name=name,
                security_type=SecurityType.OAUTH2_CLIENT_CREDENTIALS,
                description=description,
                details={
                    "token_url": flow.get("tokenUrl", ""),
                    "scopes": flow.get("scopes", {}),
                },
            )
        elif "password" in flows:
            flow = flows["password"]
            return SecurityScheme(
                name=name,
                security_type=SecurityType.OAUTH2_PASSWORD,
                description=description,
                details={
                    "token_url": flow.get("tokenUrl", ""),
                    "scopes": flow.get("scopes", {}),
                },
            )
        elif "authorizationCode" in flows:
            flow = flows["authorizationCode"]
            return SecurityScheme(
                name=name,
                security_type=SecurityType.OAUTH2_AUTHORIZATION_CODE,
                description=description,
                details={
                    "authorization_url": flow.get("authorizationUrl", ""),
                    "token_url": flow.get("tokenUrl", ""),
                    "scopes": flow.get("scopes", {}),
                },
            )

    elif scheme_type == "openIdConnect":
        return SecurityScheme(
            name=name,
            security_type=SecurityType.OPENID_CONNECT,
            description=description,
            details={
                "openid_connect_url": scheme_def.get("openIdConnectUrl", ""),
            },
        )

    return None


# =============================================================================
# GERAÇÃO DE STEPS DE AUTENTICAÇÃO
# =============================================================================


def generate_auth_steps(
    analysis: SecurityAnalysis,
    *,
    login_endpoint: str | None = None,
    credentials: dict[str, str] | None = None,
) -> list[AuthStep]:
    """
    Gera steps de autenticação baseado na análise de segurança.

    ## Parâmetros:
        analysis: Resultado de detect_security()
        login_endpoint: Endpoint de login (se diferente do padrão)
        credentials: Credenciais a usar (variáveis ou valores)

    ## Retorna:
        Lista de AuthStep com steps prontos para uso

    ## Exemplo:
        >>> analysis = detect_security(spec)
        >>> auth_steps = generate_auth_steps(analysis)
        >>> for auth in auth_steps:
        ...     plan["steps"].insert(0, auth.step)
    """
    if not analysis.has_security or not analysis.primary_scheme:
        return []

    scheme = analysis.primary_scheme
    credentials = credentials or {}

    if scheme.security_type == SecurityType.API_KEY:
        return [_generate_api_key_step(scheme, credentials)]

    elif scheme.security_type == SecurityType.HTTP_BEARER:
        return [_generate_bearer_login_step(scheme, login_endpoint, credentials)]

    elif scheme.security_type == SecurityType.HTTP_BASIC:
        return [_generate_basic_auth_step(scheme, credentials)]

    elif scheme.security_type == SecurityType.OAUTH2_PASSWORD:
        return [_generate_oauth2_password_step(scheme, credentials)]

    elif scheme.security_type == SecurityType.OAUTH2_CLIENT_CREDENTIALS:
        return [_generate_oauth2_client_credentials_step(scheme, credentials)]

    return []


def _generate_api_key_step(
    scheme: SecurityScheme,
    credentials: dict[str, str],
) -> AuthStep:
    """Gera step para API Key (não requer login, apenas configura header)."""
    location = scheme.details.get("location", "header")
    param_name = scheme.details.get("param_name", "X-API-Key")
    api_key = credentials.get("api_key", "${API_KEY}")

    # API Key não precisa de step de login, apenas configura o header
    usage_header: dict[str, str] = {}

    if location == "header":
        usage_header[param_name] = api_key
    # Para query, seria query param, mas simplificamos

    return AuthStep(
        step={
            "id": "auth-setup",
            "name": "Configuração de API Key",
            "action": {
                "type": "context",
                "set": {
                    "api_key": api_key,
                    "auth_header_name": param_name,
                },
            },
            "expected": {},
        },
        extractions=[],
        variables={"api_key": api_key},
        usage_header=usage_header,
    )


def _generate_bearer_login_step(
    scheme: SecurityScheme,
    login_endpoint: str | None,
    credentials: dict[str, str],
) -> AuthStep:
    """Gera step de login para Bearer JWT."""
    endpoint = login_endpoint or "/auth/login"
    username = credentials.get("username", "${USERNAME}")
    password = credentials.get("password", "${PASSWORD}")

    return AuthStep(
        step={
            "id": "auth-login",
            "name": "Login - Obter JWT Token",
            "action": {
                "type": "http",
                "method": "POST",
                "endpoint": endpoint,
                "body": {
                    "username": username,
                    "password": password,
                },
            },
            "expected": {
                "status_code": 200,
            },
            "extract": [
                {
                    "name": "access_token",
                    "from": "body",
                    "path": "$.access_token",
                    "critical": True,
                },
                {
                    "name": "refresh_token",
                    "from": "body",
                    "path": "$.refresh_token",
                },
            ],
        },
        extractions=[
            {"name": "access_token", "path": "$.access_token"},
            {"name": "refresh_token", "path": "$.refresh_token"},
        ],
        variables={
            "access_token": "${access_token}",
            "refresh_token": "${refresh_token}",
        },
        usage_header={"Authorization": "Bearer ${access_token}"},
    )


def _generate_basic_auth_step(
    scheme: SecurityScheme,
    credentials: dict[str, str],
) -> AuthStep:
    """Gera step para HTTP Basic Auth."""
    username = credentials.get("username", "${USERNAME}")
    password = credentials.get("password", "${PASSWORD}")

    return AuthStep(
        step={
            "id": "auth-setup",
            "name": "Configuração de Basic Auth",
            "action": {
                "type": "context",
                "set": {
                    "basic_auth_user": username,
                    "basic_auth_pass": password,
                },
            },
            "expected": {},
        },
        extractions=[],
        variables={"username": username, "password": password},
        usage_header={"Authorization": f"Basic {username}:{password}"},  # Simplificado, ideal seria base64
    )


def _generate_oauth2_password_step(
    scheme: SecurityScheme,
    credentials: dict[str, str],
) -> AuthStep:
    """Gera step para OAuth2 Password Grant."""
    token_url = scheme.details.get("token_url", "/oauth/token")
    username = credentials.get("username", "${USERNAME}")
    password = credentials.get("password", "${PASSWORD}")
    client_id = credentials.get("client_id", "${CLIENT_ID}")
    client_secret = credentials.get("client_secret", "${CLIENT_SECRET}")

    return AuthStep(
        step={
            "id": "auth-oauth2-password",
            "name": "OAuth2 - Password Grant",
            "action": {
                "type": "http",
                "method": "POST",
                "endpoint": token_url,
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                "body": {
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            },
            "expected": {
                "status_code": 200,
            },
            "extract": [
                {
                    "name": "access_token",
                    "from": "body",
                    "path": "$.access_token",
                    "critical": True,
                },
                {
                    "name": "token_type",
                    "from": "body",
                    "path": "$.token_type",
                },
                {
                    "name": "expires_in",
                    "from": "body",
                    "path": "$.expires_in",
                },
            ],
        },
        extractions=[
            {"name": "access_token", "path": "$.access_token"},
        ],
        variables={"access_token": "${access_token}"},
        usage_header={"Authorization": "Bearer ${access_token}"},
    )


def _generate_oauth2_client_credentials_step(
    scheme: SecurityScheme,
    credentials: dict[str, str],
) -> AuthStep:
    """Gera step para OAuth2 Client Credentials Grant."""
    token_url = scheme.details.get("token_url", "/oauth/token")
    client_id = credentials.get("client_id", "${CLIENT_ID}")
    client_secret = credentials.get("client_secret", "${CLIENT_SECRET}")
    scope = credentials.get("scope", "")

    body: dict[str, Any] = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if scope:
        body["scope"] = scope

    return AuthStep(
        step={
            "id": "auth-oauth2-client",
            "name": "OAuth2 - Client Credentials",
            "action": {
                "type": "http",
                "method": "POST",
                "endpoint": token_url,
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                "body": body,
            },
            "expected": {
                "status_code": 200,
            },
            "extract": [
                {
                    "name": "access_token",
                    "from": "body",
                    "path": "$.access_token",
                    "critical": True,
                },
            ],
        },
        extractions=[
            {"name": "access_token", "path": "$.access_token"},
        ],
        variables={"access_token": "${access_token}"},
        usage_header={"Authorization": "Bearer ${access_token}"},
    )


# =============================================================================
# FUNÇÕES DE UTILIDADE
# =============================================================================


def get_auth_header_for_scheme(scheme: SecurityScheme) -> dict[str, str]:
    """
    Retorna o header de autenticação apropriado para um scheme.

    ## Parâmetros:
        scheme: SecurityScheme detectado

    ## Retorna:
        Dict com header name -> value template
    """
    if scheme.security_type == SecurityType.API_KEY:
        location = scheme.details.get("location", "header")
        if location == "header":
            param_name = scheme.details.get("param_name", "X-API-Key")
            return {param_name: "${api_key}"}
        return {}

    elif scheme.security_type in (
        SecurityType.HTTP_BEARER,
        SecurityType.OAUTH2_PASSWORD,
        SecurityType.OAUTH2_CLIENT_CREDENTIALS,
    ):
        return {"Authorization": "Bearer ${access_token}"}

    elif scheme.security_type == SecurityType.HTTP_BASIC:
        return {"Authorization": "Basic ${basic_auth_encoded}"}

    return {}


def inject_auth_into_steps(
    steps: list[dict[str, Any]],
    auth_header: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Injeta headers de autenticação em todos os steps HTTP.

    ## Parâmetros:
        steps: Lista de steps UTDL
        auth_header: Header de autenticação a adicionar

    ## Retorna:
        Steps modificados com headers de auth

    ## Exemplo:
        >>> steps = [{"action": {"type": "http", "endpoint": "/users"}}]
        >>> inject_auth_into_steps(steps, {"Authorization": "Bearer ${token}"})
    """
    import copy

    modified_steps: list[dict[str, Any]] = []

    for step in steps:
        step_copy = copy.deepcopy(step)
        action = step_copy.get("action", {})

        if action.get("type") == "http":
            if "headers" not in action:
                action["headers"] = {}
            action["headers"].update(auth_header)

        modified_steps.append(step_copy)

    return modified_steps


def security_to_text(analysis: SecurityAnalysis) -> str:
    """
    Converte análise de segurança para texto legível.

    ## Parâmetros:
        analysis: Resultado de detect_security()

    ## Retorna:
        Texto descrevendo a segurança da API
    """
    if not analysis.has_security:
        return "API não requer autenticação."

    lines = ["Segurança da API:", ""]

    for name, scheme in analysis.schemes.items():
        lines.append(f"- {name}: {scheme.security_type.value}")
        if scheme.description:
            lines.append(f"  Descrição: {scheme.description}")

        if scheme.security_type == SecurityType.API_KEY:
            loc = scheme.details.get("location", "header")
            param = scheme.details.get("param_name", "")
            lines.append(f"  Local: {loc}, Parâmetro: {param}")

        elif scheme.security_type in (
            SecurityType.OAUTH2_PASSWORD,
            SecurityType.OAUTH2_CLIENT_CREDENTIALS,
        ):
            token_url = scheme.details.get("token_url", "")
            lines.append(f"  Token URL: {token_url}")

    if analysis.global_requirements:
        lines.append("")
        lines.append("Requisitos globais:")
        for req in analysis.global_requirements:
            scopes = ", ".join(req.scopes) if req.scopes else "nenhum"
            lines.append(f"  - {req.scheme_name} (scopes: {scopes})")

    return "\n".join(lines)
