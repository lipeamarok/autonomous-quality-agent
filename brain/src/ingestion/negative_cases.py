"""
================================================================================
MÃ“DULO DE GERAÃ‡ÃƒO DE CASOS NEGATIVOS
================================================================================

Este mÃ³dulo analisa especificaÃ§Ãµes OpenAPI e gera casos de teste negativos
automaticamente. Casos negativos testam comportamentos de erro da API.

## Para todos entenderem:

Casos negativos sÃ£o testes que propositalmente enviam dados invÃ¡lidos para
verificar se a API responde corretamente com erros (cÃ³digos 4xx).

## Tipos de casos negativos gerados:

1. **Campos obrigatÃ³rios ausentes**: Remove campos required do body
2. **Tipos invÃ¡lidos**: Envia string onde espera number, etc.
3. **Limites excedidos**: Valores alÃ©m de min/max, strings muito longas
4. **Formatos invÃ¡lidos**: Email invÃ¡lido, UUID malformado, etc.
5. **Valores vazios**: String vazia, array vazio, null

## Exemplo de uso:

```python
from brain.src.ingestion.swagger import parse_openapi
from brain.src.ingestion.negative_cases import generate_negative_cases

spec = parse_openapi("./openapi.yaml")
negative_steps = generate_negative_cases(spec)
# negative_steps Ã© uma lista de steps UTDL prontos para testar erros
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# TIPOS DE CASOS NEGATIVOS
# =============================================================================


@dataclass
class NegativeCase:
    """
    Representa um caso de teste negativo gerado.

    ## Atributos:
        case_type: Tipo do caso negativo (missing_required, invalid_type, etc.)
        field_name: Nome do campo sendo testado
        description: Descrição legível do teste
        invalid_value: Valor inválido a ser enviado
        expected_status: Código HTTP esperado (400, 422, etc.)
        endpoint_path: Path do endpoint (ex: /users)
        endpoint_method: Método HTTP (POST, PUT, etc.)
        expected_status_range: Range de status opcional (ex: "4xx")
    """

    case_type: str
    field_name: str
    description: str
    invalid_value: Any
    expected_status: int
    endpoint_path: str
    endpoint_method: str
    expected_status_range: str | None = None  # "4xx", "5xx", etc.


@dataclass
class NegativeTestResult:
    """
    Resultado da análise de uma spec para casos negativos.

    ## Atributos:
        cases: Lista de casos negativos gerados
        endpoints_analyzed: Número de endpoints analisados
        fields_analyzed: Número de campos analisados
    """

    cases: list[NegativeCase] = field(default_factory=lambda: [])
    endpoints_analyzed: int = 0
    fields_analyzed: int = 0


@dataclass
class RobustnessCase:
    """
    Representa um caso de teste de robustez.

    Testes de robustez verificam como a API lida com:
    - Headers malformados ou inesperados
    - Campos extras não definidos no schema
    - Content-Types inválidos
    - Payloads muito grandes

    ## Atributos:
        case_type: Tipo do caso (invalid_header, extra_field, wrong_content_type, etc.)
        description: Descrição legível do teste
        endpoint_path: Path do endpoint (ex: /users)
        endpoint_method: Método HTTP (POST, PUT, etc.)
        headers: Headers a serem enviados
        body: Body a ser enviado (opcional)
        expected_status_range: Range de status esperado (ex: "4xx")
    """

    case_type: str
    description: str
    endpoint_path: str
    endpoint_method: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    expected_status_range: str = "4xx"


# =============================================================================
# GERADORES DE VALORES INVÁLIDOS
# =============================================================================


def generate_invalid_values_for_type(
    field_type: str,
    field_format: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> list[tuple[str, Any, str]]:
    """
    Gera valores invÃ¡lidos para um tipo de campo especÃ­fico.

    ## ParÃ¢metros:
        field_type: Tipo do campo (string, integer, number, boolean, array, object)
        field_format: Formato opcional (email, uuid, date, etc.)
        constraints: RestriÃ§Ãµes opcionais (minLength, maxLength, minimum, maximum, etc.)

    ## Retorna:
        Lista de tuplas (case_type, invalid_value, description)
    """
    invalid_values: list[tuple[str, Any, str]] = []
    constraints = constraints or {}

    # -----------------------------------------------------------------
    # Tipo errado (comum a todos)
    # -----------------------------------------------------------------

    if field_type == "string":
        invalid_values.append(("invalid_type", 12345, "nÃºmero em vez de string"))
        invalid_values.append(("invalid_type", True, "boolean em vez de string"))
        invalid_values.append(("invalid_type", ["array"], "array em vez de string"))

        # String vazia (se nÃ£o permitido)
        if constraints.get("minLength", 0) > 0:
            invalid_values.append(("empty_value", "", "string vazia"))

        # String muito longa
        if "maxLength" in constraints:
            max_len = constraints["maxLength"]
            invalid_values.append((
                "limit_exceeded",
                "x" * (max_len + 10),
                f"string com {max_len + 10} chars (max: {max_len})",
            ))

        # String muito curta
        if "minLength" in constraints and constraints["minLength"] > 0:
            min_len = constraints["minLength"]
            invalid_values.append((
                "limit_exceeded",
                "x" * max(0, min_len - 1),
                f"string com {min_len - 1} chars (min: {min_len})",
            ))

    elif field_type == "integer":
        invalid_values.append(("invalid_type", "not_a_number", "string em vez de integer"))
        invalid_values.append(("invalid_type", 3.14, "float em vez de integer"))
        invalid_values.append(("invalid_type", True, "boolean em vez de integer"))

        # Valores alÃ©m dos limites
        if "minimum" in constraints:
            min_val = constraints["minimum"]
            invalid_values.append((
                "limit_exceeded",
                min_val - 1,
                f"valor {min_val - 1} abaixo do mÃ­nimo ({min_val})",
            ))

        if "maximum" in constraints:
            max_val = constraints["maximum"]
            invalid_values.append((
                "limit_exceeded",
                max_val + 1,
                f"valor {max_val + 1} acima do mÃ¡ximo ({max_val})",
            ))

    elif field_type == "number":
        invalid_values.append(("invalid_type", "not_a_number", "string em vez de number"))
        invalid_values.append(("invalid_type", True, "boolean em vez de number"))

        if "minimum" in constraints:
            min_val = constraints["minimum"]
            invalid_values.append((
                "limit_exceeded",
                min_val - 0.1,
                f"valor {min_val - 0.1} abaixo do mÃ­nimo ({min_val})",
            ))

        if "maximum" in constraints:
            max_val = constraints["maximum"]
            invalid_values.append((
                "limit_exceeded",
                max_val + 0.1,
                f"valor {max_val + 0.1} acima do mÃ¡ximo ({max_val})",
            ))

    elif field_type == "boolean":
        invalid_values.append(("invalid_type", "true", "string 'true' em vez de boolean"))
        invalid_values.append(("invalid_type", 1, "nÃºmero 1 em vez de boolean"))
        invalid_values.append(("invalid_type", "yes", "string 'yes' em vez de boolean"))

    elif field_type == "array":
        invalid_values.append(("invalid_type", "not_an_array", "string em vez de array"))
        invalid_values.append(("invalid_type", {"key": "value"}, "object em vez de array"))

        if constraints.get("minItems", 0) > 0:
            invalid_values.append(("empty_value", [], "array vazio"))

        if "maxItems" in constraints:
            max_items = constraints["maxItems"]
            invalid_values.append((
                "limit_exceeded",
                ["item"] * (max_items + 1),
                f"array com {max_items + 1} items (max: {max_items})",
            ))

    elif field_type == "object":
        invalid_values.append(("invalid_type", "not_an_object", "string em vez de object"))
        invalid_values.append(("invalid_type", ["array"], "array em vez de object"))

    # -----------------------------------------------------------------
    # Formatos especÃ­ficos
    # -----------------------------------------------------------------

    if field_format == "email":
        invalid_values.append(("invalid_format", "not-an-email", "email invÃ¡lido"))
        invalid_values.append(("invalid_format", "@missing-local.com", "email sem parte local"))
        invalid_values.append(("invalid_format", "missing-domain@", "email sem domÃ­nio"))

    elif field_format == "uuid":
        invalid_values.append(("invalid_format", "not-a-uuid", "UUID invÃ¡lido"))
        invalid_values.append(("invalid_format", "12345", "UUID muito curto"))

    elif field_format == "date":
        invalid_values.append(("invalid_format", "not-a-date", "data invÃ¡lida"))
        invalid_values.append(("invalid_format", "2024-13-45", "data com mÃªs/dia invÃ¡lido"))

    elif field_format == "date-time":
        invalid_values.append(("invalid_format", "not-a-datetime", "datetime invÃ¡lido"))
        invalid_values.append(("invalid_format", "2024-01-01", "datetime sem hora"))

    elif field_format == "uri":
        invalid_values.append(("invalid_format", "not-a-uri", "URI inválida"))
        invalid_values.append(("invalid_format", "ftp://", "URI incompleta"))

    # -----------------------------------------------------------------
    # Valores fora de enumeração
    # -----------------------------------------------------------------

    if "enum" in constraints:
        enum_values = constraints["enum"]
        if enum_values:
            # Gera valor que não está no enum
            invalid_values.append((
                "invalid_enum",
                "__INVALID_ENUM_VALUE__",
                f"valor fora do enum {enum_values}",
            ))

            # String vazia se enum não incluir
            if "" not in enum_values:
                invalid_values.append((
                    "invalid_enum",
                    "",
                    "string vazia não está no enum",
                ))

            # Tipo diferente do enum (se enum é de strings, envia número)
            if all(isinstance(v, str) for v in enum_values):
                invalid_values.append((
                    "invalid_enum",
                    99999,
                    "número em vez de valor do enum",
                ))

            # Case sensitivity test (se enum tem strings)
            if enum_values and isinstance(enum_values[0], str):
                # Testa variação de case
                first_val = enum_values[0]
                if first_val.lower() != first_val:
                    invalid_values.append((
                        "invalid_enum",
                        first_val.lower(),
                        f"'{first_val.lower()}' (lowercase) não está no enum",
                    ))
                elif first_val.upper() != first_val:
                    invalid_values.append((
                        "invalid_enum",
                        first_val.upper(),
                        f"'{first_val.upper()}' (uppercase) não está no enum",
                    ))

    # -----------------------------------------------------------------
    # Boundary values (valores nos limites exatos)
    # -----------------------------------------------------------------

    if field_type in ("integer", "number"):
        # Valor exatamente no limite (deve passar, mas testamos edge)
        if "minimum" in constraints and "exclusiveMinimum" in constraints:
            min_val = constraints["minimum"]
            invalid_values.append((
                "boundary_violation",
                min_val,
                f"valor {min_val} igual ao mínimo exclusivo",
            ))

        if "maximum" in constraints and "exclusiveMaximum" in constraints:
            max_val = constraints["maximum"]
            invalid_values.append((
                "boundary_violation",
                max_val,
                f"valor {max_val} igual ao máximo exclusivo",
            ))

    # Null (se não permitido)
    if not constraints.get("nullable", False):
        invalid_values.append(("null_value", None, "valor null"))

    return invalid_values


# =============================================================================
# ANÃLISE DE SCHEMAS
# =============================================================================


def extract_fields_from_schema(
    schema: dict[str, Any],
    parent_path: str = "",
) -> list[dict[str, Any]]:
    """
    Extrai campos de um schema OpenAPI, incluindo nested objects.

    ## ParÃ¢metros:
        schema: Schema JSON do OpenAPI
        parent_path: Caminho do objeto pai (para campos nested)

    ## Retorna:
        Lista de dicionÃ¡rios com informaÃ§Ãµes de cada campo
    """
    fields: list[dict[str, Any]] = []

    # Schema pode ter allOf, oneOf, anyOf - simplificamos pegando properties direto
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_schema in properties.items():
        full_path = f"{parent_path}.{field_name}" if parent_path else field_name

        field_info: dict[str, Any] = {
            "name": field_name,
            "full_path": full_path,
            "type": field_schema.get("type", "string"),
            "format": field_schema.get("format"),
            "required": field_name in required_fields,
            "constraints": {},
        }

        # Extrai constraints
        for constraint in ["minLength", "maxLength", "minimum", "maximum",
                          "minItems", "maxItems", "pattern", "enum", "nullable"]:
            if constraint in field_schema:
                field_info["constraints"][constraint] = field_schema[constraint]

        fields.append(field_info)

        # Processa nested objects
        if field_schema.get("type") == "object" and "properties" in field_schema:
            nested_fields = extract_fields_from_schema(field_schema, full_path)
            fields.extend(nested_fields)

        # Processa items de arrays
        if field_schema.get("type") == "array" and "items" in field_schema:
            items_schema = field_schema["items"]
            if items_schema.get("type") == "object" and "properties" in items_schema:
                nested_fields = extract_fields_from_schema(items_schema, f"{full_path}[]")
                fields.extend(nested_fields)

    return fields


# =============================================================================
# GERAÃ‡ÃƒO DE CASOS NEGATIVOS
# =============================================================================


def generate_negative_cases(
    spec: dict[str, Any],
    *,
    include_types: list[str] | None = None,
    exclude_endpoints: list[str] | None = None,
    max_cases_per_field: int = 3,
) -> NegativeTestResult:
    """
    Gera casos de teste negativos a partir de uma spec OpenAPI normalizada.

    ## Parâmetros:
        spec: Especificação normalizada (output de parse_openapi)
        include_types: Tipos de casos a incluir (None = todos)
            Opções: missing_required, invalid_type, limit_exceeded,
                    invalid_format, empty_value, null_value,
                    invalid_enum, boundary_violation
        exclude_endpoints: Paths de endpoints a ignorar
        max_cases_per_field: Máximo de casos por campo (default: 3)

    ## Retorna:
        NegativeTestResult com lista de casos gerados

    ## Exemplo:
        >>> spec = parse_openapi("./api.yaml")
        >>> result = generate_negative_cases(spec)
        >>> for case in result.cases:
        ...     print(f"{case.endpoint_method} {case.endpoint_path}: {case.description}")
    """
    result = NegativeTestResult()
    exclude_endpoints = exclude_endpoints or []
    include_types = include_types or [
        "missing_required",
        "invalid_type",
        "limit_exceeded",
        "invalid_format",
        "empty_value",
        "null_value",
        "invalid_enum",
        "boundary_violation",
    ]

    endpoints = spec.get("endpoints", [])

    for endpoint in endpoints:
        path = endpoint.get("path", "")
        method = endpoint.get("method", "")

        # Pula endpoints excluÃ­dos
        if path in exclude_endpoints:
            continue

        # SÃ³ analisa endpoints que aceitam body (POST, PUT, PATCH)
        if method not in ("POST", "PUT", "PATCH"):
            continue

        result.endpoints_analyzed += 1

        # Extrai schema do request body
        request_body = endpoint.get("request_body")
        if not request_body or not request_body.get("schema"):
            continue

        schema = request_body["schema"]
        fields = extract_fields_from_schema(schema)
        result.fields_analyzed += len(fields)

        # Gera casos para campos obrigatórios ausentes
        if "missing_required" in include_types:
            required_fields = [f for f in fields if f["required"]]
            for field_info in required_fields:
                case = NegativeCase(
                    case_type="missing_required",
                    field_name=field_info["full_path"],
                    description=f"campo obrigatório '{field_info['full_path']}' ausente",
                    invalid_value="__OMIT__",  # Marcador especial para omitir o campo
                    expected_status=400,
                    endpoint_path=path,
                    endpoint_method=method,
                    expected_status_range="4xx",  # Qualquer erro cliente é válido
                )
                result.cases.append(case)

        # Gera casos para cada campo
        for field_info in fields:
            invalid_values = generate_invalid_values_for_type(
                field_info["type"],
                field_info.get("format"),
                field_info.get("constraints"),
            )

            # Limita número de casos por campo
            cases_added = 0

            for case_type, invalid_value, description in invalid_values:
                if case_type not in include_types:
                    continue

                if cases_added >= max_cases_per_field:
                    break

                # Determina o status esperado baseado no tipo de caso
                expected_status = 400 if case_type != "invalid_format" else 422

                # Para a maioria dos casos negativos, qualquer 4xx é válido
                # pois diferentes APIs podem retornar 400, 422, ou outros códigos 4xx
                status_range = "4xx"

                case = NegativeCase(
                    case_type=case_type,
                    field_name=field_info["full_path"],
                    description=f"{field_info['full_path']}: {description}",
                    invalid_value=invalid_value,
                    expected_status=expected_status,
                    endpoint_path=path,
                    endpoint_method=method,
                    expected_status_range=status_range,
                )
                result.cases.append(case)
                cases_added += 1

    return result


# =============================================================================
# GERAÇÃO DE CASOS DE ROBUSTEZ
# =============================================================================


def generate_robustness_cases(
    spec: dict[str, Any],
    include_types: list[str] | None = None,
    exclude_endpoints: list[str] | None = None,
) -> list[RobustnessCase]:
    """
    Gera casos de teste de robustez a partir de uma spec OpenAPI.

    Testes de robustez verificam comportamentos edge-case da API:
    - Headers malformados
    - Content-Types inválidos
    - Campos extras não definidos
    - Payloads vazios ou malformados

    ## Parâmetros:
        spec: Especificação normalizada (output de parse_openapi)
        include_types: Tipos de casos a incluir (None = todos)
            Opções: invalid_header, wrong_content_type, extra_field,
                    empty_body, malformed_json, oversized_value
        exclude_endpoints: Paths de endpoints a ignorar

    ## Retorna:
        Lista de RobustnessCase

    ## Exemplo:
        >>> spec = parse_openapi("./api.yaml")
        >>> cases = generate_robustness_cases(spec)
        >>> for case in cases:
        ...     print(f"{case.case_type}: {case.description}")
    """
    cases: list[RobustnessCase] = []
    exclude_endpoints = exclude_endpoints or []
    include_types = include_types or [
        "invalid_header",
        "wrong_content_type",
        "extra_field",
        "empty_body",
        "malformed_json",
        "oversized_value",
    ]

    endpoints = spec.get("endpoints", [])

    for endpoint in endpoints:
        path = endpoint.get("path", "")
        method = endpoint.get("method", "")

        # Pula endpoints excluídos
        if path in exclude_endpoints:
            continue

        # Só analisa endpoints que aceitam body (POST, PUT, PATCH)
        if method not in ("POST", "PUT", "PATCH"):
            continue

        # =====================================================================
        # CASO: Headers inválidos
        # =====================================================================
        if "invalid_header" in include_types:
            # Content-Type inválido
            cases.append(RobustnessCase(
                case_type="invalid_header",
                description=f"{method} {path}: Content-Type inválido (text/plain)",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "text/plain"},
                body='{"test": "data"}',
                expected_status_range="4xx",
            ))

            # Header Authorization malformado
            cases.append(RobustnessCase(
                case_type="invalid_header",
                description=f"{method} {path}: Authorization header malformado",
                endpoint_path=path,
                endpoint_method=method,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "InvalidScheme token123",
                },
                body={},
                expected_status_range="4xx",
            ))

            # Accept header incompatível
            cases.append(RobustnessCase(
                case_type="invalid_header",
                description=f"{method} {path}: Accept header incompatível",
                endpoint_path=path,
                endpoint_method=method,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/xml",
                },
                body={},
                expected_status_range="4xx",  # Pode retornar 406 Not Acceptable
            ))

        # =====================================================================
        # CASO: Content-Type errado
        # =====================================================================
        if "wrong_content_type" in include_types:
            cases.append(RobustnessCase(
                case_type="wrong_content_type",
                description=f"{method} {path}: JSON enviado como form-data",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                body='{"test": "data"}',
                expected_status_range="4xx",
            ))

            cases.append(RobustnessCase(
                case_type="wrong_content_type",
                description=f"{method} {path}: Content-Type multipart sem boundary",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "multipart/form-data"},  # Sem boundary
                body='{"test": "data"}',
                expected_status_range="4xx",
            ))

        # =====================================================================
        # CASO: Campos extras não definidos no schema
        # =====================================================================
        if "extra_field" in include_types:
            cases.append(RobustnessCase(
                case_type="extra_field",
                description=f"{method} {path}: Campo extra inesperado no body",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body={
                    "__extra_field_not_in_schema__": "unexpected_value",
                    "__another_random_field__": 12345,
                },
                expected_status_range="2xx",  # Deve aceitar ou ignorar campos extras
            ))

            cases.append(RobustnessCase(
                case_type="extra_field",
                description=f"{method} {path}: Campo com nome especial (__proto__)",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body={
                    "__proto__": {"admin": True},  # Tentativa de prototype pollution
                },
                expected_status_range="4xx",  # Deve rejeitar por segurança
            ))

        # =====================================================================
        # CASO: Body vazio
        # =====================================================================
        if "empty_body" in include_types:
            cases.append(RobustnessCase(
                case_type="empty_body",
                description=f"{method} {path}: Body completamente vazio",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body=None,
                expected_status_range="4xx",
            ))

            cases.append(RobustnessCase(
                case_type="empty_body",
                description=f"{method} {path}: Body como objeto JSON vazio",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body={},
                expected_status_range="4xx",  # Depende se há campos obrigatórios
            ))

        # =====================================================================
        # CASO: JSON malformado
        # =====================================================================
        if "malformed_json" in include_types:
            cases.append(RobustnessCase(
                case_type="malformed_json",
                description=f"{method} {path}: JSON com sintaxe inválida",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body='{"invalid": json, missing quotes}',
                expected_status_range="4xx",
            ))

            cases.append(RobustnessCase(
                case_type="malformed_json",
                description=f"{method} {path}: JSON truncado",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body='{"name": "test", "age":',
                expected_status_range="4xx",
            ))

        # =====================================================================
        # CASO: Valores muito grandes
        # =====================================================================
        if "oversized_value" in include_types:
            # String muito longa
            oversized_string = "x" * 100000  # 100KB de 'x'
            cases.append(RobustnessCase(
                case_type="oversized_value",
                description=f"{method} {path}: String de 100KB",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body={"oversized_field": oversized_string},
                expected_status_range="4xx",  # Deve rejeitar payload muito grande
            ))

            # Array muito grande
            cases.append(RobustnessCase(
                case_type="oversized_value",
                description=f"{method} {path}: Array com 10000 itens",
                endpoint_path=path,
                endpoint_method=method,
                headers={"Content-Type": "application/json"},
                body={"items": list(range(10000))},
                expected_status_range="4xx",
            ))

    return cases


def robustness_cases_to_utdl_steps(
    cases: list[RobustnessCase],
) -> list[dict[str, Any]]:
    """
    Converte casos de robustez para steps UTDL.

    ## Parâmetros:
        cases: Lista de RobustnessCase

    ## Retorna:
        Lista de steps UTDL formatados
    """
    steps: list[dict[str, Any]] = []

    for i, case in enumerate(cases, 1):
        step_id = f"robust-{i:03d}"

        step: dict[str, Any] = {
            "id": step_id,
            "name": f"Robustness: {case.description}",
            "action": {
                "type": "http",
                "method": case.endpoint_method,
                "endpoint": case.endpoint_path,
            },
            "assertions": [
                {
                    "type": "status_range",
                    "operator": "eq",
                    "value": case.expected_status_range,
                }
            ],
        }

        # Adiciona headers se existirem
        if case.headers:
            step["action"]["headers"] = case.headers

        # Adiciona body se existir
        if case.body is not None:
            step["action"]["body"] = case.body

        steps.append(step)

    return steps


# =============================================================================
# GERAÇÃO DE ASSERTIONS DE LATÊNCIA
# =============================================================================


@dataclass
class LatencySLA:
    """
    Define SLAs de latência para diferentes tipos de endpoints.

    ## Atributos:
        endpoint_pattern: Padrão regex para match de endpoints
        max_latency_ms: Latência máxima em milissegundos
        p99_latency_ms: Latência P99 (opcional, para métricas avançadas)
        description: Descrição do SLA
    """
    endpoint_pattern: str
    max_latency_ms: int
    p99_latency_ms: int | None = None
    description: str = ""


# SLAs padrão por tipo de operação
DEFAULT_LATENCY_SLAS = [
    LatencySLA(
        endpoint_pattern=r"^(GET|HEAD)\s",
        max_latency_ms=200,
        p99_latency_ms=500,
        description="Leituras devem ser rápidas",
    ),
    LatencySLA(
        endpoint_pattern=r"^(POST|PUT|PATCH)\s.*/(auth|login|token)",
        max_latency_ms=1000,
        p99_latency_ms=2000,
        description="Autenticação pode ser mais lenta",
    ),
    LatencySLA(
        endpoint_pattern=r"^(POST|PUT|PATCH)\s",
        max_latency_ms=500,
        p99_latency_ms=1000,
        description="Escritas devem ser moderadamente rápidas",
    ),
    LatencySLA(
        endpoint_pattern=r"^DELETE\s",
        max_latency_ms=300,
        p99_latency_ms=600,
        description="Deleções devem ser rápidas",
    ),
]


def generate_latency_assertions(
    spec: dict[str, Any],
    slas: list[LatencySLA] | None = None,
    default_max_latency_ms: int = 500,
) -> dict[str, dict[str, Any]]:
    """
    Gera assertions de latência para cada endpoint baseado em SLAs.

    ## Parâmetros:
        spec: Especificação normalizada (output de parse_openapi)
        slas: Lista de SLAs customizados (None = usa defaults)
        default_max_latency_ms: Latência máxima padrão quando nenhum SLA match

    ## Retorna:
        Dict mapping endpoint_key -> assertion config
        Onde endpoint_key é "METHOD /path"

    ## Exemplo:
        >>> spec = parse_openapi("./api.yaml")
        >>> assertions = generate_latency_assertions(spec)
        >>> assertions["GET /users"]
        {'type': 'latency', 'operator': 'lt', 'value': 200}
    """
    import re

    slas = slas or DEFAULT_LATENCY_SLAS
    latency_assertions: dict[str, dict[str, Any]] = {}

    endpoints = spec.get("endpoints", [])

    for endpoint in endpoints:
        path = endpoint.get("path", "")
        method = endpoint.get("method", "")
        endpoint_key = f"{method} {path}"

        # Encontra o SLA que corresponde a este endpoint
        matched_sla = None
        for sla in slas:
            if re.match(sla.endpoint_pattern, endpoint_key, re.IGNORECASE):
                matched_sla = sla
                break

        # Define latência máxima
        max_latency = matched_sla.max_latency_ms if matched_sla else default_max_latency_ms

        latency_assertions[endpoint_key] = {
            "type": "latency",
            "operator": "lt",
            "value": max_latency,
        }

        # Se tem P99, adiciona como assertion secundária
        if matched_sla and matched_sla.p99_latency_ms:
            latency_assertions[f"{endpoint_key}_p99"] = {
                "type": "latency",
                "operator": "lt",
                "value": matched_sla.p99_latency_ms,
                "description": f"P99 SLA for {endpoint_key}",
            }

    return latency_assertions


def inject_latency_assertions(
    steps: list[dict[str, Any]],
    spec: dict[str, Any] | None = None,
    default_max_latency_ms: int = 500,
) -> list[dict[str, Any]]:
    """
    Injeta assertions de latência em steps existentes.

    ## Parâmetros:
        steps: Lista de steps UTDL
        spec: Especificação OpenAPI (opcional, para SLAs inteligentes)
        default_max_latency_ms: Latência máxima padrão

    ## Retorna:
        Steps com assertions de latência adicionadas

    ## Exemplo:
        >>> steps = [{"id": "step-1", "action": {"type": "http", "method": "GET", ...}}]
        >>> enriched_steps = inject_latency_assertions(steps)
        >>> enriched_steps[0]["assertions"]
        [{"type": "latency", "operator": "lt", "value": 200}]
    """
    import copy

    # Gera SLAs se tiver spec
    latency_config = {}
    if spec:
        latency_config = generate_latency_assertions(spec, default_max_latency_ms=default_max_latency_ms)

    enriched_steps = []

    for step in steps:
        step_copy = copy.deepcopy(step)

        # Só injeta em steps HTTP
        action = step_copy.get("action", {})
        if action.get("type") != "http":
            enriched_steps.append(step_copy)
            continue

        method = action.get("method", "GET")
        endpoint = action.get("endpoint", "")
        endpoint_key = f"{method} {endpoint}"

        # Inicializa assertions se não existir
        if "assertions" not in step_copy:
            step_copy["assertions"] = []

        # Adiciona assertion de latência
        if endpoint_key in latency_config:
            latency_assertion = latency_config[endpoint_key]
        else:
            # Usa default baseado no método
            if method in ("GET", "HEAD"):
                max_latency = 200
            elif method in ("POST", "PUT", "PATCH"):
                max_latency = 500
            else:
                max_latency = default_max_latency_ms

            latency_assertion = {
                "type": "latency",
                "operator": "lt",
                "value": max_latency,
            }

        # Só adiciona se não existir assertion de latência
        existing_latency = any(
            a.get("type") == "latency"
            for a in step_copy["assertions"]
        )

        if not existing_latency:
            step_copy["assertions"].append(latency_assertion)

        enriched_steps.append(step_copy)

    return enriched_steps


# =============================================================================
# GERAÇÃO DE ASSERTIONS JSON SCHEMA
# =============================================================================


@dataclass
class SchemaAssertion:
    """
    Representa uma assertion de JSON Schema para validação de resposta.

    ## Atributos:
        endpoint_key: Chave do endpoint (ex: "GET /users")
        schema: JSON Schema para validação
        path: Path opcional dentro da resposta (ex: "data.user")
        operator: "valid" ou "invalid"
        description: Descrição legível
    """

    endpoint_key: str
    schema: dict[str, Any]
    path: str | None = None
    operator: str = "valid"
    description: str = ""


def openapi_schema_to_json_schema(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Converte um schema OpenAPI para JSON Schema compatível.

    OpenAPI 3.0 usa um subconjunto de JSON Schema Draft 4/5 com extensões.
    Esta função converte para um formato JSON Schema padrão.

    ## Parâmetros:
        openapi_schema: Schema no formato OpenAPI

    ## Retorna:
        Schema no formato JSON Schema

    ## Exemplo:
        >>> openapi_schema = {"type": "string", "nullable": True}
        >>> json_schema = openapi_schema_to_json_schema(openapi_schema)
        >>> json_schema
        {'anyOf': [{'type': 'string'}, {'type': 'null'}]}
    """
    import copy
    from typing import cast

    schema: dict[str, Any] = copy.deepcopy(openapi_schema)

    # Remove keywords específicas do OpenAPI que não existem em JSON Schema
    openapi_keywords = [
        "nullable", "discriminator", "readOnly", "writeOnly",
        "xml", "externalDocs", "example", "deprecated"
    ]

    # Trata nullable -> anyOf com null
    if schema.get("nullable"):
        schema.pop("nullable", None)
        # Cria anyOf com o tipo original e null
        original_schema = {k: v for k, v in schema.items() if k not in openapi_keywords}
        schema = {
            "anyOf": [original_schema, {"type": "null"}]
        }
    else:
        # Remove apenas as keywords OpenAPI
        for kw in openapi_keywords:
            schema.pop(kw, None)

    # Processa properties recursivamente
    props = schema.get("properties")
    if isinstance(props, dict):
        new_props: dict[str, Any] = {}
        for prop_name, prop_schema in props.items():
            if isinstance(prop_schema, dict):
                new_props[prop_name] = openapi_schema_to_json_schema(prop_schema)
            else:
                new_props[prop_name] = prop_schema
        schema["properties"] = new_props

    # Processa items de array
    items = schema.get("items")
    if isinstance(items, dict):
        schema["items"] = openapi_schema_to_json_schema(items)
    elif isinstance(items, list):
        # Tuple validation em OpenAPI - items é array de schemas
        schema["items"] = [openapi_schema_to_json_schema(cast(dict[str, Any], item)) for item in items if isinstance(item, dict)]

    # Processa allOf, anyOf, oneOf
    for keyword in ["allOf", "anyOf", "oneOf"]:
        kw_value = schema.get(keyword)
        if isinstance(kw_value, list):
            schema[keyword] = [
                openapi_schema_to_json_schema(cast(dict[str, Any], s)) for s in kw_value if isinstance(s, dict)
            ]

    # Processa additionalProperties
    add_props = schema.get("additionalProperties")
    if isinstance(add_props, dict):
        schema["additionalProperties"] = openapi_schema_to_json_schema(add_props)

    return schema


def extract_response_schema(
    endpoint: dict[str, Any],
    status_code: str = "200",
) -> dict[str, Any] | None:
    """
    Extrai o schema de resposta de um endpoint para um status code.

    ## Parâmetros:
        endpoint: Definição do endpoint normalizada
        status_code: Código de status para extrair schema

    ## Retorna:
        Schema convertido para JSON Schema ou None se não existir

    ## Exemplo:
        >>> endpoint = {"responses": {"200": {"schema": {"type": "object"}}}}
        >>> schema = extract_response_schema(endpoint)
        >>> schema
        {'type': 'object'}
    """
    responses = endpoint.get("responses", {})

    # Tenta o status code específico
    response = responses.get(status_code)

    # Fallback para "2xx" ou "default"
    if not response:
        response = responses.get("2XX") or responses.get("default")

    if not response:
        return None

    # Extrai schema (OpenAPI 3.0: content.application/json.schema)
    schema = response.get("schema")

    if not schema:
        content = response.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema")

    if not schema:
        return None

    # Converte para JSON Schema padrão
    return openapi_schema_to_json_schema(schema)


def generate_schema_assertions(
    spec: dict[str, Any],
    *,
    include_nested_paths: bool = True,
    only_success_responses: bool = True,
) -> list[SchemaAssertion]:
    """
    Gera assertions de JSON Schema para todos os endpoints de uma spec.

    ## Parâmetros:
        spec: Especificação normalizada (output de parse_openapi)
        include_nested_paths: Se True, gera assertions para sub-paths também
        only_success_responses: Se True, só gera para respostas 2xx

    ## Retorna:
        Lista de SchemaAssertion

    ## Exemplo:
        >>> spec = parse_openapi("./api.yaml")
        >>> assertions = generate_schema_assertions(spec)
        >>> assertions[0].endpoint_key
        'GET /users'
        >>> assertions[0].schema
        {'type': 'array', 'items': {'type': 'object', ...}}
    """
    assertions: list[SchemaAssertion] = []
    endpoints = spec.get("endpoints", [])

    for endpoint in endpoints:
        path = endpoint.get("path", "")
        method = endpoint.get("method", "")
        endpoint_key = f"{method} {path}"

        # Extrai schema de resposta
        schema = extract_response_schema(endpoint, "200")

        if not schema:
            # Tenta outros status 2xx
            for status in ["201", "202", "204"]:
                schema = extract_response_schema(endpoint, status)
                if schema:
                    break

        if not schema:
            continue

        # Assertion principal para o body inteiro
        assertions.append(SchemaAssertion(
            endpoint_key=endpoint_key,
            schema=schema,
            path=None,
            operator="valid",
            description=f"Response body for {endpoint_key} should conform to schema",
        ))

        # Gera assertions para sub-paths se habilitado
        if include_nested_paths and schema.get("type") == "object":
            properties = schema.get("properties", {})

            for prop_name, prop_schema in properties.items():
                if prop_schema.get("type") in ("object", "array"):
                    assertions.append(SchemaAssertion(
                        endpoint_key=endpoint_key,
                        schema=prop_schema,
                        path=prop_name,
                        operator="valid",
                        description=f"Field '{prop_name}' in {endpoint_key} should conform to schema",
                    ))

    return assertions


def schema_assertions_to_dict(
    assertions: list[SchemaAssertion],
) -> dict[str, list[dict[str, Any]]]:
    """
    Converte SchemaAssertions para formato de assertions Runner.

    ## Parâmetros:
        assertions: Lista de SchemaAssertion

    ## Retorna:
        Dict mapping endpoint_key -> list of assertions

    ## Exemplo:
        >>> assertions = [SchemaAssertion("GET /users", {"type": "array"}, None, "valid")]
        >>> result = schema_assertions_to_dict(assertions)
        >>> result["GET /users"]
        [{"type": "json_schema", "operator": "valid", "value": {"type": "array"}}]
    """
    result: dict[str, list[dict[str, Any]]] = {}

    for assertion in assertions:
        if assertion.endpoint_key not in result:
            result[assertion.endpoint_key] = []

        assertion_dict: dict[str, Any] = {
            "type": "json_schema",
            "operator": assertion.operator,
            "value": assertion.schema,
        }

        if assertion.path:
            assertion_dict["path"] = assertion.path

        result[assertion.endpoint_key].append(assertion_dict)

    return result


def inject_schema_assertions(
    steps: list[dict[str, Any]],
    spec: dict[str, Any],
    *,
    validate_nested: bool = False,
) -> list[dict[str, Any]]:
    """
    Injeta assertions de JSON Schema em steps existentes.

    ## Parâmetros:
        steps: Lista de steps UTDL
        spec: Especificação OpenAPI para extrair schemas
        validate_nested: Se True, adiciona validação de sub-paths também

    ## Retorna:
        Steps com assertions de json_schema adicionadas

    ## Exemplo:
        >>> steps = [{"id": "get-users", "action": {"type": "http", "method": "GET", "endpoint": "/users"}}]
        >>> spec = parse_openapi("./api.yaml")
        >>> enriched = inject_schema_assertions(steps, spec)
        >>> enriched[0]["assertions"]
        [{"type": "json_schema", "operator": "valid", "value": {...}}]
    """
    import copy

    # Gera assertions baseado na spec
    schema_assertions = generate_schema_assertions(
        spec,
        include_nested_paths=validate_nested,
    )
    assertions_by_endpoint = schema_assertions_to_dict(schema_assertions)

    enriched_steps = []

    for step in steps:
        step_copy = copy.deepcopy(step)

        # Só injeta em steps HTTP
        action = step_copy.get("action", {})
        if action.get("type") != "http":
            enriched_steps.append(step_copy)
            continue

        method = action.get("method", "GET")
        endpoint = action.get("endpoint", "")
        endpoint_key = f"{method} {endpoint}"

        # Inicializa assertions se não existir
        if "assertions" not in step_copy:
            step_copy["assertions"] = []

        # Adiciona schema assertions se existirem para este endpoint
        if endpoint_key in assertions_by_endpoint:
            # Só adiciona se não existir assertion de json_schema
            existing_schema = any(
                a.get("type") == "json_schema"
                for a in step_copy["assertions"]
            )

            if not existing_schema:
                # Adiciona apenas a assertion principal (body inteiro)
                for assertion in assertions_by_endpoint[endpoint_key]:
                    if assertion.get("path") is None or validate_nested:
                        step_copy["assertions"].append(assertion)

        enriched_steps.append(step_copy)

    return enriched_steps


def generate_schema_violation_cases(
    spec: dict[str, Any],
    *,
    max_cases_per_endpoint: int = 5,
) -> list[NegativeCase]:
    """
    Gera casos de teste que violam propositalmente o schema de resposta.

    Útil para testar se a validação de schema está funcionando.

    ## Parâmetros:
        spec: Especificação normalizada
        max_cases_per_endpoint: Número máximo de casos por endpoint

    ## Retorna:
        Lista de NegativeCase para violações de schema

    ## Tipos de violação gerados:
        - wrong_type: Campo com tipo errado
        - missing_required: Campo obrigatório ausente
        - extra_property: Campo não definido no schema (se additionalProperties=false)
        - invalid_enum: Valor fora do enum
        - bound_violation: Valor fora de min/max
    """
    cases: list[NegativeCase] = []
    endpoints = spec.get("endpoints", [])

    for endpoint in endpoints:
        path = endpoint.get("path", "")
        method = endpoint.get("method", "")

        # Pega o schema de resposta
        schema = extract_response_schema(endpoint, "200")
        if not schema:
            continue

        endpoint_cases = 0

        # Gera violações baseadas no schema
        if schema.get("type") == "object":
            properties = schema.get("properties", {})

            for prop_name, prop_schema in properties.items():
                if endpoint_cases >= max_cases_per_endpoint:
                    break

                prop_type = prop_schema.get("type", "string")

                # Caso: tipo errado
                if prop_type == "string":
                    violation_value = 12345  # número em vez de string
                elif prop_type == "integer":
                    violation_value = "not_a_number"
                elif prop_type == "boolean":
                    violation_value = "not_bool"
                elif prop_type == "array":
                    violation_value = "not_array"
                else:
                    violation_value = None

                if violation_value is not None:
                    cases.append(NegativeCase(
                        case_type="schema_type_violation",
                        field_name=prop_name,
                        description=f"Campo '{prop_name}' com tipo errado (espera {prop_type})",
                        invalid_value=violation_value,
                        expected_status=400,
                        endpoint_path=path,
                        endpoint_method=method,
                        expected_status_range="4xx",
                    ))
                    endpoint_cases += 1

                # Caso: violação de enum
                if "enum" in prop_schema:
                    cases.append(NegativeCase(
                        case_type="schema_enum_violation",
                        field_name=prop_name,
                        description=f"Campo '{prop_name}' com valor fora do enum",
                        invalid_value="__INVALID_ENUM_VALUE__",
                        expected_status=400,
                        endpoint_path=path,
                        endpoint_method=method,
                        expected_status_range="4xx",
                    ))
                    endpoint_cases += 1

                # Caso: violação de limites numéricos
                if prop_type in ("integer", "number"):
                    if "minimum" in prop_schema:
                        min_val = prop_schema["minimum"]
                        cases.append(NegativeCase(
                            case_type="schema_bound_violation",
                            field_name=prop_name,
                            description=f"Campo '{prop_name}' abaixo do mínimo ({min_val})",
                            invalid_value=min_val - 1,
                            expected_status=400,
                            endpoint_path=path,
                            endpoint_method=method,
                            expected_status_range="4xx",
                        ))
                        endpoint_cases += 1

    return cases


def negative_cases_to_utdl_steps(
    cases: list[NegativeCase],
    base_body: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Converte casos negativos para steps UTDL prontos para execução.

    ## Parâmetros:
        cases: Lista de NegativeCase gerados
        base_body: Body base válido para modificar (opcional)

    ## Retorna:
        Lista de steps UTDL formatados

    ## Exemplo de step gerado:
        {
            "id": "neg-001",
            "name": "Test missing required field: email",
            "action": {
                "type": "http",
                "method": "POST",
                "endpoint": "/users",
                "body": {"name": "test"}  # sem email
            },
            "expected": {
                "status_code": 400
            }
        }

    O novo formato também pode gerar assertions Runner compatíveis:
        {
            "assertions": [
                {"type": "status_range", "operator": "eq", "value": "4xx"}
            ]
        }
    """
    steps: list[dict[str, Any]] = []
    base_body = base_body or {}

    for i, case in enumerate(cases, 1):
        step_id = f"neg-{i:03d}"

        # Monta o body modificado
        body = build_invalid_body(base_body, case.field_name, case.invalid_value)

        # Construir assertions no formato Runner
        assertions = []

        # Usa status_range se disponível, senão usa status_code específico
        if case.expected_status_range:
            assertions.append({
                "type": "status_range",
                "operator": "eq",
                "value": case.expected_status_range,
            })
        else:
            assertions.append({
                "type": "status_code",
                "operator": "eq",
                "value": case.expected_status,
            })

        step: dict[str, Any] = {
            "id": step_id,
            "name": f"Negative: {case.description}",
            "action": {
                "type": "http",
                "method": case.endpoint_method,
                "endpoint": case.endpoint_path,
            },
            # Novo formato: assertions Runner-compatible
            "assertions": assertions,
            # Mantém expected para backwards compatibility
            "expected": {
                "status_code": case.expected_status,
            },
        }

        # Só adiciona body se não estiver vazio
        if body is not None:
            step["action"]["body"] = body

        steps.append(step)

    return steps


def build_invalid_body(
    base_body: dict[str, Any],
    field_path: str,
    invalid_value: Any,
) -> dict[str, Any] | None:
    """
    ConstrÃ³i um body com um campo invÃ¡lido.

    ## ParÃ¢metros:
        base_body: Body base vÃ¡lido
        field_path: Caminho do campo (ex: "user.email" ou "items[].name")
        invalid_value: Valor invÃ¡lido ou "__OMIT__" para remover

    ## Retorna:
        Body modificado ou None se body deve ser omitido
    """
    import copy

    # Copia para nÃ£o modificar original
    body = copy.deepcopy(base_body)

    # Caso especial: omitir campo
    if invalid_value == "__OMIT__":
        remove_field(body, field_path)
        return body

    # Define valor invÃ¡lido
    set_field(body, field_path, invalid_value)
    return body


def remove_field(obj: dict[str, Any], path: str) -> None:
    """Remove um campo de um objeto pelo path."""
    parts = path.replace("[]", "").split(".")
    current = obj

    for part in parts[:-1]:
        if part in current:
            current = current[part]
        else:
            return  # Campo nÃ£o existe, nada a remover

    # Remove o Ãºltimo campo
    last_part = parts[-1]
    if last_part in current:
        del current[last_part]


def set_field(obj: dict[str, Any], path: str, value: Any) -> None:
    """Define um campo em um objeto pelo path."""
    parts = path.replace("[]", "").split(".")
    current = obj

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    # Define o Ãºltimo campo
    current[parts[-1]] = value


# =============================================================================
# FUNÃ‡ÃƒO DE CONVENIÃŠNCIA
# =============================================================================


def analyze_and_generate(
    spec: dict[str, Any],
    *,
    as_utdl: bool = True,
    base_body: dict[str, Any] | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]] | NegativeTestResult:
    """
    FunÃ§Ã£o de conveniÃªncia que analisa spec e gera casos negativos.

    ## ParÃ¢metros:
        spec: EspecificaÃ§Ã£o normalizada
        as_utdl: Se True, retorna steps UTDL. Se False, retorna NegativeTestResult
        base_body: Body base para modificar (usado quando as_utdl=True)
        **kwargs: Argumentos adicionais para generate_negative_cases

    ## Retorna:
        Lista de steps UTDL ou NegativeTestResult

    ## Exemplo:
        >>> spec = parse_openapi("./api.yaml")
        >>> steps = analyze_and_generate(spec, as_utdl=True)
        >>> # steps prontos para adicionar ao plano
    """
    result = generate_negative_cases(spec, **kwargs)

    if as_utdl:
        return negative_cases_to_utdl_steps(result.cases, base_body)

    return result
