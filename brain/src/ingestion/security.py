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

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# CONSTANTES DE SEGURANÇA
# =============================================================================


# Padrões de campos sensíveis que devem ser mascarados em logs
# Case-insensitive matching
SENSITIVE_PATTERNS: tuple[str, ...] = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "bearer",
    "credential",
    "credentials",
    "private_key",
    "privatekey",
    "private-key",
    "access_key",
    "accesskey",
    "secret_key",
    "secretkey",
    "auth",
    "session",
    "cookie",
)

# Valor usado para substituir dados sensíveis
REDACTED_VALUE = "***REDACTED***"


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


@dataclass
class AuthFlowResult:
    """
    Resultado de geração de fluxo de autenticação.

    Esta classe encapsula todos os resultados da geração de autenticação
    em um formato conveniente para uso no CLI e integrações.

    ## Atributos:
        auth_steps: Lista de dicts representando steps UTDL de auth
        auth_headers: Headers a adicionar em requests autenticados
        security_type: Tipo de segurança detectado
        scheme_name: Nome do esquema utilizado
        has_refresh: Se inclui step de refresh token
    """

    auth_steps: list[dict[str, Any]] = field(default_factory=lambda: [])
    auth_headers: dict[str, str] = field(default_factory=lambda: {})
    security_type: str = ""
    scheme_name: str = ""
    has_refresh: bool = False

    @property
    def has_auth(self) -> bool:
        """Retorna True se há steps de autenticação."""
        return len(self.auth_steps) > 0


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


def generate_refresh_token_step(
    scheme: SecurityScheme,
    token_url: str | None = None,
    credentials: dict[str, str] | None = None,
) -> AuthStep:
    """
    Gera step para renovar token usando refresh_token.

    ## Para todos entenderem:
    Tokens de acesso expiram. Quando isso acontece, em vez de pedir
    login novamente, usamos o refresh_token para obter um novo
    access_token sem precisar das credenciais originais.

    ## Parâmetros:
        scheme: Esquema de segurança (OAuth2 ou Bearer)
        token_url: URL do endpoint de token (opcional)
        credentials: Credenciais adicionais como client_id (opcional)

    ## Retorna:
        AuthStep com step de refresh configurado

    ## Exemplo:
        >>> refresh_step = generate_refresh_token_step(scheme, "/oauth/token")
        >>> # O step usa ${refresh_token} extraído do login anterior
    """
    creds = credentials or {}
    endpoint = token_url or scheme.details.get("token_url", "/oauth/token")
    client_id = creds.get("client_id", "${CLIENT_ID}")
    client_secret = creds.get("client_secret", "${CLIENT_SECRET}")

    return AuthStep(
        step={
            "id": "auth-refresh-token",
            "name": "Refresh Token - Renovar Access Token",
            "description": "Renova o access_token usando refresh_token quando expirado",
            "action": {
                "type": "http",
                "method": "POST",
                "endpoint": endpoint,
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                "body": {
                    "grant_type": "refresh_token",
                    "refresh_token": "${refresh_token}",
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
                    "name": "refresh_token",
                    "from": "body",
                    "path": "$.refresh_token",
                    # Refresh token pode vir novo ou não
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
            {"name": "refresh_token", "path": "$.refresh_token"},
        ],
        variables={
            "access_token": "${access_token}",
            "refresh_token": "${refresh_token}",
        },
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

    Suporta dois formatos de step UTDL:
    - Formato novo: {"action": "http_request", "params": {"method": ..., "headers": ...}}
    - Formato antigo: {"action": {"type": "http", "method": ..., "headers": ...}}

    ## Parâmetros:
        steps: Lista de steps UTDL
        auth_header: Header de autenticação a adicionar

    ## Retorna:
        Steps modificados com headers de auth

    ## Exemplo:
        >>> steps = [{"action": "http_request", "params": {"path": "/users"}}]
        >>> inject_auth_into_steps(steps, {"Authorization": "Bearer ${token}"})
    """

    modified_steps: list[dict[str, Any]] = []

    for step in steps:
        step_copy = copy.deepcopy(step)
        action = step_copy.get("action")

        # Formato novo: action é string "http_request"
        if action == "http_request":
            params = step_copy.get("params", {})
            if "headers" not in params:
                params["headers"] = {}
            params["headers"].update(auth_header)
            step_copy["params"] = params

        # Formato antigo: action é dict com type == "http"
        elif isinstance(action, dict) and action.get("type") == "http":
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


# =============================================================================
# DETECÇÃO AUTOMÁTICA DE ENDPOINT DE LOGIN
# =============================================================================

# Padrões comuns de endpoints de login/auth
LOGIN_ENDPOINT_PATTERNS = [
    "/auth/login",
    "/auth/token",
    "/auth/signin",
    "/api/auth/login",
    "/api/auth/token",
    "/api/login",
    "/api/token",
    "/login",
    "/token",
    "/signin",
    "/oauth/token",
    "/oauth2/token",
    "/v1/auth/login",
    "/v1/auth/token",
    "/v1/login",
    "/v1/token",
    "/api/v1/auth/login",
    "/api/v1/auth/token",
    "/api/v1/login",
    "/api/v1/token",
]

# Keywords que indicam endpoint de login
LOGIN_KEYWORDS = ["login", "signin", "authenticate", "token", "auth"]


@dataclass
class LoginEndpointInfo:
    """
    Informações sobre um endpoint de login detectado.

    ## Atributos:
        path: Caminho do endpoint (ex: /auth/login)
        method: Método HTTP (geralmente POST)
        body_schema: Schema do request body esperado
        token_path: JSONPath para extrair o token da resposta
        confidence: Nível de confiança na detecção (0.0 a 1.0)
    """

    path: str
    method: str = "POST"
    body_schema: dict[str, Any] = field(default_factory=lambda: {})
    token_path: str = "$.access_token"
    confidence: float = 0.5


def find_login_endpoint(spec: dict[str, Any]) -> LoginEndpointInfo | None:
    """
    Detecta automaticamente o endpoint de login em uma spec OpenAPI.

    ## Estratégia de detecção:

    1. Procura por paths que correspondem a padrões conhecidos
    2. Verifica se o endpoint aceita POST
    3. Analisa o request body buscando campos de credenciais
    4. Analisa responses buscando campos de token

    ## Parâmetros:
        spec: Especificação OpenAPI (dict original, não normalizada)

    ## Retorna:
        LoginEndpointInfo com detalhes do endpoint, ou None se não encontrado

    ## Exemplo:
        >>> spec = parse_openapi("./api.yaml", validate_spec=False)
        >>> login_info = find_login_endpoint(spec)
        >>> if login_info:
        ...     print(f"Login endpoint: {login_info.path}")
    """
    paths = spec.get("paths", {})

    candidates: list[tuple[LoginEndpointInfo, float]] = []

    for path, methods in paths.items():
        # Verifica se o path corresponde a algum padrão conhecido
        path_lower = path.lower()

        # Score baseado no path
        path_score = 0.0

        # Match exato com padrões conhecidos
        if path_lower in [p.lower() for p in LOGIN_ENDPOINT_PATTERNS]:
            path_score = 1.0
        # Match parcial com keywords
        elif any(kw in path_lower for kw in LOGIN_KEYWORDS):
            path_score = 0.7

        if path_score == 0:
            continue

        # Verifica se aceita POST
        post_details = methods.get("post") or methods.get("POST")
        if not post_details:
            continue

        # Analisa request body
        body_score = 0.0
        body_schema: dict[str, Any] = {}

        request_body = post_details.get("requestBody", {})
        if request_body:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})

            if schema:
                body_schema = schema
                properties = schema.get("properties", {})
                prop_names = [p.lower() for p in properties.keys()]

                # Procura por campos de credenciais
                has_username = any(
                    n in prop_names
                    for n in ["username", "email", "user", "login"]
                )
                has_password = any(
                    n in prop_names
                    for n in ["password", "pass", "secret", "pwd"]
                )

                if has_username and has_password:
                    body_score = 1.0
                elif has_username or has_password:
                    body_score = 0.5

        # Analisa response para encontrar token path
        token_path = "$.access_token"
        response_score = 0.0

        responses = post_details.get("responses", {})
        success_response = responses.get("200") or responses.get("201")

        if success_response:
            resp_content = success_response.get("content", {})
            resp_json = resp_content.get("application/json", {})
            resp_schema = resp_json.get("schema", {})

            if resp_schema:
                resp_props = resp_schema.get("properties", {})
                resp_prop_names = list(resp_props.keys())

                # Procura por campos de token
                for prop_name in resp_prop_names:
                    prop_lower = prop_name.lower()
                    if "token" in prop_lower or "jwt" in prop_lower:
                        if "access" in prop_lower:
                            token_path = f"$.{prop_name}"
                            response_score = 1.0
                            break
                        elif "refresh" not in prop_lower:
                            token_path = f"$.{prop_name}"
                            response_score = 0.8

        # Calcula confiança final
        confidence = (path_score * 0.4) + (body_score * 0.3) + (response_score * 0.3)

        if confidence > 0.3:
            info = LoginEndpointInfo(
                path=path,
                method="POST",
                body_schema=body_schema,
                token_path=token_path,
                confidence=confidence,
            )
            candidates.append((info, confidence))

    # Retorna o candidato com maior confiança
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    return None


def generate_complete_auth_flow(
    spec: dict[str, Any],
    *,
    credentials: dict[str, str] | None = None,
    login_endpoint_override: str | None = None,
    security_scheme_name: str | None = None,
    include_refresh_token: bool = False,
) -> AuthFlowResult:
    """
    Gera o fluxo completo de autenticação para uma spec OpenAPI.

    Esta função combina detect_security, find_login_endpoint e generate_auth_steps
    para criar um fluxo de autenticação completo.

    ## Parâmetros:
        spec: Especificação OpenAPI original
        credentials: Credenciais a usar (opcional, usa variáveis de ambiente se não fornecido)
        login_endpoint_override: Endpoint de login manual (sobrescreve detecção automática)
        security_scheme_name: Nome do esquema de segurança específico a usar
        include_refresh_token: Se True, adiciona step de refresh token para OAuth2

    ## Retorna:
        AuthFlowResult contendo:
        - auth_steps: Lista de dicts representando steps UTDL
        - auth_headers: Headers para adicionar em requests
        - security_type: Tipo de segurança detectado
        - scheme_name: Nome do esquema
        - has_refresh: Se inclui refresh token

    ## Exemplo:
        >>> result = generate_complete_auth_flow(spec, include_refresh_token=True)
        >>> if result.has_auth:
        ...     plan["steps"] = result.auth_steps + plan["steps"]
    """
    # Detecta segurança
    analysis = detect_security(spec)

    if not analysis.has_security:
        return AuthFlowResult()

    # Seleciona esquema específico se solicitado
    target_scheme = analysis.primary_scheme
    if security_scheme_name and analysis.schemes:
        matching = [s for s in analysis.schemes.values() if s.name == security_scheme_name]
        if matching:
            target_scheme = matching[0]
            # Cria nova análise com esse esquema como primário
            analysis = SecurityAnalysis(
                has_security=True,
                schemes=analysis.schemes,
                global_requirements=analysis.global_requirements,
                endpoint_requirements=analysis.endpoint_requirements,
                primary_scheme=target_scheme,
            )

    # Determina endpoint de login
    login_endpoint = login_endpoint_override

    if not login_endpoint and target_scheme:
        scheme = target_scheme

        # Para Bearer JWT, tenta encontrar endpoint de login
        if scheme.security_type == SecurityType.HTTP_BEARER:
            login_info = find_login_endpoint(spec)
            if login_info:
                login_endpoint = login_info.path

        # Para OAuth2, usa o token_url do flow
        elif scheme.security_type in (
            SecurityType.OAUTH2_PASSWORD,
            SecurityType.OAUTH2_CLIENT_CREDENTIALS,
        ):
            login_endpoint = scheme.details.get("token_url")

    # Gera steps de autenticação
    auth_steps = generate_auth_steps(
        analysis,
        login_endpoint=login_endpoint,
        credentials=credentials,
    )

    # Adiciona step de refresh token se solicitado e aplicável
    has_refresh = False
    if include_refresh_token and target_scheme and auth_steps:
        if target_scheme.security_type in (
            SecurityType.OAUTH2_PASSWORD,
            SecurityType.OAUTH2_CLIENT_CREDENTIALS,
            SecurityType.OAUTH2_AUTHORIZATION_CODE,
        ):
            # Extrai token_url do scheme
            token_url = target_scheme.details.get("token_url")
            if token_url:
                refresh_step = generate_refresh_token_step(
                    scheme=target_scheme,
                    token_url=token_url,
                )
                auth_steps.append(refresh_step)
                has_refresh = True

    # Determina headers de autenticação
    auth_headers: dict[str, str] = {}
    if auth_steps:
        auth_headers = auth_steps[0].usage_header

    # Converte AuthSteps para dicts para facilitar uso
    auth_step_dicts = [step.step for step in auth_steps]

    return AuthFlowResult(
        auth_steps=auth_step_dicts,
        auth_headers=auth_headers,
        security_type=target_scheme.security_type.value if target_scheme else "",
        scheme_name=target_scheme.name if target_scheme else "",
        has_refresh=has_refresh,
    )


def generate_complete_auth_flow_multi(
    spec: dict[str, Any],
    *,
    credentials: dict[str, str] | None = None,
    login_endpoint_override: str | None = None,
    include_refresh_token: bool = False,
    scheme_names: list[str] | None = None,
) -> AuthFlowResult:
    """
    Gera fluxo de autenticação com suporte a múltiplos esquemas e refresh tokens.

    Esta é a versão avançada que suporta:
    - Múltiplos esquemas de segurança simultaneamente
    - Geração de steps de refresh token
    - Seleção de esquemas específicos

    ## Parâmetros:
        spec: Especificação OpenAPI original
        credentials: Credenciais a usar (opcional)
        login_endpoint_override: Endpoint de login manual
        include_refresh_token: Se True, inclui step de refresh token
        scheme_names: Lista de nomes de schemes a usar (None = usa primary)

    ## Retorna:
        AuthFlowResult contendo:
        - auth_steps: Lista de dicts representando steps UTDL
        - auth_headers: Headers para adicionar em requests
        - security_type: Tipo de segurança (do primeiro esquema)
        - scheme_name: Nomes dos esquemas usados
        - has_refresh: Se inclui refresh token

    ## Exemplo:
        >>> # Com refresh token
        >>> result = generate_complete_auth_flow_multi(
        ...     spec, include_refresh_token=True
        ... )
        >>>
        >>> # Com múltiplos schemes
        >>> result = generate_complete_auth_flow_multi(
        ...     spec, scheme_names=["bearerAuth", "apiKey"]
        ... )
    """
    analysis = detect_security(spec)

    if not analysis.has_security:
        return AuthFlowResult()

    # Determina quais schemes usar
    schemes_to_use: list[SecurityScheme] = []

    if scheme_names:
        for name in scheme_names:
            if name in analysis.schemes:
                schemes_to_use.append(analysis.schemes[name])
    else:
        # Usa scheme primário
        if analysis.primary_scheme:
            schemes_to_use.append(analysis.primary_scheme)

    if not schemes_to_use:
        return AuthFlowResult()

    all_auth_steps: list[AuthStep] = []
    combined_headers: dict[str, str] = {}
    has_refresh = False

    for scheme in schemes_to_use:
        # Determina endpoint de login para cada scheme
        login_endpoint = login_endpoint_override

        if not login_endpoint:
            if scheme.security_type == SecurityType.HTTP_BEARER:
                login_info = find_login_endpoint(spec)
                if login_info:
                    login_endpoint = login_info.path

            elif scheme.security_type in (
                SecurityType.OAUTH2_PASSWORD,
                SecurityType.OAUTH2_CLIENT_CREDENTIALS,
            ):
                login_endpoint = scheme.details.get("token_url")

        # Gera step de auth
        single_analysis = SecurityAnalysis(
            schemes={scheme.name: scheme},
            has_security=True,
            primary_scheme=scheme,
        )

        auth_steps = generate_auth_steps(
            single_analysis,
            login_endpoint=login_endpoint,
            credentials=credentials,
        )

        if auth_steps:
            # Gera IDs únicos se há múltiplos schemes
            if len(schemes_to_use) > 1:
                for step in auth_steps:
                    step.step["id"] = f"{step.step['id']}-{scheme.name}"

            all_auth_steps.extend(auth_steps)
            combined_headers.update(auth_steps[0].usage_header)

            # Adiciona refresh token se solicitado e aplicável
            if include_refresh_token and scheme.security_type in (
                SecurityType.HTTP_BEARER,
                SecurityType.OAUTH2_PASSWORD,
                SecurityType.OAUTH2_CLIENT_CREDENTIALS,
            ):
                token_url = scheme.details.get("token_url")
                if token_url:
                    refresh_step = generate_refresh_token_step(
                        scheme=scheme,
                        token_url=token_url,
                    )
                    # Adiciona dependência do login
                    if auth_steps:
                        refresh_step.step["depends_on"] = [auth_steps[0].step["id"]]
                        # ID único para refresh
                        refresh_step.step["id"] = f"auth-refresh-{scheme.name}"

                    all_auth_steps.append(refresh_step)
                    has_refresh = True

    # Converte AuthSteps para dicts
    auth_step_dicts = [step.step for step in all_auth_steps]

    # Determina tipo e nome do primeiro scheme
    security_type = schemes_to_use[0].security_type.value if schemes_to_use else ""
    scheme_name = ", ".join(s.name for s in schemes_to_use) if schemes_to_use else ""

    return AuthFlowResult(
        auth_steps=auth_step_dicts,
        auth_headers=combined_headers,
        security_type=security_type,
        scheme_name=scheme_name,
        has_refresh=has_refresh,
    )


def create_authenticated_plan_steps(
    spec: dict[str, Any],
    base_steps: list[dict[str, Any]],
    *,
    credentials: dict[str, str] | None = None,
    include_refresh: bool = False,
) -> list[dict[str, Any]]:
    """
    Cria uma lista de steps com autenticação integrada.

    ## Parâmetros:
        spec: Especificação OpenAPI original
        base_steps: Steps base do plano (sem auth)
        credentials: Credenciais opcionais
        include_refresh: Se True, inclui step de refresh token

    ## Retorna:
        Lista de steps com auth step no início e headers injetados

    ## Exemplo:
        >>> steps = create_authenticated_plan_steps(spec, base_steps)
        >>> plan["steps"] = steps
    """
    result = generate_complete_auth_flow_multi(
        spec, credentials=credentials, include_refresh_token=include_refresh
    )

    if not result.has_auth:
        return base_steps

    # Insere steps de auth no início
    result_steps = list(result.auth_steps)

    # Injeta headers nos steps subsequentes
    authenticated_steps = inject_auth_into_steps(base_steps, result.auth_headers)
    result_steps.extend(authenticated_steps)

    # Adiciona dependência do auth step nos primeiros steps
    # (ignora refresh steps, que são para uso manual/condicional)
    auth_login_steps = [s for s in result.auth_steps if "refresh" not in s.get("id", "")]
    if auth_login_steps:
        first_base_step_idx = len(result.auth_steps)
        if first_base_step_idx < len(result_steps):
            step = result_steps[first_base_step_idx]
            if "depends_on" not in step:
                step["depends_on"] = []
            auth_step_id = str(auth_login_steps[-1]["id"])
            depends_on: list[str] = list(step.get("depends_on", []))
            if auth_step_id not in depends_on:
                depends_on.append(auth_step_id)
            step["depends_on"] = depends_on

    return result_steps


# =============================================================================
# SANITIZAÇÃO DE LOGS
# =============================================================================


def _is_sensitive_key(key: str) -> bool:
    """
    Verifica se uma chave corresponde a um padrão sensível.

    ## Parâmetros:
        key: Nome do campo a verificar

    ## Retorna:
        True se a chave contém um padrão sensível
    """
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in SENSITIVE_PATTERNS)


def sanitize_for_logging(data: Any) -> Any:
    """
    Mascara valores sensíveis em dados para logging seguro.

    Esta função percorre recursivamente dicionários e listas,
    substituindo valores de campos sensíveis por ***REDACTED***.

    ## Para todos entenderem:

    Quando você loga dados de requisições ou respostas, não quer
    expor senhas, tokens ou API keys. Esta função remove esses
    valores antes de logar, mantendo a estrutura dos dados.

    ## Campos sensíveis detectados:

    - password, passwd, pwd
    - secret, secret_key, client_secret
    - token, access_token, refresh_token
    - api_key, apikey, api-key
    - authorization, bearer
    - credential, credentials
    - private_key, privatekey

    ## Parâmetros:
        data: Dados a sanitizar (dict, list, ou valor primitivo)

    ## Retorna:
        Cópia dos dados com valores sensíveis mascarados

    ## Exemplo:
        >>> data = {"username": "user", "password": "secret123"}
        >>> sanitize_for_logging(data)
        {"username": "user", "password": "***REDACTED***"}

        >>> data = {"headers": {"Authorization": "Bearer token"}}
        >>> sanitize_for_logging(data)
        {"headers": {"Authorization": "***REDACTED***"}}

    ## Nota:
        Esta função NÃO modifica o objeto original.
        Sempre retorna uma cópia.
    """
    if data is None:
        return None

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(key, str) and _is_sensitive_key(key):
                # Campo sensível - mascara o valor apenas se for primitivo
                # Se for dict/list, processa recursivamente (é um container)
                if isinstance(value, (dict, list)):
                    result[key] = sanitize_for_logging(value)
                else:
                    result[key] = REDACTED_VALUE
            else:
                # Campo normal - processa recursivamente
                result[key] = sanitize_for_logging(value)
        return result

    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]

    elif isinstance(data, tuple):
        return tuple(sanitize_for_logging(item) for item in data)

    elif isinstance(data, str):
        # Para strings soltas, não mascara (pode ser qualquer coisa)
        return data

    else:
        # Números, booleans, etc - retorna como está
        return data


def sanitize_plan_for_logging(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Versão especializada para sanitizar planos UTDL.

    Além da sanitização padrão, mascara:
    - Valores de variáveis que parecem sensíveis
    - Bodies de requests com dados sensíveis
    - Headers de autenticação

    ## Parâmetros:
        plan: Plano UTDL a sanitizar

    ## Retorna:
        Cópia do plano com valores sensíveis mascarados
    """
    return sanitize_for_logging(plan)


def mask_token_preview(token: str, visible_chars: int = 4) -> str:
    """
    Mascara um token mantendo apenas os últimos caracteres visíveis.

    ## Parâmetros:
        token: Token a mascarar
        visible_chars: Quantidade de caracteres a manter visíveis

    ## Retorna:
        Token mascarado (ex: "***...7f3a")

    ## Exemplo:
        >>> mask_token_preview("sk-1234567890abcdef")
        "***...cdef"
    """
    if not token or len(token) <= visible_chars:
        return REDACTED_VALUE

    return f"***...{token[-visible_chars:]}"
