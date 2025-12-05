"""
Testes para o mÃ³dulo de geraÃ§Ã£o de casos negativos.

Testa:
- GeraÃ§Ã£o de valores invÃ¡lidos por tipo
- ExtraÃ§Ã£o de campos de schemas
- GeraÃ§Ã£o de casos negativos completos
- ConversÃ£o para steps UTDL
"""

import sys
from pathlib import Path
from typing import Any

# Adiciona o diretório brain ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.negative_cases import (
    NegativeCase,
    NegativeTestResult,
    RobustnessCase,
    LatencySLA,
    analyze_and_generate,
    generate_negative_cases,
    generate_robustness_cases,
    generate_latency_assertions,
    inject_latency_assertions,
    negative_cases_to_utdl_steps,
    robustness_cases_to_utdl_steps,
)

# Funções auxiliares públicas para testes detalhados
from src.ingestion.negative_cases import (
    build_invalid_body,
    extract_fields_from_schema,
    generate_invalid_values_for_type,
    remove_field,
    set_field,
)


class TestGenerateInvalidValues:
    """Testes para generate_invalid_values_for_type."""

    def test_string_invalid_values(self) -> None:
        """Gera valores invÃ¡lidos para tipo string."""
        values = generate_invalid_values_for_type("string")

        # Deve incluir tipos errados
        case_types = [v[0] for v in values]
        assert "invalid_type" in case_types
        assert "null_value" in case_types

    def test_string_with_length_constraints(self) -> None:
        """Gera valores invÃ¡lidos respeitando constraints de length."""
        values = generate_invalid_values_for_type(
            "string",
            constraints={"minLength": 5, "maxLength": 10},
        )

        # Deve incluir string vazia e muito longa
        case_types = [v[0] for v in values]
        assert "empty_value" in case_types
        assert "limit_exceeded" in case_types

        # Verifica que string longa tem mais de 10 chars
        long_value = [v for v in values if v[0] == "limit_exceeded" and "chars" in v[2] and "max" in v[2]]
        assert len(long_value) > 0
        assert len(long_value[0][1]) > 10

    def test_integer_invalid_values(self) -> None:
        """Gera valores invÃ¡lidos para tipo integer."""
        values = generate_invalid_values_for_type("integer")

        case_types = [v[0] for v in values]
        assert "invalid_type" in case_types

        # Verifica que inclui string e float como tipos errados
        invalid_vals = [v[1] for v in values if v[0] == "invalid_type"]
        assert "not_a_number" in invalid_vals
        assert 3.14 in invalid_vals

    def test_integer_with_min_max(self) -> None:
        """Gera valores invÃ¡lidos respeitando min/max."""
        values = generate_invalid_values_for_type(
            "integer",
            constraints={"minimum": 0, "maximum": 100},
        )

        case_types = [v[0] for v in values]
        assert "limit_exceeded" in case_types

        # Deve ter valor abaixo de 0 e acima de 100
        limit_values = [v for v in values if v[0] == "limit_exceeded"]
        nums = [v[1] for v in limit_values]
        assert any(n < 0 for n in nums)
        assert any(n > 100 for n in nums)

    def test_boolean_invalid_values(self) -> None:
        """Gera valores invÃ¡lidos para tipo boolean."""
        values = generate_invalid_values_for_type("boolean")

        invalid_vals = [v[1] for v in values if v[0] == "invalid_type"]
        assert "true" in invalid_vals  # String "true"
        assert 1 in invalid_vals  # NÃºmero 1

    def test_array_invalid_values(self) -> None:
        """Gera valores invÃ¡lidos para tipo array."""
        values = generate_invalid_values_for_type("array")

        case_types = [v[0] for v in values]
        assert "invalid_type" in case_types

    def test_email_format_invalid_values(self) -> None:
        """Gera valores invÃ¡lidos para formato email."""
        values = generate_invalid_values_for_type("string", field_format="email")

        case_types = [v[0] for v in values]
        assert "invalid_format" in case_types

        # Verifica emails invÃ¡lidos
        invalid_emails = [v[1] for v in values if v[0] == "invalid_format"]
        assert "not-an-email" in invalid_emails

    def test_uuid_format_invalid_values(self) -> None:
        """Gera valores invÃ¡lidos para formato uuid."""
        values = generate_invalid_values_for_type("string", field_format="uuid")

        invalid_uuids = [v[1] for v in values if v[0] == "invalid_format"]
        assert "not-a-uuid" in invalid_uuids

    def test_nullable_constraint(self) -> None:
        """NÃ£o gera null_value se campo Ã© nullable."""
        values_nullable = generate_invalid_values_for_type(
            "string",
            constraints={"nullable": True},
        )
        values_not_nullable = generate_invalid_values_for_type(
            "string",
            constraints={"nullable": False},
        )

        types_nullable = [v[0] for v in values_nullable]
        types_not_nullable = [v[0] for v in values_not_nullable]

        assert "null_value" not in types_nullable
        assert "null_value" in types_not_nullable

    def test_enum_invalid_values(self) -> None:
        """Gera valores inválidos para campos com enum."""
        values = generate_invalid_values_for_type(
            "string",
            constraints={"enum": ["active", "inactive", "pending"]},
        )

        case_types = [v[0] for v in values]
        assert "invalid_enum" in case_types

        # Verifica que inclui valor fora do enum
        invalid_enums = [v for v in values if v[0] == "invalid_enum"]
        invalid_vals = [v[1] for v in invalid_enums]

        assert "__INVALID_ENUM_VALUE__" in invalid_vals
        assert "" in invalid_vals  # String vazia
        assert 99999 in invalid_vals  # Número (tipo errado)

    def test_enum_case_sensitivity(self) -> None:
        """Gera variações de case para valores enum."""
        values = generate_invalid_values_for_type(
            "string",
            constraints={"enum": ["Active", "Inactive"]},
        )

        invalid_enums = [v for v in values if v[0] == "invalid_enum"]
        invalid_vals = [v[1] for v in invalid_enums]

        # Deve incluir lowercase do primeiro valor
        assert "active" in invalid_vals

    def test_boundary_violation_exclusive(self) -> None:
        """Gera violações de boundary para exclusiveMinimum/Maximum."""
        values = generate_invalid_values_for_type(
            "integer",
            constraints={
                "minimum": 0,
                "maximum": 100,
                "exclusiveMinimum": True,
                "exclusiveMaximum": True,
            },
        )

        case_types = [v[0] for v in values]
        assert "boundary_violation" in case_types

        # Valores exatamente nos limites exclusivos
        boundary_vals = [v for v in values if v[0] == "boundary_violation"]
        vals = [v[1] for v in boundary_vals]
        assert 0 in vals  # Igual ao mínimo exclusivo
        assert 100 in vals  # Igual ao máximo exclusivo


class TestExtractFieldsFromSchema:
    """Testes para extract_fields_from_schema."""

    def test_simple_schema(self) -> None:
        """Extrai campos de schema simples."""
        schema: dict[str, Any] = {
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "age": {"type": "integer"},
            },
        }

        fields = extract_fields_from_schema(schema)

        assert len(fields) == 3
        names = [f["name"] for f in fields]
        assert "name" in names
        assert "email" in names
        assert "age" in names

        # Verifica required
        email_field = [f for f in fields if f["name"] == "email"][0]
        assert email_field["required"] is True
        assert email_field["format"] == "email"

        age_field = [f for f in fields if f["name"] == "age"][0]
        assert age_field["required"] is False

    def test_nested_schema(self) -> None:
        """Extrai campos de schema com objetos aninhados."""
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "address": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }

        fields = extract_fields_from_schema(schema)

        paths = [f["full_path"] for f in fields]
        assert "user" in paths
        assert "user.name" in paths
        assert "user.address" in paths
        assert "user.address.city" in paths

    def test_array_with_object_items(self) -> None:
        """Extrai campos de arrays com items objeto."""
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    },
                },
            },
        }

        fields = extract_fields_from_schema(schema)

        paths = [f["full_path"] for f in fields]
        assert "items" in paths
        assert "items[].id" in paths
        assert "items[].name" in paths

    def test_constraints_extraction(self) -> None:
        """Extrai constraints de campos."""
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 20,
                },
                "age": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 150,
                },
            },
        }

        fields = extract_fields_from_schema(schema)

        username_field = [f for f in fields if f["name"] == "username"][0]
        assert username_field["constraints"]["minLength"] == 3
        assert username_field["constraints"]["maxLength"] == 20

        age_field = [f for f in fields if f["name"] == "age"][0]
        assert age_field["constraints"]["minimum"] == 0
        assert age_field["constraints"]["maximum"] == 150


class TestGenerateNegativeCases:
    """Testes para generate_negative_cases."""

    def test_generates_cases_for_post_endpoint(self) -> None:
        """Gera casos negativos para endpoint POST com body."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "request_body": {
                        "required": True,
                        "schema": {
                            "type": "object",
                            "required": ["name", "email"],
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string", "format": "email"},
                            },
                        },
                    },
                },
            ],
        }

        result = generate_negative_cases(spec)

        assert result.endpoints_analyzed == 1
        assert result.fields_analyzed == 2
        assert len(result.cases) > 0

        # Deve ter casos missing_required
        missing_cases = [c for c in result.cases if c.case_type == "missing_required"]
        assert len(missing_cases) == 2  # name e email sÃ£o required

    def test_ignores_get_endpoints(self) -> None:
        """NÃ£o gera casos para endpoints GET (sem body)."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "GET",
                    "request_body": None,
                },
            ],
        }

        result = generate_negative_cases(spec)

        assert result.endpoints_analyzed == 0
        assert len(result.cases) == 0

    def test_respects_exclude_endpoints(self) -> None:
        """Respeita lista de endpoints excluÃ­dos."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "request_body": {
                        "schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        },
                    },
                },
                {
                    "path": "/admin",
                    "method": "POST",
                    "request_body": {
                        "schema": {
                            "type": "object",
                            "properties": {"key": {"type": "string"}},
                        },
                    },
                },
            ],
        }

        result = generate_negative_cases(spec, exclude_endpoints=["/admin"])

        assert result.endpoints_analyzed == 1
        assert all(c.endpoint_path != "/admin" for c in result.cases)

    def test_respects_include_types(self) -> None:
        """Respeita lista de tipos de casos a incluir."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "request_body": {
                        "schema": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {"name": {"type": "string"}},
                        },
                    },
                },
            ],
        }

        result = generate_negative_cases(spec, include_types=["missing_required"])

        assert all(c.case_type == "missing_required" for c in result.cases)

    def test_respects_max_cases_per_field(self) -> None:
        """Respeita limite de casos por campo."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "request_body": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 100,
                                },
                            },
                        },
                    },
                },
            ],
        }

        result = generate_negative_cases(spec, max_cases_per_field=1)

        # Conta casos para o campo name (excluindo missing_required)
        name_cases = [c for c in result.cases if c.field_name == "name" and c.case_type != "missing_required"]
        assert len(name_cases) <= 1


class TestNegativeCasesToUtdlSteps:
    """Testes para negative_cases_to_utdl_steps."""

    def test_converts_cases_to_steps(self) -> None:
        """Converte casos negativos para steps UTDL."""
        cases = [
            NegativeCase(
                case_type="missing_required",
                field_name="email",
                description="campo obrigatÃ³rio 'email' ausente",
                invalid_value="__OMIT__",
                expected_status=400,
                endpoint_path="/users",
                endpoint_method="POST",
            ),
            NegativeCase(
                case_type="invalid_type",
                field_name="age",
                description="age: string em vez de integer",
                invalid_value="not_a_number",
                expected_status=400,
                endpoint_path="/users",
                endpoint_method="POST",
            ),
        ]

        steps = negative_cases_to_utdl_steps(cases)

        assert len(steps) == 2

        # Verifica estrutura do primeiro step
        step1 = steps[0]
        assert step1["id"] == "neg-001"
        assert "Negative:" in step1["name"]
        assert step1["action"]["type"] == "http"
        assert step1["action"]["method"] == "POST"
        assert step1["action"]["endpoint"] == "/users"
        assert step1["expected"]["status_code"] == 400

    def test_uses_base_body(self) -> None:
        """Usa body base para modificar."""
        cases = [
            NegativeCase(
                case_type="invalid_type",
                field_name="email",
                description="email: nÃºmero em vez de string",
                invalid_value=12345,
                expected_status=400,
                endpoint_path="/users",
                endpoint_method="POST",
            ),
        ]

        base_body = {"name": "Test User", "email": "test@example.com"}
        steps = negative_cases_to_utdl_steps(cases, base_body)

        assert steps[0]["action"]["body"]["name"] == "Test User"
        assert steps[0]["action"]["body"]["email"] == 12345

    def test_generates_status_range_assertions(self) -> None:
        """Gera assertions com status_range quando especificado."""
        cases = [
            NegativeCase(
                case_type="missing_required",
                field_name="email",
                description="campo obrigatório 'email' ausente",
                invalid_value="__OMIT__",
                expected_status=400,
                endpoint_path="/users",
                endpoint_method="POST",
                expected_status_range="4xx",  # Range de status 4xx
            ),
        ]

        steps = negative_cases_to_utdl_steps(cases)

        assert len(steps) == 1
        step = steps[0]

        # Deve ter assertions no novo formato
        assert "assertions" in step
        assertions = step["assertions"]
        assert len(assertions) == 1

        # Assertion deve ser status_range
        assertion = assertions[0]
        assert assertion["type"] == "status_range"
        assert assertion["operator"] == "eq"
        assert assertion["value"] == "4xx"

        # Também deve manter expected para backwards compatibility
        assert step["expected"]["status_code"] == 400

    def test_fallback_to_status_code_when_no_range(self) -> None:
        """Usa status_code específico quando range não especificado."""
        cases = [
            NegativeCase(
                case_type="invalid_type",
                field_name="age",
                description="age: string em vez de integer",
                invalid_value="not_a_number",
                expected_status=422,
                endpoint_path="/users",
                endpoint_method="POST",
                # Sem expected_status_range
            ),
        ]

        steps = negative_cases_to_utdl_steps(cases)

        step = steps[0]
        assertions = step["assertions"]

        # Deve usar status_code específico
        assertion = assertions[0]
        assert assertion["type"] == "status_code"
        assert assertion["operator"] == "eq"
        assert assertion["value"] == 422


class TestBuildInvalidBody:
    """Testes para build_invalid_body."""

    def testset_field_simple(self) -> None:
        """Define campo simples."""
        body: dict[str, Any] = {"name": "test", "email": "test@example.com"}
        result = build_invalid_body(body, "email", "invalid-email")

        assert result is not None
        assert result["name"] == "test"
        assert result["email"] == "invalid-email"

    def test_omit_field(self) -> None:
        """Remove campo com valor __OMIT__."""
        body: dict[str, Any] = {"name": "test", "email": "test@example.com"}
        result = build_invalid_body(body, "email", "__OMIT__")

        assert result is not None
        assert result["name"] == "test"
        assert "email" not in result

    def test_set_nested_field(self) -> None:
        """Define campo aninhado."""
        body: dict[str, Any] = {"user": {"name": "test"}}
        result = build_invalid_body(body, "user.name", 12345)

        assert result is not None
        assert result["user"]["name"] == 12345


class TestHelperFunctions:
    """Testes para funÃ§Ãµes auxiliares."""

    def testremove_field_simple(self) -> None:
        """Remove campo simples."""
        obj: dict[str, Any] = {"a": 1, "b": 2}
        remove_field(obj, "a")
        assert "a" not in obj
        assert "b" in obj

    def testremove_field_nested(self) -> None:
        """Remove campo aninhado."""
        obj: dict[str, Any] = {"user": {"name": "test", "email": "test@test.com"}}
        remove_field(obj, "user.email")
        assert "name" in obj["user"]
        assert "email" not in obj["user"]

    def testremove_field_nonexistent(self) -> None:
        """NÃ£o falha ao remover campo inexistente."""
        obj: dict[str, Any] = {"a": 1}
        remove_field(obj, "b")  # NÃ£o deve levantar exceÃ§Ã£o
        assert obj == {"a": 1}

    def testset_field_simple(self) -> None:
        """Define campo simples."""
        obj: dict[str, Any] = {}
        set_field(obj, "name", "test")
        assert obj["name"] == "test"

    def testset_field_nested_creates_path(self) -> None:
        """Define campo aninhado criando caminho."""
        obj: dict[str, Any] = {}
        set_field(obj, "user.profile.name", "test")
        assert obj["user"]["profile"]["name"] == "test"


class TestAnalyzeAndGenerate:
    """Testes para analyze_and_generate."""

    def test_returns_utdl_by_default(self) -> None:
        """Retorna steps UTDL por padrÃ£o."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/test",
                    "method": "POST",
                    "request_body": {
                        "schema": {
                            "type": "object",
                            "required": ["field"],
                            "properties": {"field": {"type": "string"}},
                        },
                    },
                },
            ],
        }

        result = analyze_and_generate(spec)

        assert isinstance(result, list)
        assert len(result) > 0
        assert "id" in result[0]
        assert "action" in result[0]

    def test_returns_result_when_as_utdl_false(self) -> None:
        """Retorna NegativeTestResult quando as_utdl=False."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/test",
                    "method": "POST",
                    "request_body": {
                        "schema": {
                            "type": "object",
                            "properties": {"field": {"type": "string"}},
                        },
                    },
                },
            ],
        }

        result = analyze_and_generate(spec, as_utdl=False)

        assert isinstance(result, NegativeTestResult)
        assert hasattr(result, "cases")
        assert hasattr(result, "endpoints_analyzed")


class TestRobustnessCases:
    """Testes para geração de casos de robustez."""

    def test_generates_invalid_header_cases(self) -> None:
        """Gera casos com headers inválidos."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "request_body": {
                        "schema": {"type": "object"},
                    },
                },
            ],
        }

        cases = generate_robustness_cases(spec, include_types=["invalid_header"])

        assert len(cases) >= 1
        assert all(c.case_type == "invalid_header" for c in cases)
        # Deve ter Content-Type inválido
        assert any("Content-Type" in str(c.headers) for c in cases)

    def test_generates_extra_field_cases(self) -> None:
        """Gera casos com campos extras não definidos."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "request_body": {
                        "schema": {"type": "object"},
                    },
                },
            ],
        }

        cases = generate_robustness_cases(spec, include_types=["extra_field"])

        assert len(cases) >= 1
        assert all(c.case_type == "extra_field" for c in cases)
        # Deve ter __proto__ para teste de prototype pollution
        assert any("__proto__" in str(c.body) for c in cases)

    def test_generates_malformed_json_cases(self) -> None:
        """Gera casos com JSON malformado."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/data",
                    "method": "PUT",
                    "request_body": {
                        "schema": {"type": "object"},
                    },
                },
            ],
        }

        cases = generate_robustness_cases(spec, include_types=["malformed_json"])

        assert len(cases) >= 1
        assert all(c.case_type == "malformed_json" for c in cases)
        # JSON truncado deve estar nos casos
        assert any("truncado" in c.description.lower() for c in cases)

    def test_generates_oversized_value_cases(self) -> None:
        """Gera casos com valores muito grandes."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/upload",
                    "method": "POST",
                    "request_body": {
                        "schema": {"type": "object"},
                    },
                },
            ],
        }

        cases = generate_robustness_cases(spec, include_types=["oversized_value"])

        assert len(cases) >= 1
        assert all(c.case_type == "oversized_value" for c in cases)
        # Deve ter string de 100KB
        assert any("100KB" in c.description for c in cases)

    def test_skips_get_endpoints(self) -> None:
        """Não gera casos para endpoints GET."""
        spec: dict[str, Any] = {
            "endpoints": [
                {"path": "/users", "method": "GET"},
                {"path": "/users/{id}", "method": "GET"},
            ],
        }

        cases = generate_robustness_cases(spec)

        assert len(cases) == 0

    def test_robustness_to_utdl_steps(self) -> None:
        """Converte casos de robustez para steps UTDL."""
        cases = [
            RobustnessCase(
                case_type="invalid_header",
                description="POST /users: Content-Type inválido",
                endpoint_path="/users",
                endpoint_method="POST",
                headers={"Content-Type": "text/plain"},
                body='{"test": "data"}',
                expected_status_range="4xx",
            ),
        ]

        steps = robustness_cases_to_utdl_steps(cases)

        assert len(steps) == 1
        step = steps[0]
        assert step["id"] == "robust-001"
        assert "Robustness:" in step["name"]
        assert step["action"]["method"] == "POST"
        assert step["action"]["endpoint"] == "/users"
        assert step["action"]["headers"]["Content-Type"] == "text/plain"
        # Deve ter assertion de status_range
        assert step["assertions"][0]["type"] == "status_range"
        assert step["assertions"][0]["value"] == "4xx"

    def test_respects_exclude_endpoints(self) -> None:
        """Respeita lista de endpoints excluídos."""
        spec: dict[str, Any] = {
            "endpoints": [
                {
                    "path": "/internal/health",
                    "method": "POST",
                    "request_body": {"schema": {"type": "object"}},
                },
                {
                    "path": "/api/users",
                    "method": "POST",
                    "request_body": {"schema": {"type": "object"}},
                },
            ],
        }

        cases = generate_robustness_cases(
            spec,
            exclude_endpoints=["/internal/health"],
            include_types=["empty_body"],
        )

        # Só deve ter casos do /api/users
        assert all(c.endpoint_path == "/api/users" for c in cases)


class TestLatencyAssertions:
    """Testes para geração de assertions de latência."""

    def test_generate_latency_assertions_for_get(self) -> None:
        """Gera assertions de latência para endpoints GET."""
        spec: dict[str, Any] = {
            "endpoints": [
                {"path": "/users", "method": "GET"},
                {"path": "/users/{id}", "method": "GET"},
            ],
        }

        assertions = generate_latency_assertions(spec)

        # GET deve ter latência mais baixa (200ms)
        assert "GET /users" in assertions
        assert assertions["GET /users"]["type"] == "latency"
        assert assertions["GET /users"]["operator"] == "lt"
        assert assertions["GET /users"]["value"] == 200

    def test_generate_latency_assertions_for_post(self) -> None:
        """Gera assertions de latência para endpoints POST."""
        spec: dict[str, Any] = {
            "endpoints": [
                {"path": "/users", "method": "POST"},
            ],
        }

        assertions = generate_latency_assertions(spec)

        # POST deve ter latência moderada (500ms)
        assert "POST /users" in assertions
        assert assertions["POST /users"]["value"] == 500

    def test_auth_endpoints_have_higher_latency(self) -> None:
        """Endpoints de autenticação têm latência mais alta permitida."""
        spec: dict[str, Any] = {
            "endpoints": [
                {"path": "/auth/login", "method": "POST"},
                {"path": "/auth/token", "method": "POST"},
            ],
        }

        assertions = generate_latency_assertions(spec)

        # Auth deve permitir 1000ms
        assert "POST /auth/login" in assertions
        assert assertions["POST /auth/login"]["value"] == 1000

    def test_custom_slas(self) -> None:
        """Usa SLAs customizados."""
        spec: dict[str, Any] = {
            "endpoints": [
                {"path": "/fast", "method": "GET"},
            ],
        }

        custom_slas = [
            LatencySLA(
                endpoint_pattern=r"^GET /fast$",
                max_latency_ms=50,
                description="Endpoint muito rápido",
            ),
        ]

        assertions = generate_latency_assertions(spec, slas=custom_slas)

        assert assertions["GET /fast"]["value"] == 50

    def test_default_latency_when_no_match(self) -> None:
        """Usa latência padrão quando nenhum SLA corresponde."""
        spec: dict[str, Any] = {
            "endpoints": [
                {"path": "/custom", "method": "OPTIONS"},
            ],
        }

        assertions = generate_latency_assertions(
            spec,
            slas=[],  # Sem SLAs
            default_max_latency_ms=300,
        )

        assert assertions["OPTIONS /custom"]["value"] == 300

    def test_inject_latency_into_steps(self) -> None:
        """Injeta assertions de latência em steps existentes."""
        steps = [
            {
                "id": "step-1",
                "name": "Get users",
                "action": {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/users",
                },
            },
        ]

        enriched = inject_latency_assertions(steps)

        assert len(enriched) == 1
        assert "assertions" in enriched[0]
        latency_assertions = [
            a for a in enriched[0]["assertions"] if a["type"] == "latency"
        ]
        assert len(latency_assertions) == 1
        assert latency_assertions[0]["operator"] == "lt"
        assert latency_assertions[0]["value"] == 200  # GET default

    def test_inject_preserves_existing_assertions(self) -> None:
        """Mantém assertions existentes ao injetar latência."""
        steps = [
            {
                "id": "step-1",
                "action": {
                    "type": "http",
                    "method": "POST",
                    "endpoint": "/users",
                },
                "assertions": [
                    {"type": "status_code", "operator": "eq", "value": 201},
                ],
            },
        ]

        enriched = inject_latency_assertions(steps)

        # Deve ter 2 assertions: status_code original + latency
        assert len(enriched[0]["assertions"]) == 2
        types = [a["type"] for a in enriched[0]["assertions"]]
        assert "status_code" in types
        assert "latency" in types

    def test_does_not_duplicate_latency(self) -> None:
        """Não duplica assertion de latência se já existir."""
        steps = [
            {
                "id": "step-1",
                "action": {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/users",
                },
                "assertions": [
                    {"type": "latency", "operator": "lt", "value": 100},
                ],
            },
        ]

        enriched = inject_latency_assertions(steps)

        # Deve manter apenas 1 assertion de latência
        latency_assertions = [
            a for a in enriched[0]["assertions"] if a["type"] == "latency"
        ]
        assert len(latency_assertions) == 1
        assert latency_assertions[0]["value"] == 100  # Original, não sobrescrito

    def test_skips_non_http_steps(self) -> None:
        """Ignora steps que não são HTTP."""
        steps = [
            {
                "id": "wait-1",
                "action": {"type": "wait", "duration_ms": 1000},
            },
        ]

        enriched = inject_latency_assertions(steps)

        # Não deve adicionar assertions
        assert "assertions" not in enriched[0]


# =============================================================================
# TESTES: JSON SCHEMA ASSERTIONS
# =============================================================================

from src.ingestion.negative_cases import (
    SchemaAssertion,
    openapi_schema_to_json_schema,
    extract_response_schema,
    generate_schema_assertions,
    schema_assertions_to_dict,
    inject_schema_assertions,
    generate_schema_violation_cases,
)


class TestOpenAPISchemaConversion:
    """Testes para openapi_schema_to_json_schema."""

    def test_simple_object_schema(self) -> None:
        """Converte schema de objeto simples."""
        openapi_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }

        json_schema = openapi_schema_to_json_schema(openapi_schema)

        assert json_schema["type"] == "object"
        assert "name" in json_schema["properties"]
        assert "required" in json_schema

    def test_nullable_field_conversion(self) -> None:
        """Converte campo nullable para anyOf."""
        openapi_schema = {
            "type": "string",
            "nullable": True,
        }

        json_schema = openapi_schema_to_json_schema(openapi_schema)

        # Deve usar anyOf para nullable
        assert "anyOf" in json_schema
        types = [s.get("type") for s in json_schema["anyOf"]]
        assert "string" in types
        assert "null" in types

    def test_removes_openapi_keywords(self) -> None:
        """Remove keywords específicas do OpenAPI."""
        openapi_schema = {
            "type": "string",
            "readOnly": True,
            "deprecated": True,
            "example": "test",
            "externalDocs": {"url": "http://example.com"},
        }

        json_schema = openapi_schema_to_json_schema(openapi_schema)

        assert "readOnly" not in json_schema
        assert "deprecated" not in json_schema
        assert "example" not in json_schema
        assert "externalDocs" not in json_schema
        assert json_schema["type"] == "string"

    def test_nested_object_conversion(self) -> None:
        """Converte schemas aninhados recursivamente."""
        openapi_schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "id": {"type": "integer", "readOnly": True},
                    },
                },
            },
        }

        json_schema = openapi_schema_to_json_schema(openapi_schema)

        # Propriedade aninhada deve ter anyOf por causa do nullable
        user_schema = json_schema["properties"]["user"]
        assert "anyOf" in user_schema

    def test_array_items_conversion(self) -> None:
        """Converte items de array."""
        openapi_schema = {
            "type": "array",
            "items": {
                "type": "string",
                "nullable": True,
            },
        }

        json_schema = openapi_schema_to_json_schema(openapi_schema)

        assert json_schema["type"] == "array"
        assert "anyOf" in json_schema["items"]

    def test_allof_conversion(self) -> None:
        """Converte allOf com schemas."""
        openapi_schema = {
            "allOf": [
                {"type": "object", "nullable": True},
                {"properties": {"extra": {"type": "string"}}},
            ],
        }

        json_schema = openapi_schema_to_json_schema(openapi_schema)

        assert "allOf" in json_schema
        # Primeiro schema deve ter anyOf por causa do nullable
        assert "anyOf" in json_schema["allOf"][0]


class TestExtractResponseSchema:
    """Testes para extract_response_schema."""

    def test_extracts_200_schema(self) -> None:
        """Extrai schema de resposta 200."""
        endpoint = {
            "responses": {
                "200": {
                    "schema": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}},
                    },
                },
            },
        }

        schema = extract_response_schema(endpoint, "200")

        assert schema is not None
        assert schema["type"] == "object"

    def test_extracts_openapi3_content_schema(self) -> None:
        """Extrai schema no formato OpenAPI 3.0."""
        endpoint = {
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }

        schema = extract_response_schema(endpoint)

        assert schema is not None
        assert schema["type"] == "array"

    def test_fallback_to_default_response(self) -> None:
        """Usa resposta default se status específico não existir."""
        endpoint = {
            "responses": {
                "default": {
                    "schema": {"type": "object"},
                },
            },
        }

        schema = extract_response_schema(endpoint, "404")

        assert schema is not None
        assert schema["type"] == "object"

    def test_returns_none_for_missing_schema(self) -> None:
        """Retorna None se não houver schema."""
        endpoint = {
            "responses": {
                "200": {
                    "description": "Success",
                },
            },
        }

        schema = extract_response_schema(endpoint)

        assert schema is None

    def test_returns_none_for_empty_responses(self) -> None:
        """Retorna None para respostas vazias."""
        endpoint = {"responses": {}}

        schema = extract_response_schema(endpoint)

        assert schema is None


class TestGenerateSchemaAssertions:
    """Testes para generate_schema_assertions."""

    def test_generates_assertions_for_endpoints(self) -> None:
        """Gera assertions para endpoints com schemas."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "GET",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                    },
                },
            ],
        }

        assertions = generate_schema_assertions(spec)

        assert len(assertions) >= 1
        assert assertions[0].endpoint_key == "GET /users"
        assert assertions[0].schema["type"] == "array"
        assert assertions[0].operator == "valid"

    def test_generates_nested_path_assertions(self) -> None:
        """Gera assertions para sub-paths quando habilitado."""
        spec = {
            "endpoints": [
                {
                    "path": "/users/{id}",
                    "method": "GET",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "object",
                                        "properties": {"id": {"type": "integer"}},
                                    },
                                    "meta": {
                                        "type": "object",
                                    },
                                },
                            },
                        },
                    },
                },
            ],
        }

        assertions = generate_schema_assertions(spec, include_nested_paths=True)

        # Deve ter assertion para o body e para sub-paths
        paths = [a.path for a in assertions]
        assert None in paths  # Body principal
        assert "data" in paths
        assert "meta" in paths

    def test_skips_endpoints_without_schema(self) -> None:
        """Ignora endpoints sem schema de resposta."""
        spec = {
            "endpoints": [
                {
                    "path": "/health",
                    "method": "GET",
                    "responses": {
                        "200": {"description": "OK"},
                    },
                },
            ],
        }

        assertions = generate_schema_assertions(spec)

        assert len(assertions) == 0

    def test_tries_multiple_success_codes(self) -> None:
        """Tenta múltiplos status codes 2xx."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "responses": {
                        "201": {
                            "schema": {"type": "object"},
                        },
                    },
                },
            ],
        }

        assertions = generate_schema_assertions(spec)

        assert len(assertions) == 1
        assert assertions[0].endpoint_key == "POST /users"


class TestSchemaAssertionsToDict:
    """Testes para schema_assertions_to_dict."""

    def test_converts_to_runner_format(self) -> None:
        """Converte para formato de assertion do Runner."""
        assertions = [
            SchemaAssertion(
                endpoint_key="GET /users",
                schema={"type": "array"},
                operator="valid",
            ),
        ]

        result = schema_assertions_to_dict(assertions)

        assert "GET /users" in result
        assert len(result["GET /users"]) == 1
        assert result["GET /users"][0]["type"] == "json_schema"
        assert result["GET /users"][0]["operator"] == "valid"
        assert result["GET /users"][0]["value"] == {"type": "array"}

    def test_includes_path_when_present(self) -> None:
        """Inclui path na assertion quando especificado."""
        assertions = [
            SchemaAssertion(
                endpoint_key="GET /users",
                schema={"type": "object"},
                path="data.user",
                operator="valid",
            ),
        ]

        result = schema_assertions_to_dict(assertions)

        assert result["GET /users"][0]["path"] == "data.user"

    def test_groups_by_endpoint(self) -> None:
        """Agrupa assertions por endpoint."""
        assertions = [
            SchemaAssertion(
                endpoint_key="GET /users",
                schema={"type": "array"},
                operator="valid",
            ),
            SchemaAssertion(
                endpoint_key="GET /users",
                schema={"type": "object"},
                path="data",
                operator="valid",
            ),
            SchemaAssertion(
                endpoint_key="POST /users",
                schema={"type": "object"},
                operator="valid",
            ),
        ]

        result = schema_assertions_to_dict(assertions)

        assert len(result["GET /users"]) == 2
        assert len(result["POST /users"]) == 1


class TestInjectSchemaAssertions:
    """Testes para inject_schema_assertions."""

    def test_injects_schema_assertion(self) -> None:
        """Injeta assertion de schema em steps."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "GET",
                    "responses": {
                        "200": {
                            "schema": {"type": "array"},
                        },
                    },
                },
            ],
        }

        steps = [
            {
                "id": "get-users",
                "action": {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/users",
                },
            },
        ]

        enriched = inject_schema_assertions(steps, spec)

        assert "assertions" in enriched[0]
        schema_assertions = [
            a for a in enriched[0]["assertions"] if a["type"] == "json_schema"
        ]
        assert len(schema_assertions) == 1
        assert schema_assertions[0]["operator"] == "valid"

    def test_does_not_duplicate_schema_assertion(self) -> None:
        """Não duplica assertion de schema se já existir."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "GET",
                    "responses": {
                        "200": {"schema": {"type": "array"}},
                    },
                },
            ],
        }

        steps = [
            {
                "id": "get-users",
                "action": {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/users",
                },
                "assertions": [
                    {"type": "json_schema", "operator": "valid", "value": {"type": "object"}},
                ],
            },
        ]

        enriched = inject_schema_assertions(steps, spec)

        schema_assertions = [
            a for a in enriched[0]["assertions"] if a["type"] == "json_schema"
        ]
        # Deve manter apenas o original
        assert len(schema_assertions) == 1
        assert schema_assertions[0]["value"] == {"type": "object"}

    def test_preserves_other_assertions(self) -> None:
        """Preserva outras assertions ao injetar schema."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "GET",
                    "responses": {
                        "200": {"schema": {"type": "array"}},
                    },
                },
            ],
        }

        steps = [
            {
                "id": "get-users",
                "action": {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/users",
                },
                "assertions": [
                    {"type": "status_code", "operator": "eq", "value": 200},
                ],
            },
        ]

        enriched = inject_schema_assertions(steps, spec)

        assert len(enriched[0]["assertions"]) == 2
        types = [a["type"] for a in enriched[0]["assertions"]]
        assert "status_code" in types
        assert "json_schema" in types

    def test_skips_non_http_steps(self) -> None:
        """Ignora steps que não são HTTP."""
        spec = {"endpoints": []}

        steps = [
            {
                "id": "wait-1",
                "action": {"type": "wait", "duration_ms": 1000},
            },
        ]

        enriched = inject_schema_assertions(steps, spec)

        assert "assertions" not in enriched[0]

    def test_includes_nested_paths_when_enabled(self) -> None:
        """Inclui assertions para sub-paths quando habilitado."""
        spec = {
            "endpoints": [
                {
                    "path": "/users/{id}",
                    "method": "GET",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {"type": "object"},
                                },
                            },
                        },
                    },
                },
            ],
        }

        steps = [
            {
                "id": "get-user",
                "action": {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/users/{id}",
                },
            },
        ]

        enriched = inject_schema_assertions(steps, spec, validate_nested=True)

        schema_assertions = [
            a for a in enriched[0]["assertions"] if a["type"] == "json_schema"
        ]
        # Deve ter assertion para body e para "data"
        assert len(schema_assertions) >= 2


class TestGenerateSchemaViolationCases:
    """Testes para generate_schema_violation_cases."""

    def test_generates_type_violation_cases(self) -> None:
        """Gera casos de violação de tipo."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "age": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            ],
        }

        cases = generate_schema_violation_cases(spec)

        assert len(cases) >= 1
        case_types = [c.case_type for c in cases]
        assert "schema_type_violation" in case_types

        # Verifica que tem violações para diferentes campos
        field_names = [c.field_name for c in cases]
        assert "name" in field_names or "age" in field_names

    def test_generates_enum_violation_cases(self) -> None:
        """Gera casos de violação de enum."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {
                                        "type": "string",
                                        "enum": ["active", "inactive"],
                                    },
                                },
                            },
                        },
                    },
                },
            ],
        }

        cases = generate_schema_violation_cases(spec)

        case_types = [c.case_type for c in cases]
        assert "schema_enum_violation" in case_types

    def test_generates_bound_violation_cases(self) -> None:
        """Gera casos de violação de limites."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "age": {
                                        "type": "integer",
                                        "minimum": 0,
                                    },
                                },
                            },
                        },
                    },
                },
            ],
        }

        cases = generate_schema_violation_cases(spec)

        case_types = [c.case_type for c in cases]
        assert "schema_bound_violation" in case_types

        # Valor deve ser abaixo do mínimo
        bound_case = next(c for c in cases if c.case_type == "schema_bound_violation")
        assert bound_case.invalid_value < 0

    def test_respects_max_cases_per_endpoint(self) -> None:
        """Respeita limite de casos por endpoint."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "field1": {"type": "string"},
                                    "field2": {"type": "integer"},
                                    "field3": {"type": "boolean"},
                                    "field4": {"type": "string"},
                                    "field5": {"type": "integer"},
                                    "field6": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            ],
        }

        cases = generate_schema_violation_cases(spec, max_cases_per_endpoint=3)

        assert len(cases) <= 3

    def test_skips_endpoints_without_schema(self) -> None:
        """Ignora endpoints sem schema."""
        spec = {
            "endpoints": [
                {
                    "path": "/health",
                    "method": "GET",
                    "responses": {
                        "200": {"description": "OK"},
                    },
                },
            ],
        }

        cases = generate_schema_violation_cases(spec)

        assert len(cases) == 0

    def test_all_cases_expect_4xx(self) -> None:
        """Todos os casos de violação esperam erro 4xx."""
        spec = {
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            ],
        }

        cases = generate_schema_violation_cases(spec)

        for case in cases:
            assert case.expected_status_range == "4xx"
            assert case.expected_status == 400
