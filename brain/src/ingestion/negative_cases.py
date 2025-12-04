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
        description: DescriÃ§Ã£o legÃ­vel do teste
        invalid_value: Valor invÃ¡lido a ser enviado
        expected_status: CÃ³digo HTTP esperado (400, 422, etc.)
        endpoint_path: Path do endpoint (ex: /users)
        endpoint_method: MÃ©todo HTTP (POST, PUT, etc.)
    """

    case_type: str
    field_name: str
    description: str
    invalid_value: Any
    expected_status: int
    endpoint_path: str
    endpoint_method: str


@dataclass
class NegativeTestResult:
    """
    Resultado da anÃ¡lise de uma spec para casos negativos.

    ## Atributos:
        cases: Lista de casos negativos gerados
        endpoints_analyzed: NÃºmero de endpoints analisados
        fields_analyzed: NÃºmero de campos analisados
    """

    cases: list[NegativeCase] = field(default_factory=lambda: [])
    endpoints_analyzed: int = 0
    fields_analyzed: int = 0


# =============================================================================
# GERADORES DE VALORES INVÃLIDOS
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
        invalid_values.append(("invalid_format", "not-a-uri", "URI invÃ¡lida"))
        invalid_values.append(("invalid_format", "ftp://", "URI incompleta"))

    # Null (se nÃ£o permitido)
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

    ## ParÃ¢metros:
        spec: EspecificaÃ§Ã£o normalizada (output de parse_openapi)
        include_types: Tipos de casos a incluir (None = todos)
            OpÃ§Ãµes: missing_required, invalid_type, limit_exceeded,
                    invalid_format, empty_value, null_value
        exclude_endpoints: Paths de endpoints a ignorar
        max_cases_per_field: MÃ¡ximo de casos por campo (default: 3)

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

        # Gera casos para campos obrigatÃ³rios ausentes
        if "missing_required" in include_types:
            required_fields = [f for f in fields if f["required"]]
            for field_info in required_fields:
                case = NegativeCase(
                    case_type="missing_required",
                    field_name=field_info["full_path"],
                    description=f"campo obrigatÃ³rio '{field_info['full_path']}' ausente",
                    invalid_value="__OMIT__",  # Marcador especial para omitir o campo
                    expected_status=400,
                    endpoint_path=path,
                    endpoint_method=method,
                )
                result.cases.append(case)

        # Gera casos para cada campo
        for field_info in fields:
            invalid_values = generate_invalid_values_for_type(
                field_info["type"],
                field_info.get("format"),
                field_info.get("constraints"),
            )

            # Limita nÃºmero de casos por campo
            cases_added = 0

            for case_type, invalid_value, description in invalid_values:
                if case_type not in include_types:
                    continue

                if cases_added >= max_cases_per_field:
                    break

                case = NegativeCase(
                    case_type=case_type,
                    field_name=field_info["full_path"],
                    description=f"{field_info['full_path']}: {description}",
                    invalid_value=invalid_value,
                    expected_status=400 if case_type != "invalid_format" else 422,
                    endpoint_path=path,
                    endpoint_method=method,
                )
                result.cases.append(case)
                cases_added += 1

    return result


def negative_cases_to_utdl_steps(
    cases: list[NegativeCase],
    base_body: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Converte casos negativos para steps UTDL prontos para execuÃ§Ã£o.

    ## ParÃ¢metros:
        cases: Lista de NegativeCase gerados
        base_body: Body base vÃ¡lido para modificar (opcional)

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
    """
    steps: list[dict[str, Any]] = []
    base_body = base_body or {}

    for i, case in enumerate(cases, 1):
        step_id = f"neg-{i:03d}"

        # Monta o body modificado
        body = build_invalid_body(base_body, case.field_name, case.invalid_value)

        step: dict[str, Any] = {
            "id": step_id,
            "name": f"Negative: {case.description}",
            "action": {
                "type": "http",
                "method": case.endpoint_method,
                "endpoint": case.endpoint_path,
            },
            "expected": {
                "status_code": case.expected_status,
            },
        }

        # SÃ³ adiciona body se nÃ£o estiver vazio
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
