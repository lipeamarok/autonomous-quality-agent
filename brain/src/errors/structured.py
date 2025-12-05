"""
================================================================================
Erros Estruturados com Contexto Rico
================================================================================

Fornece classes de erro que incluem:
- Código padronizado
- Path JSON exato para o problema
- Sugestões de correção
- Formatação para CLI e JSON
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .codes import ErrorCode, ErrorCodes, ErrorCategory, Severity


@dataclass
class StructuredError:
    """
    Erro estruturado com contexto completo.

    ## Atributos:

    - `code`: Código de erro (ErrorCode)
    - `message`: Mensagem legível
    - `path`: Caminho JSON até o problema ($.steps[0].action)
    - `suggestion`: Sugestão de como corrigir
    - `context`: Dados adicionais para debug
    - `severity`: Severidade (pode sobrescrever o padrão do código)

    ## Exemplo:

        >>> error = StructuredError(
        ...     code=ErrorCodes.UNKNOWN_DEPENDENCY,
        ...     message="Step 'step2' depende de 'step_inexistente' que não existe",
        ...     path="$.steps[1].depends_on[0]",
        ...     suggestion="Verifique se o ID está correto ou remova a dependência",
        ... )
    """
    code: ErrorCode
    message: str
    path: str | None = None
    suggestion: str | None = None
    context: dict[str, Any] = field(default_factory=lambda: {})
    severity: Severity | None = None

    @property
    def effective_severity(self) -> Severity:
        """Severidade efetiva (própria ou do código)."""
        return self.severity or self.code.severity

    @property
    def category(self) -> ErrorCategory:
        """Categoria do erro."""
        return self.code.category

    def __str__(self) -> str:
        """Representação legível."""
        parts = [f"{self.code}: {self.message}"]
        if self.path:
            parts[0] += f" ({self.path})"
        return parts[0]

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário (para JSON)."""
        result: dict[str, Any] = {
            "code": self.code.formatted,
            "name": self.code.name,
            "message": self.message,
            "severity": self.effective_severity.value,
            "category": self.category.description,
        }
        if self.path:
            result["path"] = self.path
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.context:
            result["context"] = self.context
        return result


@dataclass
class ValidationError(StructuredError):
    """
    Erro de validação de plano UTDL.

    Especialização de StructuredError para erros de validação,
    com helpers para tipos comuns de erro.
    """

    @classmethod
    def missing_field(
        cls,
        field_name: str,
        path: str,
        parent_type: str = "step",
    ) -> "ValidationError":
        """Cria erro de campo obrigatório ausente."""
        return cls(
            code=ErrorCodes.MISSING_REQUIRED_FIELD,
            message=f"Campo obrigatório '{field_name}' ausente em {parent_type}",
            path=path,
            suggestion=f"Adicione o campo '{field_name}' ao {parent_type}",
        )

    @classmethod
    def unknown_dependency(
        cls,
        step_id: str,
        dependency_id: str,
        path: str,
        available_ids: list[str] | None = None,
    ) -> "ValidationError":
        """Cria erro de dependência desconhecida."""
        suggestion = f"Verifique se o ID '{dependency_id}' está correto"
        if available_ids:
            # Sugere IDs similares
            similar = [sid for sid in available_ids if dependency_id.lower() in sid.lower() or sid.lower() in dependency_id.lower()]
            if similar:
                suggestion += f". IDs similares: {', '.join(similar[:3])}"
            else:
                suggestion += f". IDs disponíveis: {', '.join(available_ids[:5])}"
                if len(available_ids) > 5:
                    suggestion += f" (+{len(available_ids) - 5} mais)"

        return cls(
            code=ErrorCodes.UNKNOWN_DEPENDENCY,
            message=f"Step '{step_id}' depende de '{dependency_id}' que não existe",
            path=path,
            suggestion=suggestion,
            context={"step_id": step_id, "dependency_id": dependency_id},
        )

    @classmethod
    def circular_dependency(
        cls,
        cycle: list[str],
        path: str | None = None,
    ) -> "ValidationError":
        """Cria erro de dependência circular."""
        cycle_str = " → ".join(cycle)
        return cls(
            code=ErrorCodes.CIRCULAR_DEPENDENCY,
            message=f"Dependência circular detectada: {cycle_str}",
            path=path or "$.steps",
            suggestion="Reorganize as dependências para formar um DAG (sem ciclos)",
            context={"cycle": cycle},
        )

    @classmethod
    def duplicate_id(
        cls,
        step_id: str,
        first_index: int,
        second_index: int,
    ) -> "ValidationError":
        """Cria erro de ID duplicado."""
        return cls(
            code=ErrorCodes.DUPLICATE_STEP_ID,
            message=f"ID '{step_id}' usado em steps[{first_index}] e steps[{second_index}]",
            path=f"$.steps[{second_index}].id",
            suggestion=f"Renomeie um dos steps para ter ID único",
            context={"step_id": step_id, "indices": [first_index, second_index]},
        )

    @classmethod
    def invalid_assertion(
        cls,
        assertion_type: str,
        path: str,
        valid_types: list[str] | None = None,
    ) -> "ValidationError":
        """Cria erro de assertion inválida."""
        suggestion = f"Use um tipo de assertion válido"
        if valid_types:
            suggestion += f": {', '.join(valid_types)}"

        return cls(
            code=ErrorCodes.INVALID_ASSERTION_TYPE,
            message=f"Tipo de assertion '{assertion_type}' inválido",
            path=path,
            suggestion=suggestion,
            context={"assertion_type": assertion_type},
        )


@dataclass
class ConfigurationError(StructuredError):
    """Erro de configuração/ambiente."""

    @classmethod
    def runner_not_found(cls, searched_paths: list[str]) -> "ConfigurationError":
        """Cria erro de runner não encontrado."""
        return cls(
            code=ErrorCodes.RUNNER_NOT_FOUND,
            message="Executável do Runner não encontrado",
            suggestion="Compile com 'cargo build --release' ou use --runner-path",
            context={"searched_paths": searched_paths},
        )

    @classmethod
    def missing_api_key(cls, provider: str, env_var: str) -> "ConfigurationError":
        """Cria erro de API key ausente."""
        return cls(
            code=ErrorCodes.MISSING_API_KEY,
            message=f"API key para {provider} não configurada",
            suggestion=f"Configure a variável de ambiente {env_var}",
            context={"provider": provider, "env_var": env_var},
        )


@dataclass
class GenerationError(StructuredError):
    """Erro na geração de plano via LLM."""

    @classmethod
    def llm_error(cls, provider: str, error_message: str) -> "GenerationError":
        """Cria erro de falha no LLM."""
        return cls(
            code=ErrorCodes.LLM_API_ERROR,
            message=f"Erro ao chamar {provider}: {error_message}",
            suggestion="Verifique a API key e conexão com a internet",
            context={"provider": provider},
        )


# =============================================================================
# FUNÇÕES DE FORMATAÇÃO
# =============================================================================


def format_error(error: StructuredError, verbose: bool = False) -> str:
    """
    Formata erro para output CLI.

    ## Parâmetros:

    - `error`: Erro a formatar
    - `verbose`: Se True, inclui contexto completo
    """
    severity = error.effective_severity
    icon = severity.icon
    color = severity.color

    parts = [f"[{color}]{icon} {error.code}: {error.message}[/{color}]"]

    if error.path:
        parts.append(f"   [dim]Path: {error.path}[/dim]")

    if error.suggestion:
        parts.append(f"   [cyan]💡 {error.suggestion}[/cyan]")

    if verbose and error.context:
        import json
        ctx_str = json.dumps(error.context, indent=2, ensure_ascii=False)
        parts.append(f"   [dim]Context: {ctx_str}[/dim]")

    return "\n".join(parts)


def format_errors_for_json(errors: list[StructuredError]) -> dict[str, Any]:
    """
    Formata lista de erros para saída JSON.

    ## Retorno:

    Dict com estrutura:
    ```json
    {
        "success": false,
        "errors": [...],
        "summary": {
            "total": 3,
            "by_severity": {"error": 2, "warning": 1},
            "by_category": {"Validação": 2, "Configuração": 1}
        }
    }
    ```
    """
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}

    for err in errors:
        sev = err.effective_severity.value
        cat = err.category.description
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "success": len([e for e in errors if e.effective_severity == Severity.ERROR]) == 0,
        "errors": [e.to_dict() for e in errors],
        "summary": {
            "total": len(errors),
            "by_severity": by_severity,
            "by_category": by_category,
        },
    }


def format_errors_for_cli(
    errors: list[StructuredError],
    verbose: bool = False,
    group_by_severity: bool = True,
) -> str:
    """
    Formata lista de erros para output CLI com Rich.

    ## Parâmetros:

    - `errors`: Lista de erros
    - `verbose`: Inclui contexto
    - `group_by_severity`: Agrupa por severidade
    """
    if not errors:
        return "[green]✓ Nenhum erro encontrado[/green]"

    lines: list[str] = []

    if group_by_severity:
        # Agrupa por severidade
        by_severity: dict[Severity, list[StructuredError]] = {}
        for err in errors:
            sev = err.effective_severity
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(err)

        # Ordena por severidade (ERROR primeiro)
        order = [Severity.ERROR, Severity.WARNING, Severity.INFO, Severity.HINT]
        for sev in order:
            if sev in by_severity:
                lines.append(f"\n[bold {sev.color}]{sev.icon} {sev.value.upper()}S ({len(by_severity[sev])})[/bold {sev.color}]")
                for err in by_severity[sev]:
                    lines.append(format_error(err, verbose))
    else:
        for err in errors:
            lines.append(format_error(err, verbose))

    return "\n".join(lines)
