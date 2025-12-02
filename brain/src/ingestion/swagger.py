"""
Módulo de Ingestão OpenAPI/Swagger.

Parseia especificações OpenAPI (v3) e Swagger (v2) e as converte para um
formato normalizado que pode ser usado pelo LLM para geração de planos de teste.

Funcionalidades:
- Validação de specs usando openapi-spec-validator
- Carregamento de specs de arquivo (JSON/YAML), URL ou dict
- Extração de endpoints, parâmetros, request bodies e responses
- Conversão para texto em linguagem natural para consumo pelo LLM
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Hashable, Mapping, cast

from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError


def _empty_str_list() -> list[str]:
    """Factory para lista vazia de strings (tipagem explícita)."""
    return []


@dataclass
class ValidationResult:
    """
    Resultado da validação de uma especificação OpenAPI.

    Attributes:
        is_valid: True se a spec é válida, False caso contrário.
        errors: Lista de erros de validação encontrados.
        warnings: Lista de avisos (não-bloqueantes).
    """

    is_valid: bool = True
    errors: list[str] = field(default_factory=_empty_str_list)
    warnings: list[str] = field(default_factory=_empty_str_list)


class OpenAPIValidationException(Exception):
    """
    Exceção lançada quando uma especificação OpenAPI é inválida.

    Attributes:
        validation_result: Resultado detalhado da validação.
    """

    def __init__(self, message: str, validation_result: ValidationResult) -> None:
        super().__init__(message)
        self.validation_result = validation_result


def validate_openapi_spec(spec: dict[str, Any]) -> ValidationResult:
    """
    Valida uma especificação OpenAPI usando openapi-spec-validator.

    Verifica:
    - Conformidade com schema OpenAPI 3.x ou Swagger 2.0
    - Referências ($ref) válidas
    - Estrutura de paths, operations, schemas

    Args:
        spec: Dicionário contendo a especificação OpenAPI

    Returns:
        ValidationResult com is_valid, errors e warnings

    Example:
        >>> result = validate_openapi_spec({"openapi": "3.0.0", ...})
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(f"Erro: {error}")
    """
    result = ValidationResult()

    # Verificações básicas
    if not spec:
        result.is_valid = False
        result.errors.append("Especificação vazia")
        return result

    has_openapi = "openapi" in spec
    has_swagger = "swagger" in spec

    if not has_openapi and not has_swagger:
        result.is_valid = False
        result.errors.append(
            "Especificação inválida: ausência de campo 'openapi' (v3) ou 'swagger' (v2)"
        )
        return result

    if "info" not in spec:
        result.warnings.append("Campo 'info' ausente (recomendado)")

    if "paths" not in spec or not spec.get("paths"):
        result.warnings.append("Nenhum endpoint definido em 'paths'")

    # Validação completa usando openapi-spec-validator
    try:
        validate(cast(Mapping[Hashable, Any], spec))
    except OpenAPIValidationError as e:
        result.is_valid = False
        # Extrai mensagens de erro do validador
        error_msg = str(e)
        if hasattr(e, "message"):
            error_msg = e.message
        result.errors.append(f"Falha na validação OpenAPI: {error_msg}")

        # Se houver erros aninhados, adiciona-os também
        if hasattr(e, "__cause__") and e.__cause__:
            result.errors.append(f"Causa: {e.__cause__!s}")

    except Exception as e:
        result.is_valid = False
        result.errors.append(f"Erro inesperado na validação: {e!s}")

    return result


def parse_openapi(
    source: str | Path | dict[str, Any],
    *,
    validate_spec: bool = True,
    strict: bool = False,
) -> dict[str, Any]:
    """
    Parseia uma especificação OpenAPI de várias fontes.

    Suporta carregamento de:
    - Arquivos locais (JSON ou YAML)
    - URLs remotas (HTTP/HTTPS)
    - Dicionários já parseados

    Args:
        source: Pode ser:
            - Caminho de arquivo (str ou Path)
            - URL (str começando com http:// ou https://)
            - dict (já parseado)
        validate_spec: Se True, valida a spec antes de processar.
            Default: True.
        strict: Se True, levanta exceção em specs inválidas.
            Se False, apenas loga warnings e continua.
            Default: False.

    Returns:
        Dicionário normalizado contendo:
        - base_url: URL do servidor
        - title: Título da API
        - endpoints: Lista de resumos de endpoints
        - validation: Resultado da validação (se validate_spec=True)

    Raises:
        FileNotFoundError: Se o arquivo não existir
        requests.HTTPError: Se a URL retornar erro
        yaml.YAMLError: Se o YAML for inválido
        json.JSONDecodeError: Se o JSON for inválido
        OpenAPIValidationException: Se strict=True e a spec for inválida

    Example:
        >>> spec = parse_openapi("./openapi.yaml")
        >>> spec = parse_openapi("https://api.example.com/openapi.json")
        >>> spec = parse_openapi({"openapi": "3.0.0", ...})
        >>> # Modo estrito - falha em specs inválidas
        >>> spec = parse_openapi("./api.yaml", strict=True)
    """
    if isinstance(source, dict):
        spec = source
    else:
        source_str = str(source)
        if source_str.startswith(("http://", "https://")):
            import requests

            resp = requests.get(source_str, timeout=30)
            resp.raise_for_status()
            spec = resp.json()
        else:
            path = Path(source)
            with path.open(encoding="utf-8") as f:
                if path.suffix in (".yaml", ".yml"):
                    import yaml

                    spec = yaml.safe_load(f)
                else:
                    spec = json.load(f)

    # Validação opcional
    validation_result: ValidationResult | None = None
    if validate_spec:
        validation_result = validate_openapi_spec(spec)

        if not validation_result.is_valid:
            if strict:
                raise OpenAPIValidationException(
                    f"Especificação OpenAPI inválida: {', '.join(validation_result.errors)}",
                    validation_result,
                )
            # Log warnings se não for strict
            import logging

            logger = logging.getLogger(__name__)
            for error in validation_result.errors:
                logger.warning("OpenAPI validation error: %s", error)

        for warning in validation_result.warnings:
            import logging

            logger = logging.getLogger(__name__)
            logger.info("OpenAPI validation warning: %s", warning)

    normalized = _normalize_spec(spec)

    # Adiciona resultado da validação ao output
    if validation_result:
        normalized["validation"] = {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
        }

    return normalized


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """
    Converte spec OpenAPI para formato simplificado para consumo pelo LLM.

    Args:
        spec: Especificação OpenAPI/Swagger completa

    Returns:
        Dicionário com base_url, title e lista de endpoints
    """
    # Extrai URL base
    base_url = ""
    if "servers" in spec and spec["servers"]:
        base_url = spec["servers"][0].get("url", "")

    # Extrai endpoints
    endpoints: list[dict[str, Any]] = []
    paths: dict[str, Any] = spec.get("paths", {})

    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue

            endpoint: dict[str, Any] = {
                "path": path,
                "method": method.upper(),
                "summary": details.get("summary", ""),
                "description": details.get("description", ""),
                "parameters": _extract_parameters(details),
                "request_body": _extract_request_body(details),
                "responses": _extract_responses(details),
            }
            endpoints.append(endpoint)

    return {
        "base_url": base_url,
        "title": spec.get("info", {}).get("title", "API"),
        "endpoints": endpoints,
    }


def _extract_parameters(details: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extrai parâmetros de query, path e header de um endpoint.

    Args:
        details: Detalhes do endpoint na spec OpenAPI

    Returns:
        Lista de dicionários com informações de cada parâmetro
    """
    params: list[dict[str, Any]] = []
    for param in details.get("parameters", []):
        params.append(
            {
                "name": param.get("name"),
                "in": param.get("in"),  # query, path, header
                "required": param.get("required", False),
                "type": param.get("schema", {}).get("type", "string"),
            }
        )
    return params


def _extract_request_body(details: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extrai schema do request body de um endpoint.

    Args:
        details: Detalhes do endpoint na spec OpenAPI

    Returns:
        Dicionário com required e schema, ou None se não houver body
    """
    body = details.get("requestBody", {})
    if not body:
        return None

    content = body.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})

    return {
        "required": body.get("required", False),
        "schema": schema,
    }


def _extract_responses(details: dict[str, Any]) -> dict[str, dict[str, str]]:
    """
    Extrai definições de responses de um endpoint.

    Args:
        details: Detalhes do endpoint na spec OpenAPI

    Returns:
        Dicionário mapeando códigos HTTP para descrições
    """
    responses: dict[str, dict[str, str]] = {}
    for code, response in details.get("responses", {}).items():
        responses[code] = {
            "description": response.get("description", ""),
        }
    return responses


def spec_to_requirement_text(spec: dict[str, Any]) -> str:
    """
    Converte uma spec OpenAPI normalizada para texto em linguagem natural.

    Este texto pode ser passado diretamente ao LLM para geração de planos
    de teste. O formato é legível tanto por humanos quanto por modelos de IA.

    Args:
        spec: Especificação normalizada (output de parse_openapi)

    Returns:
        String com descrição textual da API e seus endpoints

    Example:
        >>> spec = parse_openapi("./api.yaml")
        >>> text = spec_to_requirement_text(spec)
        >>> plan = generate_utdl(requirement=text, base_url=spec["base_url"])
    """
    lines: list[str] = [f"API: {spec.get('title', 'API Desconhecida')}"]
    lines.append(f"URL Base: {spec.get('base_url', 'Não especificada')}")
    lines.append("")
    lines.append("Endpoints:")

    for endpoint in spec.get("endpoints", []):
        lines.append(f"\n- {endpoint['method']} {endpoint['path']}")
        if endpoint.get("summary"):
            lines.append(f"  Resumo: {endpoint['summary']}")
        if endpoint.get("parameters"):
            params = ", ".join(p["name"] for p in endpoint["parameters"])
            lines.append(f"  Parâmetros: {params}")
        if endpoint.get("request_body"):
            lines.append("  Aceita corpo JSON")
        if endpoint.get("responses"):
            codes = ", ".join(endpoint["responses"].keys())
            lines.append(f"  Códigos de resposta: {codes}")

    return "\n".join(lines)
