"""
================================================================================
Códigos de Erro Padronizados
================================================================================

Compatíveis com os códigos do Runner para facilitar integração.

## Estrutura do Código:

    E[categoria][número]
    │ │         │
    │ │         └── Erro específico (001-999)
    │ └── Categoria (1-6)
    └── Prefixo "E" (Error)

## Categorias:

- E1xxx: Validação/Parsing
- E2xxx: HTTP/Rede
- E3xxx: Assertions
- E4xxx: Configuração
- E5xxx: Interno
- E6xxx: Brain-específico
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass


class ErrorCategory(Enum):
    """
    Categorias de erro compatíveis com o Runner.

    Cada categoria representa uma família de erros relacionados.
    """
    VALIDATION = 1      # E1xxx: Erros de validação/parsing
    HTTP = 2            # E2xxx: Erros de rede/HTTP
    ASSERTION = 3       # E3xxx: Assertions falharam
    CONFIGURATION = 4   # E4xxx: Configuração/ambiente
    INTERNAL = 5        # E5xxx: Erros internos/bugs
    BRAIN = 6           # E6xxx: Específicos do Brain

    @property
    def description(self) -> str:
        """Descrição legível da categoria."""
        descriptions = {
            self.VALIDATION: "Validação",
            self.HTTP: "HTTP/Rede",
            self.ASSERTION: "Assertion",
            self.CONFIGURATION: "Configuração",
            self.INTERNAL: "Interno",
            self.BRAIN: "Brain",
        }
        return descriptions.get(self, "Desconhecido")

    @property
    def emoji(self) -> str:
        """Emoji representativo da categoria."""
        emojis = {
            self.VALIDATION: "📋",
            self.HTTP: "🌐",
            self.ASSERTION: "❌",
            self.CONFIGURATION: "⚙️",
            self.INTERNAL: "🐛",
            self.BRAIN: "🧠",
        }
        return emojis.get(self, "❓")


class Severity(Enum):
    """
    Níveis de severidade para erros e warnings.

    ## Níveis:

    - ERROR: Bloqueia execução, requer correção
    - WARNING: Não bloqueia, mas merece atenção
    - INFO: Informativo, pode ser ignorado
    - HINT: Sugestão de melhoria
    """
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"

    @property
    def icon(self) -> str:
        """Ícone para output CLI."""
        icons = {
            self.ERROR: "❌",
            self.WARNING: "⚠️",
            self.INFO: "ℹ️",
            self.HINT: "💡",
        }
        return icons.get(self, "•")

    @property
    def color(self) -> str:
        """Cor Rich para output."""
        colors = {
            self.ERROR: "red",
            self.WARNING: "yellow",
            self.INFO: "blue",
            self.HINT: "dim",
        }
        return colors.get(self, "white")


@dataclass(frozen=True)
class ErrorCode:
    """
    Código de erro estruturado.

    ## Atributos:

    - `code`: Código numérico (1001-6999)
    - `category`: Categoria do erro
    - `name`: Nome legível do erro
    - `description`: Descrição detalhada
    - `severity`: Severidade padrão
    """
    code: int
    name: str
    description: str
    severity: Severity = Severity.ERROR

    @property
    def category(self) -> ErrorCategory:
        """Extrai categoria do código numérico."""
        cat_num = self.code // 1000
        try:
            return ErrorCategory(cat_num)
        except ValueError:
            return ErrorCategory.INTERNAL

    @property
    def formatted(self) -> str:
        """Código formatado (E1001, E2003, etc)."""
        return f"E{self.code:04d}"

    def __str__(self) -> str:
        return self.formatted

    def __repr__(self) -> str:
        return f"ErrorCode({self.formatted}: {self.name})"


# =============================================================================
# CÓDIGOS DE ERRO DEFINIDOS
# =============================================================================

class ErrorCodes:
    """
    Catálogo de todos os códigos de erro do Brain.

    Organizados por categoria para fácil navegação.
    """

    # =========================================================================
    # E1xxx: Validação/Parsing
    # =========================================================================

    EMPTY_PLAN = ErrorCode(
        code=1001,
        name="EMPTY_PLAN",
        description="Plano não tem nenhum step definido",
    )

    UNSUPPORTED_SPEC_VERSION = ErrorCode(
        code=1002,
        name="UNSUPPORTED_SPEC_VERSION",
        description="Versão de spec não suportada",
    )

    UNKNOWN_ACTION = ErrorCode(
        code=1003,
        name="UNKNOWN_ACTION",
        description="Action desconhecida no step",
        severity=Severity.WARNING,
    )

    MISSING_REQUIRED_FIELD = ErrorCode(
        code=1004,
        name="MISSING_REQUIRED_FIELD",
        description="Campo obrigatório ausente",
    )

    UNKNOWN_DEPENDENCY = ErrorCode(
        code=1005,
        name="UNKNOWN_DEPENDENCY",
        description="Dependência referencia step que não existe",
    )

    CIRCULAR_DEPENDENCY = ErrorCode(
        code=1006,
        name="CIRCULAR_DEPENDENCY",
        description="Dependência circular detectada",
    )

    INVALID_HTTP_METHOD = ErrorCode(
        code=1007,
        name="INVALID_HTTP_METHOD",
        description="Método HTTP inválido",
    )

    EMPTY_STEP_ID = ErrorCode(
        code=1008,
        name="EMPTY_STEP_ID",
        description="ID de step vazio ou só espaços",
    )

    INVALID_JSON = ErrorCode(
        code=1009,
        name="INVALID_JSON",
        description="JSON inválido no plano",
    )

    MAX_STEPS_EXCEEDED = ErrorCode(
        code=1010,
        name="MAX_STEPS_EXCEEDED",
        description="Plano excede limite de steps",
    )

    MAX_RETRIES_EXCEEDED = ErrorCode(
        code=1011,
        name="MAX_RETRIES_EXCEEDED",
        description="Soma de retries excede limite",
    )

    EXECUTION_TIMEOUT_EXCEEDED = ErrorCode(
        code=1012,
        name="EXECUTION_TIMEOUT_EXCEEDED",
        description="Tempo estimado excede limite",
    )

    DUPLICATE_STEP_ID = ErrorCode(
        code=1013,
        name="DUPLICATE_STEP_ID",
        description="IDs de steps duplicados",
    )

    SELF_DEPENDENCY = ErrorCode(
        code=1014,
        name="SELF_DEPENDENCY",
        description="Step depende de si mesmo",
    )

    INVALID_ASSERTION_TYPE = ErrorCode(
        code=1015,
        name="INVALID_ASSERTION_TYPE",
        description="Tipo de assertion inválido",
    )

    MISSING_ASSERTION_FIELD = ErrorCode(
        code=1016,
        name="MISSING_ASSERTION_FIELD",
        description="Campo obrigatório de assertion ausente",
    )

    INVALID_REGEX = ErrorCode(
        code=1017,
        name="INVALID_REGEX",
        description="Expressão regular inválida",
    )

    INVALID_JSONPATH = ErrorCode(
        code=1018,
        name="INVALID_JSONPATH",
        description="Expressão JSONPath inválida",
    )

    # =========================================================================
    # E4xxx: Configuração
    # =========================================================================

    MISSING_BASE_URL = ErrorCode(
        code=4001,
        name="MISSING_BASE_URL",
        description="base_url não configurada",
    )

    RUNNER_NOT_FOUND = ErrorCode(
        code=4002,
        name="RUNNER_NOT_FOUND",
        description="Executável do Runner não encontrado",
    )

    INVALID_SWAGGER = ErrorCode(
        code=4003,
        name="INVALID_SWAGGER",
        description="Arquivo OpenAPI/Swagger inválido",
    )

    LLM_API_ERROR = ErrorCode(
        code=4004,
        name="LLM_API_ERROR",
        description="Erro ao chamar API do LLM",
    )

    MISSING_API_KEY = ErrorCode(
        code=4005,
        name="MISSING_API_KEY",
        description="API key não configurada",
    )

    # =========================================================================
    # E5xxx: Interno
    # =========================================================================

    INTERNAL_ERROR = ErrorCode(
        code=5001,
        name="INTERNAL_ERROR",
        description="Erro interno inesperado",
    )

    CACHE_ERROR = ErrorCode(
        code=5002,
        name="CACHE_ERROR",
        description="Erro ao acessar cache",
    )

    # =========================================================================
    # E6xxx: Brain-específico
    # =========================================================================

    PLAN_EXCEEDS_MAX_STEPS = ErrorCode(
        code=6001,
        name="PLAN_EXCEEDS_MAX_STEPS",
        description="Plano gerado excede limite de steps do Runner",
    )

    PLAN_EXCEEDS_MAX_PARALLEL = ErrorCode(
        code=6002,
        name="PLAN_EXCEEDS_MAX_PARALLEL",
        description="Plano excede limite de paralelismo",
    )

    PLAN_EXCEEDS_MAX_RETRIES = ErrorCode(
        code=6003,
        name="PLAN_EXCEEDS_MAX_RETRIES",
        description="Plano excede limite total de retries",
    )

    PLAN_EXCEEDS_TIMEOUT = ErrorCode(
        code=6004,
        name="PLAN_EXCEEDS_TIMEOUT",
        description="Tempo estimado excede timeout de execução",
    )

    NORMALIZATION_FAILED = ErrorCode(
        code=6005,
        name="NORMALIZATION_FAILED",
        description="Falha ao normalizar formato do plano",
    )

    GENERATION_FAILED = ErrorCode(
        code=6006,
        name="GENERATION_FAILED",
        description="Falha ao gerar plano via LLM",
    )

    VERSION_NOT_FOUND = ErrorCode(
        code=6007,
        name="VERSION_NOT_FOUND",
        description="Versão do plano não encontrada",
    )

    @classmethod
    def get_by_code(cls, code: int) -> ErrorCode | None:
        """Busca ErrorCode pelo número."""
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, ErrorCode) and attr.code == code:
                return attr
        return None

    @classmethod
    def get_by_name(cls, name: str) -> ErrorCode | None:
        """Busca ErrorCode pelo nome."""
        return getattr(cls, name, None)
