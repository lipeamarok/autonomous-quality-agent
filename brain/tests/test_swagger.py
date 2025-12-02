"""
Testes para o módulo de ingestão OpenAPI/Swagger.

Testa:
- Validação de especificações OpenAPI
- Parsing de specs v2 e v3
- Conversão para texto
"""

import sys
from pathlib import Path
from typing import Any

import pytest

# Adiciona o diretório brain ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.swagger import (
    OpenAPIValidationException,
    parse_openapi,
    spec_to_requirement_text,
    validate_openapi_spec,
)


class TestValidateOpenAPISpec:
    """Testes para validate_openapi_spec."""

    def test_empty_spec_is_invalid(self) -> None:
        """Spec vazia deve ser inválida."""
        result = validate_openapi_spec({})
        assert not result.is_valid
        assert len(result.errors) > 0
        assert "vazia" in result.errors[0].lower()

    def test_missing_version_field(self) -> None:
        """Spec sem campo openapi ou swagger é inválida."""
        spec: dict[str, Any] = {"info": {"title": "Test"}, "paths": {}}
        result = validate_openapi_spec(spec)
        assert not result.is_valid
        assert any("openapi" in e.lower() or "swagger" in e.lower() for e in result.errors)

    def test_valid_openapi_3_spec(self) -> None:
        """Spec OpenAPI 3.0 válida deve passar."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {"200": {"description": "Success"}},
                    }
                }
            },
        }
        result = validate_openapi_spec(spec)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_info_generates_warning(self) -> None:
        """Spec sem campo info deve gerar warning."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "paths": {
                "/test": {
                    "get": {"responses": {"200": {"description": "OK"}}}
                }
            },
        }
        # Mesmo sem info, a spec pode ser válida, mas gera warning
        result = validate_openapi_spec(spec)
        # O validador pode ou não considerar válida dependendo da versão
        # Verificamos se há warning sobre info
        assert any("info" in w.lower() for w in result.warnings) or not result.is_valid

    def test_empty_paths_generates_warning(self) -> None:
        """Spec sem endpoints em paths deve gerar warning."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "Empty API", "version": "1.0.0"},
            "paths": {},
        }
        result = validate_openapi_spec(spec)
        assert any("paths" in w.lower() or "endpoint" in w.lower() for w in result.warnings)


class TestParseOpenAPI:
    """Testes para parse_openapi."""

    def test_parse_dict_source(self) -> None:
        """Parsing de dict fonte deve funcionar."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "My API", "version": "1.0.0"},
            "servers": [{"url": "https://api.example.com"}],
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {"200": {"description": "Success"}},
                    }
                }
            },
        }
        result = parse_openapi(spec)

        assert result["title"] == "My API"
        assert result["base_url"] == "https://api.example.com"
        assert len(result["endpoints"]) == 1
        assert result["endpoints"][0]["method"] == "GET"
        assert result["endpoints"][0]["path"] == "/users"

    def test_parse_with_validation(self) -> None:
        """Parsing deve incluir resultado da validação."""
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "Valid API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {"responses": {"200": {"description": "OK"}}}
                }
            },
        }
        result = parse_openapi(spec, validate_spec=True)

        assert "validation" in result
        assert result["validation"]["is_valid"] is True

    def test_parse_skip_validation(self) -> None:
        """Parsing sem validação não deve incluir campo validation."""
        spec: dict[str, Any] = {"openapi": "3.0.0", "paths": {}}  # Inválida, mas passamos sem validar
        result = parse_openapi(spec, validate_spec=False)

        assert "validation" not in result

    def test_strict_mode_raises_on_invalid(self) -> None:
        """Modo strict deve levantar exceção em spec inválida."""
        spec: dict[str, Any] = {}  # Spec vazia é inválida

        with pytest.raises(OpenAPIValidationException) as exc_info:
            parse_openapi(spec, strict=True)

        assert exc_info.value.validation_result.is_valid is False

    def test_non_strict_mode_continues_on_invalid(self) -> None:
        """Modo não-strict deve continuar mesmo com spec inválida."""
        spec: dict[str, Any] = {"openapi": "3.0.0", "paths": {}}  # Falta info

        # Não deve levantar exceção
        result = parse_openapi(spec, strict=False)
        assert "endpoints" in result


class TestSpecToRequirementText:
    """Testes para spec_to_requirement_text."""

    def test_basic_conversion(self) -> None:
        """Conversão básica deve incluir título e endpoints."""
        spec: dict[str, Any] = {
            "title": "User API",
            "base_url": "https://api.example.com",
            "endpoints": [
                {
                    "path": "/users",
                    "method": "GET",
                    "summary": "List all users",
                    "parameters": [{"name": "page"}],
                    "request_body": None,
                    "responses": {"200": {"description": "Success"}},
                }
            ],
        }

        text = spec_to_requirement_text(spec)

        assert "User API" in text
        assert "https://api.example.com" in text
        assert "GET /users" in text
        assert "List all users" in text
        assert "page" in text.lower()
        assert "200" in text

    def test_multiple_endpoints(self) -> None:
        """Múltiplos endpoints devem ser listados."""
        spec: dict[str, Any] = {
            "title": "API",
            "base_url": "",
            "endpoints": [
                {"path": "/a", "method": "GET", "summary": "", "parameters": [], "responses": {}},
                {"path": "/b", "method": "POST", "summary": "", "parameters": [], "responses": {}},
                {"path": "/c", "method": "DELETE", "summary": "", "parameters": [], "responses": {}},
            ],
        }

        text = spec_to_requirement_text(spec)

        assert "GET /a" in text
        assert "POST /b" in text
        assert "DELETE /c" in text

    def test_endpoint_with_body(self) -> None:
        """Endpoint com body deve indicar que aceita JSON."""
        spec: dict[str, Any] = {
            "title": "API",
            "base_url": "",
            "endpoints": [
                {
                    "path": "/users",
                    "method": "POST",
                    "summary": "Create user",
                    "parameters": [],
                    "request_body": {"required": True, "schema": {}},
                    "responses": {},
                }
            ],
        }

        text = spec_to_requirement_text(spec)

        assert "corpo JSON" in text.lower() or "json" in text.lower()
