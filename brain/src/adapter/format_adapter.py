"""
================================================================================
FORMAT ADAPTER — NORMALIZAÇÃO DE PLANOS UTDL
================================================================================

Este módulo implementa o SmartFormatAdapter, responsável por normalizar
diferentes formatos de planos de teste para o formato UTDL válido.

## Para todos entenderem:

O validador UTDL é muito rígido e exige uma estrutura exata:
- spec_version: "0.1"
- meta: { id, name }
- config: { base_url }
- steps: [{ id, action, params, assertions, extract }]

Qualquer desvio (ex: "tests" em vez de "steps") causa erro.

Este adaptador resolve o problema ao:
1. Mapear aliases conhecidos para os nomes corretos
2. Gerar campos obrigatórios ausentes (meta, config)
3. Normalizar assertions e extractions

## Aliases suportados:

### Root level:
- tests → steps
- scenarios → steps
- cases → steps

### Assertion type:
- status → status_code
- code → status_code
- body → json_body
- response_body → json_body

### Assertion fields:
- expected → value
- expect → value

### Extraction fields:
- from → source
- name → target
- as → target
- exports → extract

### HTTP params:
- url → path
- endpoint → path

"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

# Tentar importar yaml - é opcional
try:
    import yaml
    _yaml_available = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    _yaml_available = False

YAML_AVAILABLE: bool = _yaml_available


# =============================================================================
# CONSTANTES - MAPEAMENTO DE ALIASES
# =============================================================================

# Aliases para o campo de steps na raiz do plano
STEPS_ALIASES = {"tests", "scenarios", "cases", "test_cases"}

# Aliases para tipos de assertion
ASSERTION_TYPE_ALIASES = {
    "status": "status_code",
    "code": "status_code",
    "http_status": "status_code",
    "body": "json_body",
    "response_body": "json_body",
    "json": "json_body",
    "response_time": "latency",
    "duration": "latency",
    "time": "latency",
}

# Aliases para campos de assertion
ASSERTION_FIELD_ALIASES = {
    "expected": "value",
    "expect": "value",
    "expected_value": "value",
}

# Aliases para campos de extraction
EXTRACTION_FIELD_ALIASES = {
    "from": "source",
    "name": "target",
    "as": "target",
    "variable": "target",
    "var": "target",
    "to": "target",
    "json_path": "path",
    "jsonpath": "path",
}

# Aliases para campos de params HTTP
HTTP_PARAMS_ALIASES: dict[str, str | None] = {
    "url": "path",
    "endpoint": "path",
    "uri": "path",
    "http": None,  # Indica que deve ser expandido
}


# =============================================================================
# CLASSE PRINCIPAL
# =============================================================================

class SmartFormatAdapter:
    """
    Adaptador inteligente que normaliza diferentes formatos para UTDL válido.

    ## Responsabilidades:
    1. Mapear aliases de campos para nomes UTDL corretos
    2. Gerar campos obrigatórios ausentes (spec_version, meta, config)
    3. Normalizar estrutura de steps, assertions e extractions
    4. Remover BOM UTF-8 de arquivos
    5. Suportar entrada em JSON ou YAML

    ## Uso:

    ```python
    adapter = SmartFormatAdapter()

    # Normalizar dict
    normalized = adapter.normalize(raw_dict)

    # Carregar e normalizar arquivo
    normalized = adapter.load_and_normalize("path/to/plan.json")
    normalized = adapter.load_and_normalize("path/to/plan.yaml")
    ```
    """

    def __init__(self) -> None:
        """Inicializa o adaptador."""
        pass  # Sem estado, mas deixamos método para extensibilidade futura

    def normalize(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Normaliza um plano para formato UTDL válido.

        Args:
            plan: Dicionário com o plano (pode ter formato alternativo)

        Returns:
            Dicionário normalizado no formato UTDL válido

        Raises:
            ValueError: Se não houver steps/tests no plano
        """
        # Cria cópia para não modificar original
        result: dict[str, Any] = {}

        # 1. Garantir spec_version
        result["spec_version"] = plan.get("spec_version", "0.1")

        # 2. Garantir meta
        result["meta"] = self._normalize_meta(plan.get("meta"))

        # 3. Garantir config
        result["config"] = self._normalize_config(plan)

        # 4. Normalizar steps (pode vir como tests, scenarios, etc.)
        steps = self._extract_steps(plan)
        if not steps:
            raise ValueError(
                "Plano inválido: campo 'steps' (ou 'tests') é obrigatório e não pode estar vazio"
            )
        result["steps"] = [self._normalize_step(step) for step in steps]

        return result

    def load_and_normalize(self, path: str | Path) -> dict[str, Any]:
        """
        Carrega um arquivo e normaliza para formato UTDL.

        Suporta arquivos JSON e YAML.
        Remove automaticamente BOM UTF-8 se presente.

        Args:
            path: Caminho para o arquivo (JSON ou YAML)

        Returns:
            Dicionário normalizado no formato UTDL válido

        Raises:
            FileNotFoundError: Se o arquivo não existir
            ValueError: Se o formato não for suportado ou conteúdo inválido
        """
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        # Lê conteúdo removendo BOM
        content = self._read_file_without_bom(file_path)

        # Detecta formato pelo conteúdo ou extensão
        data = self._parse_content(content, file_path.suffix.lower())

        if not isinstance(data, dict):
            raise ValueError(f"Conteúdo do arquivo deve ser um objeto/dict, não {type(data).__name__}")

        # Cast explícito para satisfazer type checker
        plan_data = cast(dict[str, Any], data)
        return self.normalize(plan_data)

    # =========================================================================
    # MÉTODOS PRIVADOS - NORMALIZAÇÃO
    # =========================================================================

    def _normalize_meta(self, meta: dict[str, Any] | None) -> dict[str, Any]:
        """
        Normaliza ou gera o campo meta.

        Se meta não existir ou estiver incompleto, gera valores padrão.
        """
        if meta is None:
            meta = {}

        return {
            "id": meta.get("id", str(uuid.uuid4())),
            "name": meta.get("name", "Auto-generated Test Plan"),
            "description": meta.get("description"),
            "tags": meta.get("tags", []),
            "created_at": meta.get("created_at", datetime.now(timezone.utc).isoformat()),
        }

    def _normalize_config(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Normaliza ou gera o campo config.

        Pode extrair base_url do nível raiz se config não existir.
        """
        config = plan.get("config", {})

        # base_url pode estar na raiz ou em config
        base_url = config.get("base_url") or plan.get("base_url", "https://api.example.com")

        return {
            "base_url": base_url,
            "timeout_ms": config.get("timeout_ms", 30000),
            "global_headers": config.get("global_headers", {}),
            "variables": config.get("variables", {}),
        }

    def _extract_steps(self, plan: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extrai steps do plano, verificando aliases.

        Verifica: steps, tests, scenarios, cases
        """
        # Primeiro tenta "steps" (nome correto)
        if "steps" in plan:
            return plan["steps"]

        # Tenta aliases
        for alias in STEPS_ALIASES:
            if alias in plan:
                return plan[alias]

        return []

    def _normalize_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """
        Normaliza um step individual.

        Trata casos como:
        - Step com 'http' em vez de 'action' + 'params'
        - Assertions com aliases
        - Extractions com aliases (ou 'exports')
        """
        result: dict[str, Any] = {}

        # ID do step
        result["id"] = step.get("id", str(uuid.uuid4()))

        # Description
        if "description" in step:
            result["description"] = step["description"]

        # depends_on
        if "depends_on" in step:
            result["depends_on"] = step["depends_on"]

        # Action e Params - pode vir como 'http' direto ou action como dict
        if "http" in step:
            result["action"] = "http_request"
            result["params"] = self._normalize_http_params(step["http"])
        elif "action" in step:
            action = step["action"]
            # Caso 1: action é um dicionário (formato antigo)
            # Ex: {"type": "http", "method": "GET", "endpoint": "/users"}
            if isinstance(action, dict):
                action_type = action.get("type", "http")
                if action_type in ("http", "http_request"):
                    result["action"] = "http_request"
                    result["params"] = self._normalize_http_params(action)
                else:
                    # Outros tipos de action como context, wait, etc.
                    result["action"] = action_type
                    result["params"] = {k: v for k, v in action.items() if k != "type"}
            # Caso 2: action é uma string (formato UTDL correto)
            else:
                result["action"] = action
                result["params"] = self._normalize_params(step.get("params", {}), action)
        else:
            # Tenta inferir de outros campos
            if "method" in step or "path" in step:
                result["action"] = "http_request"
                result["params"] = self._normalize_http_params(step)
            else:
                result["action"] = step.get("action", "http_request")
                result["params"] = step.get("params", {})

        # Assertions - pode vir como 'assertions' (array) ou 'expected' (dict no formato antigo)
        assertions = step.get("assertions", [])
        expected = step.get("expected", {})
        
        # Converte 'expected' dict para array de assertions
        if expected and not assertions:
            assertions = self._convert_expected_to_assertions(expected)
        
        if assertions:
            result["assertions"] = [self._normalize_assertion(a) for a in assertions]

        # Extract/Exports
        extractions: list[dict[str, Any]] = (
            step.get("extract") or step.get("exports") or step.get("extractions") or []
        )
        if extractions:
            result["extract"] = [self._normalize_extraction(e) for e in extractions]

        # Recovery policy
        if "recovery_policy" in step:
            result["recovery_policy"] = step["recovery_policy"]
        elif "recovery" in step:
            result["recovery_policy"] = step["recovery"]

        return result

    def _normalize_http_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Normaliza parâmetros de requisição HTTP.

        Aliases suportados:
        - url, endpoint, uri → path
        """
        result: dict[str, Any] = {}

        # Method (obrigatório)
        result["method"] = params.get("method", "GET").upper()

        # Path (pode vir como url, endpoint, uri)
        path = (
            params.get("path")
            or params.get("url")
            or params.get("endpoint")
            or params.get("uri")
            or "/"
        )
        result["path"] = path

        # Headers (opcional)
        if "headers" in params:
            result["headers"] = params["headers"]

        # Body (opcional)
        if "body" in params:
            result["body"] = params["body"]
        elif "data" in params:
            result["body"] = params["data"]
        elif "json" in params:
            result["body"] = params["json"]

        # Query params (opcional)
        if "query" in params:
            result["query"] = params["query"]
        elif "query_params" in params:
            result["query"] = params["query_params"]

        return result

    def _convert_expected_to_assertions(self, expected: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Converte formato antigo 'expected' para array de assertions UTDL.
        
        Formato antigo:
            {"status_code": 200, "status": 200}
        
        Formato UTDL:
            [{"type": "status_code", "operator": "eq", "value": 200}]
        """
        assertions: list[dict[str, Any]] = []
        
        # Status code - pode vir como status_code ou status
        status = expected.get("status_code") or expected.get("status")
        if status is not None:
            assertions.append({
                "type": "status_code",
                "operator": "eq",
                "value": status,
            })
        
        # Body/JSON assertions
        if "body" in expected:
            body_val = expected["body"]
            if isinstance(body_val, dict):
                # Body com path específico
                assertions.append({
                    "type": "json_body",
                    "operator": "eq",
                    "value": body_val,
                })
            else:
                assertions.append({
                    "type": "body",
                    "operator": "contains",
                    "value": body_val,
                })
        
        # Headers
        if "headers" in expected:
            for header_name, header_value in expected["headers"].items():
                assertions.append({
                    "type": "header",
                    "operator": "eq",
                    "path": header_name,
                    "value": header_value,
                })
        
        return assertions

    def _normalize_params(self, params: dict[str, Any], action: str) -> dict[str, Any]:
        """
        Normaliza params baseado no tipo de action.
        """
        if action == "http_request":
            return self._normalize_http_params(params)
        elif action in ("wait", "sleep"):
            return {
                "duration_ms": params.get("duration_ms") or params.get("ms") or params.get("duration", 1000)
            }
        return params

    def _normalize_assertion(self, assertion: dict[str, Any]) -> dict[str, Any]:
        """
        Normaliza uma assertion individual.

        Aliases suportados:
        - type: status → status_code, body → json_body
        - fields: expected → value
        """
        result: dict[str, Any] = {}

        # Type - aplicar aliases
        raw_type = assertion.get("type", "status_code")
        result["type"] = ASSERTION_TYPE_ALIASES.get(raw_type, raw_type)

        # Operator (padrão: eq)
        result["operator"] = assertion.get("operator", "eq")

        # Value - pode vir como 'expected' ou 'expect'
        value = (
            assertion.get("value")
            if "value" in assertion
            else assertion.get("expected")
            if "expected" in assertion
            else assertion.get("expect")
        )
        if value is not None:
            result["value"] = value

        # Path (para json_body e header)
        if "path" in assertion:
            result["path"] = assertion["path"]
        elif "name" in assertion and result["type"] == "header":
            # Para header, 'name' pode ser usado como path
            result["path"] = assertion["name"]

        return result

    def _normalize_extraction(self, extraction: dict[str, Any]) -> dict[str, Any]:
        """
        Normaliza uma extraction individual.

        Aliases suportados:
        - from → source
        - name, as, to, variable → target
        - json_path, jsonpath → path
        """
        result: dict[str, Any] = {}

        # Source - pode vir como 'from'
        source = extraction.get("source") or extraction.get("from", "body")
        result["source"] = source

        # Path
        path = extraction.get("path") or extraction.get("json_path") or extraction.get("jsonpath")
        if path:
            result["path"] = path

        # Target - pode vir como 'name', 'as', 'to', 'variable'
        target = (
            extraction.get("target")
            or extraction.get("name")
            or extraction.get("as")
            or extraction.get("to")
            or extraction.get("variable")
            or extraction.get("var")
        )
        if target:
            result["target"] = target
        else:
            # Gera nome baseado no path se não especificado
            result["target"] = f"extracted_{uuid.uuid4().hex[:8]}"

        # Campos opcionais
        if extraction.get("all_values"):
            result["all_values"] = True
        if extraction.get("critical"):
            result["critical"] = True
        if extraction.get("regex"):
            result["regex"] = extraction["regex"]

        return result

    # =========================================================================
    # MÉTODOS PRIVADOS - I/O
    # =========================================================================

    def _read_file_without_bom(self, path: Path) -> str:
        """
        Lê arquivo removendo BOM UTF-8 se presente.

        BOM (Byte Order Mark) é um caractere invisível que alguns editores
        adicionam no início de arquivos UTF-8. Isso pode causar erros de parsing.
        """
        content = path.read_text(encoding="utf-8-sig")  # utf-8-sig remove BOM automaticamente
        return content

    def _parse_content(self, content: str, extension: str) -> Any:
        """
        Faz parse do conteúdo baseado na extensão ou detecta formato.

        Args:
            content: Conteúdo do arquivo
            extension: Extensão do arquivo (com ponto, ex: ".json")

        Returns:
            Dados parseados (dict ou list)
        """
        content = content.strip()

        # Tenta JSON primeiro (mais comum)
        if extension in (".json",) or content.startswith("{") or content.startswith("["):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass  # Tenta YAML se JSON falhar

        # Tenta YAML
        if extension in (".yaml", ".yml") or (YAML_AVAILABLE and not content.startswith("{")):
            if not YAML_AVAILABLE or yaml is None:
                raise ValueError(
                    "Arquivo YAML detectado, mas PyYAML não está instalado. "
                    "Instale com: pip install pyyaml"
                )
            try:
                return yaml.safe_load(content)
            except Exception as e:
                raise ValueError(f"Erro ao parsear YAML: {e}")

        # Última tentativa: JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Erro ao parsear JSON: {e}")


# =============================================================================
# FUNÇÃO DE CONVENIÊNCIA
# =============================================================================

def normalize_plan(plan_or_path: dict[str, Any] | str | Path) -> dict[str, Any]:
    """
    Função de conveniência para normalizar planos.

    Aceita dict ou caminho para arquivo.

    Args:
        plan_or_path: Dicionário com plano ou caminho para arquivo

    Returns:
        Dicionário normalizado no formato UTDL válido

    Examples:
        >>> # Com dict
        >>> plan = normalize_plan({"tests": [...]})

        >>> # Com arquivo
        >>> plan = normalize_plan("path/to/plan.json")
    """
    adapter = SmartFormatAdapter()

    if isinstance(plan_or_path, dict):
        return adapter.normalize(plan_or_path)
    else:
        return adapter.load_and_normalize(plan_or_path)
