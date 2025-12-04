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

# Adiciona o diretÃ³rio brain ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.negative_cases import (
    NegativeCase,
    NegativeTestResult,
    analyze_and_generate,
    generate_negative_cases,
    negative_cases_to_utdl_steps,
)

# FunÃ§Ãµes auxiliares pÃºblicas para testes detalhados
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
