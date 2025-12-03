"""
================================================================================
MÓDULO DE INGESTÃO OPENAPI/SWAGGER
================================================================================

Este módulo processa especificações OpenAPI (v3) e Swagger (v2) e as converte
para um formato que o LLM pode entender facilmente.

## Para todos entenderem:

OpenAPI (antes chamado Swagger) é um formato padrão para documentar APIs REST.
É como um "contrato" que diz:
- Quais endpoints a API tem (ex: /users, /login)
- Quais métodos HTTP cada um aceita (GET, POST, etc.)
- Quais parâmetros são necessários
- Quais respostas são possíveis

Este módulo lê essa documentação e a converte para texto simples
que a IA pode usar para gerar planos de teste automaticamente.

## Fluxo típico:

1. Usuário tem arquivo openapi.json ou URL da spec
2. `parse_openapi()` carrega e valida a spec
3. `spec_to_requirement_text()` converte para texto legível
4. Esse texto vai para o LLM gerar o plano UTDL

## Funcionalidades:
- Validação de specs usando openapi-spec-validator
- Carregamento de specs de arquivo (JSON/YAML), URL ou dict
- Extração de endpoints, parâmetros, request bodies e responses
- Conversão para texto em linguagem natural para consumo pelo LLM
"""

# =============================================================================
# IMPORTS - Bibliotecas necessárias
# =============================================================================

from __future__ import annotations

# json: Para ler arquivos .json
import json

# dataclass: Simplifica criação de classes de dados
from dataclasses import dataclass, field

# Path: Manipulação de caminhos de arquivo de forma cross-platform
from pathlib import Path

# typing: Anotações de tipo para melhor documentação
from typing import Any, Hashable, Mapping, cast

# openapi_spec_validator: Biblioteca que valida specs OpenAPI
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================


def _empty_str_list() -> list[str]:
    """
    Factory para lista vazia de strings.

    ## Para todos entenderem:
    Uma "factory function" é uma função que cria objetos.
    Esta é usada como valor padrão em dataclasses para evitar
    o problema de listas mutáveis compartilhadas.

    Por que não usar `field(default_factory=list)`?
    Porque `list` não tem tipo definido. Esta função
    retorna `list[str]` explicitamente para o type checker.
    """
    return []


# =============================================================================
# CLASSES DE DADOS
# =============================================================================


@dataclass
class ValidationResult:
    """
    Resultado da validação de uma especificação OpenAPI.

    ## Para todos entenderem:
    @dataclass é um "decorador" que transforma a classe em uma
    estrutura de dados simples. Gera automaticamente __init__,
    __repr__, etc.

    ## Atributos:
        is_valid: True se a spec é válida, False caso contrário.
            Exemplo: Uma spec sem campo "openapi" retorna False.

        errors: Lista de erros de validação encontrados.
            Exemplo: ["Campo 'info' ausente", "Path inválido"]

        warnings: Lista de avisos (não-bloqueantes).
            Exemplo: ["Nenhum endpoint definido em 'paths'"]
            Warnings não invalidam a spec, apenas alertam.
    """

    is_valid: bool = True
    errors: list[str] = field(default_factory=_empty_str_list)
    warnings: list[str] = field(default_factory=_empty_str_list)


class OpenAPIValidationException(Exception):
    """
    Exceção lançada quando uma especificação OpenAPI é inválida.

    ## Para todos entenderem:
    Exceções são "erros controlados" que podemos capturar e tratar.
    Esta exceção é lançada no modo "strict" quando a spec é inválida.

    ## Atributos:
        validation_result: Resultado detalhado da validação.
            Contém a lista de erros específicos encontrados.
    """

    def __init__(self, message: str, validation_result: ValidationResult) -> None:
        # Chama o construtor da classe pai (Exception)
        super().__init__(message)
        # Armazena o resultado para acesso posterior
        self.validation_result = validation_result


# =============================================================================
# FUNÇÃO DE VALIDAÇÃO
# =============================================================================


def validate_openapi_spec(spec: dict[str, Any]) -> ValidationResult:
    """
    Valida uma especificação OpenAPI usando openapi-spec-validator.

    ## Para todos entenderem:
    Esta função verifica se um arquivo OpenAPI/Swagger está correto.
    É como um "corretor ortográfico" para documentação de API.

    ## Verificações realizadas:
    - Conformidade com schema OpenAPI 3.x ou Swagger 2.0
    - Referências ($ref) válidas (links internos no documento)
    - Estrutura de paths, operations, schemas

    ## Parâmetros:
        spec: Dicionário contendo a especificação OpenAPI.
            Normalmente vem de json.load() ou yaml.safe_load().

    ## Retorna:
        ValidationResult com:
        - is_valid: True/False
        - errors: Lista de erros (se houver)
        - warnings: Lista de avisos

    ## Exemplo:
        >>> result = validate_openapi_spec({"openapi": "3.0.0", ...})
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(f"Erro: {error}")
    """
    # Cria objeto de resultado, inicialmente válido
    result = ValidationResult()

    # -----------------------------------------------------------------
    # Verificações básicas (antes de chamar o validador externo)
    # -----------------------------------------------------------------

    # Spec vazia não faz sentido
    if not spec:
        result.is_valid = False
        result.errors.append("Especificação vazia")
        return result

    # Verifica se tem campo de versão (openapi para v3, swagger para v2)
    has_openapi = "openapi" in spec
    has_swagger = "swagger" in spec

    if not has_openapi and not has_swagger:
        result.is_valid = False
        result.errors.append(
            "Especificação inválida: ausência de campo 'openapi' (v3) ou 'swagger' (v2)"
        )
        return result

    # Warnings (não bloqueiam, apenas alertam)
    if "info" not in spec:
        result.warnings.append("Campo 'info' ausente (recomendado)")

    if "paths" not in spec or not spec.get("paths"):
        result.warnings.append("Nenhum endpoint definido em 'paths'")

    # -----------------------------------------------------------------
    # Validação completa usando openapi-spec-validator
    # -----------------------------------------------------------------

    try:
        # cast() é só para o type checker, não faz nada em runtime
        validate(cast(Mapping[Hashable, Any], spec))

    except OpenAPIValidationError as e:
        # Spec inválida segundo o validador oficial
        result.is_valid = False

        # Extrai mensagem de erro
        error_msg = str(e)
        if hasattr(e, "message"):
            error_msg = e.message
        result.errors.append(f"Falha na validação OpenAPI: {error_msg}")

        # Se houver causa encadeada, adiciona também
        if hasattr(e, "__cause__") and e.__cause__:
            result.errors.append(f"Causa: {e.__cause__!s}")

    except Exception as e:
        # Erro inesperado (bug no validador, etc.)
        result.is_valid = False
        result.errors.append(f"Erro inesperado na validação: {e!s}")

    return result


# =============================================================================
# FUNÇÃO PRINCIPAL DE PARSING
# =============================================================================


def parse_openapi(
    source: str | Path | dict[str, Any],
    *,
    validate_spec: bool = True,
    strict: bool = False,
) -> dict[str, Any]:
    """
    Parseia uma especificação OpenAPI de várias fontes.

    ## Para todos entenderem:
    Esta é a função principal do módulo. Ela:
    1. Carrega a spec de onde quer que esteja
    2. Opcionalmente valida
    3. Normaliza para um formato simplificado

    ## Fontes suportadas:
    - Arquivos locais (JSON ou YAML)
    - URLs remotas (HTTP/HTTPS)
    - Dicionários já parseados

    ## Parâmetros:
        source: Pode ser:
            - Caminho de arquivo: "./openapi.json" ou Path("./openapi.yaml")
            - URL: "https://api.example.com/openapi.json"
            - dict: {"openapi": "3.0.0", ...}

        validate_spec: Se True, valida a spec antes de processar.
            Default: True.

        strict: Se True, levanta exceção em specs inválidas.
            Se False, apenas loga warnings e continua.
            Default: False.

    ## Retorna:
        Dicionário normalizado contendo:
        - base_url: URL do servidor (ex: "https://api.example.com")
        - title: Título da API (ex: "User Management API")
        - endpoints: Lista de resumos de endpoints
        - validation: Resultado da validação (se validate_spec=True)

    ## Erros possíveis:
        FileNotFoundError: Se o arquivo não existir
        requests.HTTPError: Se a URL retornar erro
        yaml.YAMLError: Se o YAML for inválido
        json.JSONDecodeError: Se o JSON for inválido
        OpenAPIValidationException: Se strict=True e a spec for inválida

    ## Exemplos:
        >>> spec = parse_openapi("./openapi.yaml")
        >>> spec = parse_openapi("https://api.example.com/openapi.json")
        >>> spec = parse_openapi({"openapi": "3.0.0", ...})
        >>> # Modo estrito - falha em specs inválidas
        >>> spec = parse_openapi("./api.yaml", strict=True)
    """
    # -----------------------------------------------------------------
    # Passo 1: Carregar a spec da fonte apropriada
    # -----------------------------------------------------------------

    if isinstance(source, dict):
        # Já é um dicionário, usa direto
        spec = source
    else:
        # Converte para string para verificar tipo
        source_str = str(source)

        if source_str.startswith(("http://", "https://")):
            # É uma URL, faz download
            import requests

            resp = requests.get(source_str, timeout=30)
            resp.raise_for_status()  # Lança exceção se erro HTTP
            spec = resp.json()
        else:
            # É um arquivo local
            path = Path(source)
            with path.open(encoding="utf-8") as f:
                if path.suffix in (".yaml", ".yml"):
                    # Arquivo YAML
                    import yaml

                    spec = yaml.safe_load(f)
                else:
                    # Assume JSON
                    spec = json.load(f)

    # -----------------------------------------------------------------
    # Passo 2: Validação opcional
    # -----------------------------------------------------------------

    validation_result: ValidationResult | None = None

    if validate_spec:
        validation_result = validate_openapi_spec(spec)

        if not validation_result.is_valid:
            if strict:
                # Modo estrito: lança exceção
                raise OpenAPIValidationException(
                    f"Especificação OpenAPI inválida: {', '.join(validation_result.errors)}",
                    validation_result,
                )
            # Modo não-estrito: loga warnings e continua
            import logging

            logger = logging.getLogger(__name__)
            for error in validation_result.errors:
                logger.warning("OpenAPI validation error: %s", error)

        # Loga warnings independente de validez
        for warning in validation_result.warnings:
            import logging

            logger = logging.getLogger(__name__)
            logger.info("OpenAPI validation warning: %s", warning)

    # -----------------------------------------------------------------
    # Passo 3: Normalização
    # -----------------------------------------------------------------

    normalized = _normalize_spec(spec)

    # Adiciona resultado da validação ao output
    if validation_result:
        normalized["validation"] = {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
        }

    return normalized


# =============================================================================
# FUNÇÕES DE NORMALIZAÇÃO (Internas)
# =============================================================================


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """
    Converte spec OpenAPI para formato simplificado para consumo pelo LLM.

    ## Para todos entenderem:
    Specs OpenAPI podem ser muito complexas, com centenas de campos.
    Esta função extrai apenas o essencial:
    - URL base do servidor
    - Título da API
    - Lista de endpoints com método, path, parâmetros, etc.

    ## Parâmetros:
        spec: Especificação OpenAPI/Swagger completa

    ## Retorna:
        Dicionário simplificado com base_url, title e endpoints
    """
    # Extrai URL base do campo "servers" (OpenAPI 3.x)
    base_url = ""
    if "servers" in spec and spec["servers"]:
        # Pega o primeiro servidor da lista
        base_url = spec["servers"][0].get("url", "")

    # Lista para acumular endpoints
    endpoints: list[dict[str, Any]] = []

    # Itera sobre paths (ex: "/users", "/auth/login")
    paths: dict[str, Any] = spec.get("paths", {})

    for path, methods in paths.items():
        # Para cada path, itera sobre métodos (get, post, etc.)
        for method, details in methods.items():
            # Ignora métodos inválidos (parameters, servers são campos especiais)
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue

            # Extrai informações do endpoint
            endpoint: dict[str, Any] = {
                "path": path,  # Ex: "/users/{id}"
                "method": method.upper(),  # Ex: "GET"
                "summary": details.get("summary", ""),  # Descrição curta
                "description": details.get("description", ""),  # Descrição longa
                "parameters": _extract_parameters(details),  # Query, path, header params
                "request_body": _extract_request_body(details),  # Body para POST/PUT
                "responses": _extract_responses(details),  # Códigos de resposta
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

    ## Para todos entenderem:
    Parâmetros são dados que você envia junto com a requisição:
    - **path**: Parte da URL (ex: /users/{id} -> id é parâmetro)
    - **query**: Após o ? na URL (ex: /users?page=1 -> page é parâmetro)
    - **header**: Cabeçalhos HTTP (ex: Authorization)

    ## Parâmetros:
        details: Detalhes do endpoint na spec OpenAPI

    ## Retorna:
        Lista de dicionários com informações de cada parâmetro:
        - name: Nome do parâmetro
        - in: Onde ele vai (query, path, header)
        - required: Se é obrigatório
        - type: Tipo de dado (string, integer, etc.)
    """
    params: list[dict[str, Any]] = []

    for param in details.get("parameters", []):
        params.append(
            {
                "name": param.get("name"),
                "in": param.get("in"),  # "query", "path", "header"
                "required": param.get("required", False),
                "type": param.get("schema", {}).get("type", "string"),
            }
        )

    return params


def _extract_request_body(details: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extrai schema do request body de um endpoint.

    ## Para todos entenderem:
    Request body é o "corpo" da requisição - dados enviados
    em requisições POST, PUT, PATCH. Geralmente é JSON.

    ## Parâmetros:
        details: Detalhes do endpoint na spec OpenAPI

    ## Retorna:
        Dicionário com required e schema, ou None se não houver body
    """
    body = details.get("requestBody", {})
    if not body:
        return None

    # OpenAPI 3.x usa content -> application/json -> schema
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

    ## Para todos entenderem:
    Responses são as possíveis respostas que a API pode retornar.
    Cada uma tem um código HTTP (200, 404, 500) e uma descrição.

    ## Parâmetros:
        details: Detalhes do endpoint na spec OpenAPI

    ## Retorna:
        Dicionário mapeando códigos HTTP para descrições.
        Ex: {"200": {"description": "Success"}, "404": {"description": "Not found"}}
    """
    responses: dict[str, dict[str, str]] = {}

    for code, response in details.get("responses", {}).items():
        responses[code] = {
            "description": response.get("description", ""),
        }

    return responses


# =============================================================================
# CONVERSÃO PARA TEXTO
# =============================================================================


def spec_to_requirement_text(spec: dict[str, Any]) -> str:
    """
    Converte uma spec OpenAPI normalizada para texto em linguagem natural.

    ## Para todos entenderem:
    Esta função pega a spec técnica e a transforma em texto
    que tanto humanos quanto IAs podem ler facilmente.

    O texto gerado pode ser passado diretamente ao LLM para
    que ele gere planos de teste.

    ## Parâmetros:
        spec: Especificação normalizada (output de parse_openapi)

    ## Retorna:
        String com descrição textual da API e seus endpoints.

    ## Exemplo de saída:
        ```
        API: User Management API
        URL Base: https://api.example.com

        Endpoints:

        - GET /users
          Resumo: List all users
          Parâmetros: page, limit
          Códigos de resposta: 200, 401

        - POST /users
          Resumo: Create new user
          Aceita corpo JSON
          Códigos de resposta: 201, 400
        ```

    ## Uso típico:
        >>> spec = parse_openapi("./api.yaml")
        >>> text = spec_to_requirement_text(spec)
        >>> plan = generate_utdl(requirement=text, base_url=spec["base_url"])
    """
    # Inicia com título e URL
    lines: list[str] = [f"API: {spec.get('title', 'API Desconhecida')}"]
    lines.append(f"URL Base: {spec.get('base_url', 'Não especificada')}")
    lines.append("")  # Linha em branco
    lines.append("Endpoints:")

    # Adiciona cada endpoint
    for endpoint in spec.get("endpoints", []):
        lines.append(f"\n- {endpoint['method']} {endpoint['path']}")

        if endpoint.get("summary"):
            lines.append(f"  Resumo: {endpoint['summary']}")

        if endpoint.get("parameters"):
            # Lista os nomes dos parâmetros
            params = ", ".join(p["name"] for p in endpoint["parameters"])
            lines.append(f"  Parâmetros: {params}")

        if endpoint.get("request_body"):
            lines.append("  Aceita corpo JSON")

        if endpoint.get("responses"):
            # Lista os códigos de resposta
            codes = ", ".join(endpoint["responses"].keys())
            lines.append(f"  Códigos de resposta: {codes}")

    return "\n".join(lines)
