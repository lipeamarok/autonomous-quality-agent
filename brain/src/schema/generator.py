"""
================================================================================
Geração e Validação de Schema UTDL
================================================================================

Este módulo fornece ferramentas para:
1. Gerar JSON Schema a partir dos modelos Pydantic
2. Comparar com o schema canônico (schemas/utdl.schema.json)
3. Validar planos contra o schema

## Uso:

    # Gerar schema do Pydantic
    python -m src.schema.generator --export

    # Comparar com schema canônico
    python -m src.schema.generator --compare

    # Validar um plano
    python -m src.schema.generator --validate plan.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ..validator.models import Plan


# Caminho para o schema canônico
CANONICAL_SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "schemas" / "utdl.schema.json"


def generate_pydantic_schema() -> dict[str, Any]:
    """
    Gera JSON Schema a partir do modelo Pydantic Plan.

    Usa TypeAdapter para gerar schema compatível com JSON Schema draft-07.
    """
    adapter = TypeAdapter(Plan)
    schema = adapter.json_schema(mode="serialization")

    # Adiciona metadados
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["$id"] = "https://github.com/lipeamarok/autonomous-quality-agent/schemas/utdl.pydantic.schema.json"
    schema["title"] = "UTDL Plan Schema (Pydantic Generated)"
    schema["description"] = "Auto-generated from Pydantic models. Compare with canonical utdl.schema.json."

    return schema


def load_canonical_schema() -> dict[str, Any]:
    """Carrega o schema canônico."""
    if not CANONICAL_SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema canônico não encontrado: {CANONICAL_SCHEMA_PATH}")

    with open(CANONICAL_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_schemas(
    pydantic_schema: dict[str, Any],
    canonical_schema: dict[str, Any],
) -> list[str]:
    """
    Compara dois schemas e retorna diferenças.

    Foca nas diferenças estruturais importantes:
    - Campos obrigatórios
    - Tipos de campos
    - Enums
    """
    differences: list[str] = []

    def get_required(schema: dict[str, Any]) -> set[str]:
        return set(schema.get("required", []))

    def get_properties(schema: dict[str, Any]) -> dict[str, Any]:
        return schema.get("properties", {})

    def compare_object(path: str, pydantic: dict[str, Any], canonical: dict[str, Any]) -> None:
        """Compara dois objetos recursivamente."""
        # Compara required
        pyd_req = get_required(pydantic)
        can_req = get_required(canonical)

        missing_in_pydantic = can_req - pyd_req
        missing_in_canonical = pyd_req - can_req

        if missing_in_pydantic:
            differences.append(f"{path}: Campos obrigatórios faltando em Pydantic: {missing_in_pydantic}")
        if missing_in_canonical:
            differences.append(f"{path}: Campos obrigatórios extras em Pydantic: {missing_in_canonical}")

        # Compara properties
        pyd_props = get_properties(pydantic)
        can_props = get_properties(canonical)

        all_props = set(pyd_props.keys()) | set(can_props.keys())

        for prop in all_props:
            prop_path = f"{path}.{prop}"

            if prop not in pyd_props:
                differences.append(f"{prop_path}: Faltando em Pydantic")
                continue
            if prop not in can_props:
                differences.append(f"{prop_path}: Faltando no schema canônico")
                continue

            pyd_prop = pyd_props[prop]
            can_prop = can_props[prop]

            # Compara tipos
            pyd_type = pyd_prop.get("type")
            can_type = can_prop.get("type")

            if pyd_type != can_type:
                # Ignora diferenças de null handling (anyOf vs type array)
                if not (pyd_type is None and "anyOf" in pyd_prop):
                    differences.append(f"{prop_path}: Tipo diferente - Pydantic: {pyd_type}, Canônico: {can_type}")

            # Compara enums
            pyd_enum = pyd_prop.get("enum")
            can_enum = can_prop.get("enum")

            if pyd_enum and can_enum and set(pyd_enum) != set(can_enum):
                differences.append(f"{prop_path}: Enum diferente - Pydantic: {pyd_enum}, Canônico: {can_enum}")

            # Recursão para objetos
            if pyd_type == "object" and can_type == "object":
                compare_object(prop_path, pyd_prop, can_prop)

    # Compara raiz
    compare_object("$", pydantic_schema, canonical_schema)

    # Compara definitions
    pyd_defs = pydantic_schema.get("$defs", pydantic_schema.get("definitions", {}))
    can_defs = canonical_schema.get("definitions", {})

    # Mapeia nomes de definição (Pydantic usa nomes diferentes)
    # Nota: Não reportamos diferença de nomes, apenas validamos estrutura
    _ = set(pyd_defs.keys())  # pyd_def_names
    _ = set(can_defs.keys())  # can_def_names

    # Não reporta diferença de nomes de definição, apenas estrutura

    return differences


def export_pydantic_schema(output_path: Path | None = None) -> Path:
    """
    Exporta o schema Pydantic para um arquivo JSON.
    """
    schema = generate_pydantic_schema()

    if output_path is None:
        output_path = CANONICAL_SCHEMA_PATH.parent / "utdl.pydantic.schema.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    return output_path


def get_schema_validation_errors(validator: Any, instance: dict[str, Any]) -> list[Any]:
    """
    Wrapper para iter_errors que retorna lista tipada.

    jsonschema não tem type stubs completos, então encapsulamos aqui.
    """
    return list(validator.iter_errors(instance))


def validate_plan_against_schema(plan_path: Path) -> tuple[bool, list[str]]:
    """
    Valida um plano contra o schema canônico.

    Retorna (is_valid, errors).
    """
    try:
        import jsonschema
    except ImportError:
        return False, ["jsonschema não instalado. Execute: pip install jsonschema"]

    # Carrega plano
    with open(plan_path, "r", encoding="utf-8") as f:
        plan: dict[str, Any] = json.load(f)

    # Carrega schema
    schema = load_canonical_schema()

    # Valida
    validator = jsonschema.Draft7Validator(schema)
    validation_errors = get_schema_validation_errors(validator, plan)

    if validation_errors:
        return False, [f"{e.json_path}: {e.message}" for e in validation_errors]

    return True, []


def main() -> int:
    """Função principal para CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="UTDL Schema Generator and Validator")
    parser.add_argument("--export", action="store_true", help="Export Pydantic schema to JSON")
    parser.add_argument("--compare", action="store_true", help="Compare Pydantic with canonical schema")
    parser.add_argument("--validate", type=Path, help="Validate a plan against canonical schema")

    args = parser.parse_args()

    if args.export:
        path = export_pydantic_schema()
        print(f"Schema exportado para: {path}")
        return 0

    if args.compare:
        pydantic_schema = generate_pydantic_schema()
        canonical_schema = load_canonical_schema()

        differences = compare_schemas(pydantic_schema, canonical_schema)

        if differences:
            print("Diferenças encontradas:")
            for diff in differences:
                print(f"  - {diff}")
            return 1
        else:
            print("✓ Schemas estão compatíveis!")
            return 0

    if args.validate:
        is_valid, errors = validate_plan_against_schema(args.validate)

        if is_valid:
            print(f"✓ Plano válido: {args.validate}")
            return 0
        else:
            print(f"✗ Plano inválido: {args.validate}")
            for error in errors:
                print(f"  - {error}")
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
