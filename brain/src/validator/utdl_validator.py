"""
================================================================================
VALIDADOR UTDL INDEPENDENTE
================================================================================

Este módulo fornece validação de planos UTDL desacoplada do Generator.
Permite reutilização em CLI, editor, ou qualquer outro contexto.

## Para todos entenderem:

Imagine que você é um revisor de documentos. O Generator é quem escreve
os documentos, mas você (Validator) é quem verifica se estão corretos.

Separar essas responsabilidades permite:
- Validar planos de qualquer fonte (não só do LLM)
- Reutilizar validação em diferentes contextos
- Testar validação isoladamente

## Diferenças de validação:

| Quem        | O que valida                           |
|-------------|----------------------------------------|
| Brain       | Estrutura Pydantic, campos obrigatórios|
| Runner      | Semântica, dependências, DAG válido    |

## Exemplo de uso:

    >>> from brain.src.validator.utdl_validator import UTDLValidator
    >>> validator = UTDLValidator()
    >>> result = validator.validate(plan_dict)
    >>> if result.is_valid:
    ...     print("Plano válido!")
    ... else:
    ...     for error in result.errors:
    ...         print(f"Erro: {error}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .models import Plan, Step


@dataclass
class ValidationResult:
    """
    Resultado da validação de um plano UTDL.

    ## Atributos:

    - `is_valid`: True se o plano passou em todas as validações
    - `errors`: Lista de erros encontrados (strings descritivas)
    - `warnings`: Lista de avisos (não impedem uso, mas merecem atenção)
    - `plan`: O plano validado (se válido, None se inválido)

    ## Exemplo:

        >>> result = validator.validate(plan_dict)
        >>> if not result.is_valid:
        ...     print(f"Encontrados {len(result.errors)} erros")
    """
    is_valid: bool
    errors: list[str] = field(default_factory=lambda: [])
    warnings: list[str] = field(default_factory=lambda: [])
    plan: Plan | None = None


class UTDLValidator:
    """
    Validador independente de planos UTDL.

    Este validador realiza validações estruturais usando Pydantic,
    além de validações semânticas adicionais.

    ## Validações realizadas:

    1. **Estrutura Pydantic**: Campos obrigatórios, tipos corretos
    2. **Dependências existem**: depends_on referencia steps válidos
    3. **Sem ciclos**: Detecta dependências circulares
    4. **IDs únicos**: Cada step tem ID único
    5. **Spec version**: Versão do formato é suportada

    ## Exemplo:

        >>> validator = UTDLValidator(strict=True)
        >>> result = validator.validate({"spec_version": "0.1", ...})
    """

    SUPPORTED_SPEC_VERSIONS = {"0.1"}
    VALID_ACTIONS = {"http_request", "wait", "sleep"}

    def __init__(self, strict: bool = False):
        """
        Inicializa o validador.

        ## Parâmetros:

        - `strict`: Se True, trata warnings como erros
        """
        self.strict = strict

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """
        Valida um plano UTDL.

        ## Parâmetros:

        - `data`: Dicionário com o plano UTDL

        ## Retorno:

        ValidationResult com status, erros e warnings.

        ## Exemplo:

            >>> result = validator.validate(plan_dict)
            >>> print(result.is_valid)
            True
        """
        errors: list[str] = []
        warnings: list[str] = []
        plan: Plan | None = None

        # =====================================================================
        # VALIDAÇÃO ESTRUTURAL (Pydantic)
        # =====================================================================

        try:
            plan = Plan(**data)
        except ValidationError as e:
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                errors.append(f"[{loc}] {msg}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # =====================================================================
        # VALIDAÇÃO DE SPEC_VERSION
        # =====================================================================

        if plan.spec_version not in self.SUPPORTED_SPEC_VERSIONS:
            errors.append(
                f"spec_version '{plan.spec_version}' não suportada. "
                f"Versões válidas: {self.SUPPORTED_SPEC_VERSIONS}"
            )

        # =====================================================================
        # VALIDAÇÃO DE STEPS
        # =====================================================================

        step_ids = {step.id for step in plan.steps}

        # Verifica IDs únicos
        if len(step_ids) != len(plan.steps):
            seen: set[str] = set()
            duplicates: list[str] = []
            for step in plan.steps:
                if step.id in seen:
                    duplicates.append(step.id)
                seen.add(step.id)
            errors.append(f"IDs de steps duplicados: {duplicates}")

        # Verifica dependências e ciclos
        for step in plan.steps:
            # Dependências existem?
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        f"Step '{step.id}': dependência '{dep}' não existe no plano"
                    )

            # Auto-referência?
            if step.id in step.depends_on:
                errors.append(f"Step '{step.id}': auto-referência em depends_on")

            # Action válida?
            if step.action not in self.VALID_ACTIONS:
                warnings.append(
                    f"Step '{step.id}': action '{step.action}' não é padrão. "
                    f"Actions válidas: {self.VALID_ACTIONS}"
                )

        # Detecta ciclos complexos
        cycle_errors = self._detect_cycles(plan.steps)
        errors.extend(cycle_errors)

        # =====================================================================
        # VALIDAÇÃO DE PLANO VAZIO
        # =====================================================================

        if not plan.steps:
            errors.append("Plano não tem nenhum step definido")

        # =====================================================================
        # RESULTADO FINAL
        # =====================================================================

        if self.strict and warnings:
            errors.extend([f"[strict] {w}" for w in warnings])
            warnings = []

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            plan=plan if is_valid else None,
        )

    def _detect_cycles(self, steps: list[Step]) -> list[str]:
        """
        Detecta ciclos no grafo de dependências usando DFS.

        ## Algoritmo:

        Usa coloração de nós:
        - 0 (branco): Não visitado
        - 1 (cinza): Em processamento
        - 2 (preto): Completo

        Se encontrar nó cinza durante DFS = ciclo!
        """
        errors: list[str] = []

        # Constrói grafo de dependências
        graph: dict[str, list[str]] = {step.id: step.depends_on for step in steps}
        color: dict[str, int] = {step.id: 0 for step in steps}

        def dfs(node: str) -> bool:
            """Retorna True se encontrou ciclo."""
            color[node] = 1  # Marca como em processamento

            for dep in graph.get(node, []):
                if dep not in color:
                    continue  # Dependência não existe (já reportado)
                if color[dep] == 1:
                    errors.append(f"Dependência circular detectada: {node} → {dep}")
                    return True
                if color[dep] == 0:
                    if dfs(dep):
                        return True

            color[node] = 2  # Marca como completo
            return False

        for step_id in graph:
            if color[step_id] == 0:
                dfs(step_id)

        return errors

    def validate_json(self, json_str: str) -> ValidationResult:
        """
        Valida um plano UTDL a partir de string JSON.

        ## Parâmetros:

        - `json_str`: String JSON do plano

        ## Retorno:

        ValidationResult com status, erros e warnings.
        """
        import json

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"JSON inválido: {e}"],
            )

        return self.validate(data)
