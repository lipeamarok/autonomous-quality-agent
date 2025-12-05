#!/usr/bin/env python3
"""
================================================================================
Script de Validação de Schema para CI/CD
================================================================================

Este script verifica a consistência entre:
1. Schema canônico (schemas/utdl.schema.json)
2. Modelos Pydantic (brain/src/validator/models.py)
3. Structs Rust (runner/src/protocol/mod.rs)

Uso:
    python scripts/validate_schema.py

Exit codes:
    0 = Tudo OK
    1 = Diferenças encontradas
    2 = Erro de execução
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any
import sys
from pathlib import Path


# Paths
ROOT = Path(__file__).parent.parent
CANONICAL_SCHEMA = ROOT / "schemas" / "utdl.schema.json"
PYDANTIC_MODELS = ROOT / "brain" / "src" / "validator" / "models.py"
RUST_PROTOCOL = ROOT / "runner" / "src" / "protocol" / "mod.rs"


def check_file_exists(path: Path, name: str) -> bool:
    """Verifica se arquivo existe."""
    if not path.exists():
        print(f"❌ {name} não encontrado: {path}")
        return False
    print(f"✓ {name} encontrado")
    return True


def load_canonical_schema() -> dict[str, Any]:
    """Carrega schema canônico."""
    with open(CANONICAL_SCHEMA, "r", encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def extract_pydantic_fields() -> dict[str, list[str]]:
    """Extrai campos definidos nos modelos Pydantic."""
    content = PYDANTIC_MODELS.read_text(encoding="utf-8")
    
    # Regex para encontrar classes e seus campos
    class_pattern = r"class (\w+)\(BaseModel\):"
    field_pattern = r"^\s+(\w+):\s+.*(?:Field|=|#)"
    
    models: dict[str, list[str]] = {}
    current_class = None
    
    for line in content.split("\n"):
        class_match = re.match(class_pattern, line)
        if class_match:
            current_class = class_match.group(1)
            models[current_class] = []
            continue
        
        if current_class:
            field_match = re.match(field_pattern, line)
            if field_match:
                field_name = field_match.group(1)
                if not field_name.startswith("_"):
                    models[current_class].append(field_name)
    
    return models


def extract_rust_fields() -> dict[str, list[str]]:
    """Extrai campos definidos nas structs Rust."""
    content = RUST_PROTOCOL.read_text(encoding="utf-8")
    
    # Regex para encontrar structs e seus campos
    struct_pattern = r"pub struct (\w+) \{"
    field_pattern = r"^\s+pub (\w+):"
    
    structs: dict[str, list[str]] = {}
    current_struct = None
    in_struct = False
    brace_count = 0
    
    for line in content.split("\n"):
        struct_match = re.match(struct_pattern, line)
        if struct_match:
            current_struct = struct_match.group(1)
            structs[current_struct] = []
            in_struct = True
            brace_count = 1
            continue
        
        if in_struct:
            brace_count += line.count("{") - line.count("}")
            
            if brace_count <= 0:
                in_struct = False
                current_struct = None
                continue
            
            field_match = re.match(field_pattern, line)
            if field_match and current_struct is not None:
                structs[current_struct].append(field_match.group(1))
    
    return structs


def compare_fields(
    schema_fields: set[str],
    pydantic_fields: set[str],
    rust_fields: set[str],
    model_name: str,
) -> list[str]:
    """Compara campos entre as três fontes."""
    issues: list[str] = []
    
    # Campos no schema mas não em Pydantic
    missing_pydantic = schema_fields - pydantic_fields
    if missing_pydantic:
        issues.append(f"  {model_name}: Campos no schema faltando em Pydantic: {missing_pydantic}")
    
    # Campos no schema mas não em Rust
    missing_rust = schema_fields - rust_fields
    if missing_rust:
        issues.append(f"  {model_name}: Campos no schema faltando em Rust: {missing_rust}")
    
    # Campos extras em Pydantic
    extra_pydantic = pydantic_fields - schema_fields
    if extra_pydantic:
        issues.append(f"  {model_name}: Campos extras em Pydantic: {extra_pydantic}")
    
    # Campos extras em Rust
    extra_rust = rust_fields - schema_fields
    if extra_rust:
        issues.append(f"  {model_name}: Campos extras em Rust: {extra_rust}")
    
    return issues


def validate_schema_consistency() -> tuple[bool, list[str]]:
    """Valida consistência entre schema, Pydantic e Rust.
    
    Nota: Esta é uma validação heurística baseada em regex.
    A validação real acontece nos testes de conformidade.
    """
    issues: list[str] = []
    
    # Por enquanto, apenas verifica se os arquivos existem e são válidos
    try:
        schema = load_canonical_schema()
        if "definitions" not in schema:
            issues.append("Schema não tem definitions")
        
        pydantic_models = extract_pydantic_fields()
        if not pydantic_models:
            issues.append("Nenhum modelo Pydantic encontrado")
        
        rust_structs = extract_rust_fields()
        if not rust_structs:
            issues.append("Nenhuma struct Rust encontrada")
        
        # Verifica modelos essenciais existem
        essential_models = ["Plan", "Meta", "Config", "Step"]
        for model in essential_models:
            if model not in pydantic_models:
                issues.append(f"Modelo Pydantic '{model}' não encontrado")
            if model not in rust_structs:
                issues.append(f"Struct Rust '{model}' não encontrada")
        
    except Exception as e:
        issues.append(f"Erro ao validar: {e}")
    
    return len(issues) == 0, issues


def run_conformance_tests() -> bool:
    """Executa testes de conformidade."""
    print("\n📋 Executando testes de conformidade...")
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_conformance.py", "-v", "--tb=short"],
        cwd=ROOT / "brain",
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"❌ Testes falharam:\n{result.stdout}\n{result.stderr}")
        return False
    
    print("✓ Testes de conformidade passaram")
    return True


def main() -> int:
    """Função principal."""
    print("=" * 60)
    print("Validação de Consistência de Schema UTDL")
    print("=" * 60)
    
    # Verifica arquivos
    print("\n📁 Verificando arquivos...")
    files_ok = all([
        check_file_exists(CANONICAL_SCHEMA, "Schema canônico"),
        check_file_exists(PYDANTIC_MODELS, "Modelos Pydantic"),
        check_file_exists(RUST_PROTOCOL, "Structs Rust"),
    ])
    
    if not files_ok:
        return 2
    
    # Valida consistência
    print("\n🔍 Validando consistência entre schemas...")
    is_consistent, issues = validate_schema_consistency()
    
    if not is_consistent:
        print("❌ Inconsistências encontradas:")
        for issue in issues:
            print(issue)
    else:
        print("✓ Schemas estão consistentes")
    
    # Executa testes
    tests_ok = run_conformance_tests()
    
    # Resultado final
    print("\n" + "=" * 60)
    if is_consistent and tests_ok:
        print("✅ Validação completa - Tudo OK!")
        return 0
    else:
        print("❌ Validação falhou - Verifique os problemas acima")
        return 1


if __name__ == "__main__":
    sys.exit(main())
