"""
Módulo de Ingestão OpenAPI/Swagger.

Parseia especificações OpenAPI (v3) e Swagger (v2) e as converte para um
formato normalizado que pode ser usado pelo LLM para geração de planos de teste.

Funcionalidades:
- Carregamento de specs de arquivo (JSON/YAML), URL ou dict
- Extração de endpoints, parâmetros, request bodies e responses
- Conversão para texto em linguagem natural para consumo pelo LLM
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_openapi(source: str | Path | dict[str, Any]) -> dict[str, Any]:
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

    Returns:
        Dicionário normalizado contendo:
        - base_url: URL do servidor
        - title: Título da API
        - endpoints: Lista de resumos de endpoints

    Raises:
        FileNotFoundError: Se o arquivo não existir
        requests.HTTPError: Se a URL retornar erro
        yaml.YAMLError: Se o YAML for inválido
        json.JSONDecodeError: Se o JSON for inválido

    Example:
        >>> spec = parse_openapi("./openapi.yaml")
        >>> spec = parse_openapi("https://api.example.com/openapi.json")
        >>> spec = parse_openapi({"openapi": "3.0.0", ...})
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

    return _normalize_spec(spec)


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
