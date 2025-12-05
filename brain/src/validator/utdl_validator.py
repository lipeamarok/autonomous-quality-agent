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

## Modos de Validação:

| Modo       | Comportamento                              |
|------------|-------------------------------------------|
| strict     | Warnings viram erros, planos parciais falham |
| lenient    | Warnings ignorados, planos parciais passam |
| default    | Warnings reportados, erros bloqueiam       |

## Diferenças de validação:

| Quem        | O que valida                           |
|-------------|----------------------------------------|
| Brain       | Estrutura Pydantic, campos obrigatórios|
| Runner      | Semântica, dependências, DAG válido    |

## Exemplo de uso:

    >>> from brain.src.validator.utdl_validator import UTDLValidator, ValidationMode
    >>> validator = UTDLValidator(mode=ValidationMode.LENIENT)
    >>> result = validator.validate(plan_dict)
    >>> if result.is_valid:
    ...     print("Plano válido!")
    ... else:
    ...     for error in result.errors:
    ...         print(f"Erro: {error}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Importa sistema de erros estruturados (opcional, para compatibilidade)
try:
    from ..errors import (
        StructuredError,
        ValidationError as StructuredValidationError,
        ErrorCodes,
        ExecutionLimits,
        validate_plan_limits,
        Severity,
    )
    HAS_STRUCTURED_ERRORS = True
except ImportError:
    HAS_STRUCTURED_ERRORS = False

from pydantic import ValidationError

from .models import Plan, Step


class ValidationMode(Enum):
    """
    Modos de validação para planos UTDL.

    ## Modos disponíveis:

    - `STRICT`: Máxima rigidez. Qualquer warning vira erro.
      Use para produção, CI/CD, ou quando planos devem ser perfeitos.

    - `DEFAULT`: Modo padrão. Erros bloqueiam, warnings são reportados.
      Use para desenvolvimento normal.

    - `LENIENT`: Máxima tolerância. Planos parciais são aceitos.
      Use para prototipagem rápida, debugging, ou quando o LLM
      ainda está "aprendendo" a gerar planos corretos.

    ## Quando usar cada modo:

    ```python
    # CI/CD - nada passa se tiver warnings
    validator = UTDLValidator(mode=ValidationMode.STRICT)

    # Desenvolvimento normal
    validator = UTDLValidator()  # default

    # Prototipagem - aceita planos imperfeitos
    validator = UTDLValidator(mode=ValidationMode.LENIENT)
    ```
    """
    STRICT = "strict"
    DEFAULT = "default"
    LENIENT = "lenient"


@dataclass
class ValidationResult:
    """
    Resultado da validação de um plano UTDL.

    ## Atributos:

    - `is_valid`: True se o plano passou em todas as validações
    - `errors`: Lista de erros encontrados (strings descritivas)
    - `warnings`: Lista de avisos (não impedem uso, mas merecem atenção)
    - `plan`: O plano validado (se válido, None se inválido)
    - `structured_errors`: Lista de erros estruturados (com path e sugestões)

    ## Exemplo:

        >>> result = validator.validate(plan_dict)
        >>> if not result.is_valid:
        ...     print(f"Encontrados {len(result.errors)} erros")
    """
    is_valid: bool
    errors: list[str] = field(default_factory=lambda: [])
    warnings: list[str] = field(default_factory=lambda: [])
    plan: Plan | None = None
    structured_errors: list[Any] = field(default_factory=lambda: [])

    def get_errors_with_paths(self) -> list[dict[str, Any]]:
        """
        Retorna erros com paths JSON para localização exata.

        ## Retorno:

        Lista de dicts com 'message', 'path', 'suggestion'.
        """
        if self.structured_errors:
            return [e.to_dict() for e in self.structured_errors]

        # Fallback para erros legados (sem path)
        return [{"message": e, "path": None, "suggestion": None} for e in self.errors]


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

    ## Modos de validação:

    - `STRICT`: Warnings viram erros, plano deve ser perfeito
    - `DEFAULT`: Erros bloqueiam, warnings são reportados
    - `LENIENT`: Tolera planos parciais, minimiza erros bloqueantes

    ## Exemplo:

        >>> validator = UTDLValidator(mode=ValidationMode.LENIENT)
        >>> result = validator.validate({"spec_version": "0.1", ...})
    """

    SUPPORTED_SPEC_VERSIONS = {"0.1"}
    VALID_ACTIONS = {"http_request", "wait", "sleep"}

    def __init__(
        self,
        mode: ValidationMode = ValidationMode.DEFAULT,
        strict: bool | None = None,
        validate_limits: bool = True,
        execution_limits: Any | None = None,
    ):
        """
        Inicializa o validador.

        ## Parâmetros:

        - `mode`: Modo de validação (STRICT, DEFAULT, ou LENIENT)
        - `strict`: DEPRECATED - use mode=ValidationMode.STRICT
        - `validate_limits`: Se True, valida limites do Runner
        - `execution_limits`: Limites personalizados (None = carrega do env)

        ## Exemplo:

            >>> # Novo estilo (preferido)
            >>> validator = UTDLValidator(mode=ValidationMode.LENIENT)
            >>>
            >>> # Estilo legado (ainda funciona)
            >>> validator = UTDLValidator(strict=True)
            >>>
            >>> # Com validação de limites
            >>> validator = UTDLValidator(validate_limits=True)
        """
        # Suporte ao parâmetro legado 'strict'
        if strict is not None:
            self.mode = ValidationMode.STRICT if strict else ValidationMode.DEFAULT
        else:
            self.mode = mode

        self.validate_limits = validate_limits
        self._execution_limits = execution_limits

        # Mantém atributo para compatibilidade
        self.strict = self.mode == ValidationMode.STRICT

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

            # Em modo LENIENT, tolerar erros de dependência
            if self.mode == ValidationMode.LENIENT:
                lenient_errors: list[str] = []
                non_critical_pydantic = [
                    "step desconhecido",  # Dependência faltando
                ]
                for err in errors:
                    is_critical = True
                    for pattern in non_critical_pydantic:
                        if pattern in err:
                            warnings.append(f"[lenient] {err}")
                            is_critical = False
                            break
                    if is_critical:
                        lenient_errors.append(err)

                # Se não restou erros críticos, retorna válido com warnings
                if not lenient_errors:
                    return ValidationResult(
                        is_valid=True,
                        errors=[],
                        warnings=warnings,
                        plan=None,  # Plano não disponível em modo lenient com erros
                    )
                errors = lenient_errors

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
            if self.mode == ValidationMode.LENIENT:
                warnings.append("Plano não tem nenhum step definido")
            else:
                errors.append("Plano não tem nenhum step definido")

        # =====================================================================
        # APLICAÇÃO DO MODO DE VALIDAÇÃO
        # =====================================================================

        if self.mode == ValidationMode.STRICT:
            # Em modo STRICT, warnings viram erros
            if warnings:
                errors.extend([f"[strict] {w}" for w in warnings])
                warnings = []

        elif self.mode == ValidationMode.LENIENT:
            # Em modo LENIENT, alguns erros não-críticos viram warnings
            lenient_errors: list[str] = []
            non_critical_patterns = [
                "não existe no plano",      # Dependência faltando (UTDLValidator)
                "step desconhecido",        # Dependência faltando (Pydantic model)
                "não é padrão",             # Action desconhecida
            ]
            for err in errors:
                is_critical = True
                for pattern in non_critical_patterns:
                    if pattern in err:
                        warnings.append(f"[lenient] {err}")
                        is_critical = False
                        break
                if is_critical:
                    lenient_errors.append(err)
            errors = lenient_errors

        # =====================================================================
        # VALIDAÇÃO DE LIMITES (se habilitada)
        # =====================================================================

        structured_errors: list[Any] = []

        if self.validate_limits and HAS_STRUCTURED_ERRORS:
            limits = self._execution_limits or ExecutionLimits.from_env()
            violations = validate_plan_limits(data, limits)

            for violation in violations:
                structured_err = violation.to_structured_error()
                structured_errors.append(structured_err)

                # Adiciona aos erros/warnings baseado em severidade
                msg = f"{violation.limit_name}: {violation.actual_value} > {violation.limit_value}"
                if violation.severity == Severity.ERROR:
                    errors.append(msg)
                else:
                    warnings.append(msg)

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            plan=plan if is_valid else None,
            structured_errors=structured_errors,
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
