"""
================================================================================
CONFIGURAÇÃO CENTRALIZADA DO BRAIN
================================================================================

Este módulo centraliza todas as configurações do Brain em um único lugar,
evitando que cada módulo leia configurações de formas diferentes.

## Para todos entenderem:

Imagine que você tem uma empresa onde cada departamento tem seu próprio
jeito de definir horários, regras e políticas. Isso vira uma bagunça!

Este módulo é como o "RH" que define regras únicas para todos:
- Qual modelo de IA usar
- Quantas tentativas de correção
- Nível de logs (verbose ou silencioso)
- Se força validação estrita

## Por que centralizar?

1. **Consistência**: Todos os módulos usam as mesmas configs
2. **Facilidade**: Mudar config em um lugar muda para todos
3. **Testabilidade**: Fácil mockar configs em testes
4. **Documentação**: Um lugar só para ver todas as opções

## Fontes de configuração (em ordem de prioridade):

1. Parâmetros passados diretamente
2. Variáveis de ambiente
3. Valores padrão

## Exemplo de uso:

    >>> config = BrainConfig.from_env()
    >>> config.model
    'gpt-4'
    >>> config.verbose
    False

    >>> # Ou com valores customizados
    >>> config = BrainConfig(model="claude-3-opus", verbose=True)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .cache import PlanCache, ExecutionHistory


class BrainConfig(BaseModel):
    """
    Configuração centralizada do Brain.

    Esta classe usa Pydantic para validação automática dos valores.
    Todos os campos têm valores padrão sensatos que funcionam out-of-the-box.

    ## Atributos:

    - `model`: Identificador do modelo LLM (ex: "gpt-4", "claude-3-opus")
    - `max_llm_retries`: Máximo de tentativas de correção com LLM
    - `force_schema`: Se True, força validação estrita do schema
    - `verbose`: Se True, exibe logs detalhados
    - `temperature`: Temperatura para sampling do LLM (0.0-1.0)
    - `cache_enabled`: Se True, usa cache de hash dos insumos
    - `cache_dir`: Diretório para armazenar cache
    - `strict_validation`: Se True, falha em qualquer warning de validação

    ## Exemplo:

        >>> config = BrainConfig(model="gpt-4-turbo", verbose=True)
        >>> config.temperature
        0.2
    """

    # =========================================================================
    # CONFIGURAÇÕES DO LLM
    # =========================================================================

    model: str = Field(
        default="gpt-5.1",
        description="Identificador do modelo LLM a usar. Ex: gpt-5.1, grok-4-1-fast-reasoning"
    )

    llm_provider: str = Field(
        default="openai",
        description="Provedor LLM primário. Opções: openai, xai"
    )

    llm_fallback_enabled: bool = Field(
        default=True,
        description="Se True, usa provedor de fallback quando primário falha"
    )

    max_llm_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Máximo de tentativas de correção quando validação falha"
    )

    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Temperatura para sampling. 0.0=determinístico, 1.0=criativo"
    )

    # =========================================================================
    # CONFIGURAÇÕES DE VALIDAÇÃO
    # =========================================================================

    force_schema: bool = Field(
        default=True,
        description="Se True, força validação estrita do schema UTDL"
    )

    strict_validation: bool = Field(
        default=False,
        description="Se True, trata warnings de validação como erros"
    )

    # =========================================================================
    # CONFIGURAÇÕES DE CACHE
    # =========================================================================

    cache_enabled: bool = Field(
        default=True,
        description="Se True, cacheia planos baseado no hash do input"
    )

    cache_dir: str = Field(
        default=".brain_cache",
        description="Diretório para armazenar cache de planos (local)"
    )

    cache_global: bool = Field(
        default=False,
        description="Se True, usa cache global em ~/.aqa/cache/"
    )

    cache_ttl_days: int | None = Field(
        default=None,
        ge=1,
        description="Dias até expiração do cache (None = nunca expira)"
    )

    cache_compress: bool = Field(
        default=False,
        description="Se True, comprime entries do cache com gzip"
    )

    # =========================================================================
    # CONFIGURAÇÕES DE HISTÓRICO
    # =========================================================================

    history_enabled: bool = Field(
        default=True,
        description="Se True, mantém histórico de execuções"
    )

    history_dir: str | None = Field(
        default=None,
        description="Diretório para histórico (default: ~/.aqa/history)"
    )

    history_max_records: int = Field(
        default=1000,
        ge=10,
        description="Número máximo de registros no histórico"
    )

    history_compress: bool = Field(
        default=True,
        description="Se True, comprime registros de histórico"
    )

    # =========================================================================
    # CONFIGURAÇÕES DE LIMITES DE EXECUÇÃO
    # =========================================================================

    max_steps: int | None = Field(
        default=None,
        ge=1,
        description="Número máximo de steps a executar (None = sem limite)"
    )

    timeout_seconds: int = Field(
        default=300,
        ge=1,
        description="Timeout global de execução em segundos"
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Número máximo de retries por step em caso de falha"
    )

    # =========================================================================
    # CONFIGURAÇÕES DE OUTPUT
    # =========================================================================

    verbose: bool = Field(
        default=False,
        description="Se True, exibe logs detalhados de debug"
    )

    silent: bool = Field(
        default=False,
        description="Se True, suprime todos os logs exceto erros críticos"
    )

    # =========================================================================
    # MÉTODOS DE CLASSE
    # =========================================================================

    @classmethod
    def from_env(cls) -> "BrainConfig":
        """
        Cria configuração a partir de variáveis de ambiente.

        ## Variáveis suportadas:

        - `BRAIN_MODEL`: Modelo LLM (default: "gpt-5.1")
        - `BRAIN_LLM_PROVIDER`: Provedor primário (default: "openai")
        - `BRAIN_LLM_FALLBACK`: Habilita fallback (default: "true")
        - `BRAIN_MAX_RETRIES`: Máximo de retries LLM (default: 3)
        - `BRAIN_TEMPERATURE`: Temperatura do LLM (default: 0.2)
        - `BRAIN_FORCE_SCHEMA`: Força validação (default: "true")
        - `BRAIN_STRICT_VALIDATION`: Modo estrito (default: "false")
        - `BRAIN_CACHE_ENABLED`: Habilita cache (default: "true")
        - `BRAIN_CACHE_DIR`: Diretório de cache (default: ".brain_cache")
        - `BRAIN_CACHE_GLOBAL`: Usa cache global ~/.aqa (default: "false")
        - `BRAIN_CACHE_TTL_DAYS`: Dias até expiração (default: None)
        - `BRAIN_CACHE_COMPRESS`: Comprime cache (default: "false")
        - `BRAIN_HISTORY_ENABLED`: Habilita histórico (default: "true")
        - `BRAIN_HISTORY_DIR`: Diretório de histórico (default: ~/.aqa/history)
        - `BRAIN_HISTORY_MAX_RECORDS`: Máximo de registros (default: 1000)
        - `BRAIN_HISTORY_COMPRESS`: Comprime histórico (default: "true")
        - `BRAIN_MAX_STEPS`: Máximo de steps a executar (default: None)
        - `BRAIN_TIMEOUT`: Timeout de execução em segundos (default: 300)
        - `BRAIN_MAX_STEP_RETRIES`: Retries por step falho (default: 3)
        - `BRAIN_VERBOSE`: Logs detalhados (default: "false")
        - `BRAIN_SILENT`: Modo silencioso (default: "false")

        ## Exemplo:

            >>> import os
            >>> os.environ["BRAIN_MODEL"] = "claude-3-opus"
            >>> config = BrainConfig.from_env()
            >>> config.model
            'claude-3-opus'
        """
        def get_bool(key: str, default: bool) -> bool:
            """Helper para converter string para bool."""
            val = os.environ.get(key, str(default)).lower()
            return val in ("true", "1", "yes", "on")

        def get_float(key: str, default: float) -> float:
            """Helper para converter string para float."""
            try:
                return float(os.environ.get(key, str(default)))
            except ValueError:
                return default

        def get_int(key: str, default: int) -> int:
            """Helper para converter string para int."""
            try:
                return int(os.environ.get(key, str(default)))
            except ValueError:
                return default

        def get_int_or_none(key: str) -> int | None:
            """Helper para converter string para int ou None."""
            val = os.environ.get(key)
            if val is None or val.lower() in ("", "none", "null"):
                return None
            try:
                return int(val)
            except ValueError:
                return None

        def get_str_or_none(key: str) -> str | None:
            """Helper para obter string ou None."""
            val = os.environ.get(key)
            if val is None or val.lower() in ("", "none", "null"):
                return None
            return val

        return cls(
            model=os.environ.get("BRAIN_MODEL", "gpt-5.1"),
            llm_provider=os.environ.get("BRAIN_LLM_PROVIDER", "openai"),
            llm_fallback_enabled=get_bool("BRAIN_LLM_FALLBACK", True),
            max_llm_retries=get_int("BRAIN_MAX_RETRIES", 3),
            temperature=get_float("BRAIN_TEMPERATURE", 0.2),
            force_schema=get_bool("BRAIN_FORCE_SCHEMA", True),
            strict_validation=get_bool("BRAIN_STRICT_VALIDATION", False),
            cache_enabled=get_bool("BRAIN_CACHE_ENABLED", True),
            cache_dir=os.environ.get("BRAIN_CACHE_DIR", ".brain_cache"),
            cache_global=get_bool("BRAIN_CACHE_GLOBAL", False),
            cache_ttl_days=get_int_or_none("BRAIN_CACHE_TTL_DAYS"),
            cache_compress=get_bool("BRAIN_CACHE_COMPRESS", False),
            history_enabled=get_bool("BRAIN_HISTORY_ENABLED", True),
            history_dir=get_str_or_none("BRAIN_HISTORY_DIR"),
            history_max_records=get_int("BRAIN_HISTORY_MAX_RECORDS", 1000),
            history_compress=get_bool("BRAIN_HISTORY_COMPRESS", True),
            max_steps=get_int_or_none("BRAIN_MAX_STEPS"),
            timeout_seconds=get_int("BRAIN_TIMEOUT", 300),
            max_retries=get_int("BRAIN_MAX_STEP_RETRIES", 3),
            verbose=get_bool("BRAIN_VERBOSE", False),
            silent=get_bool("BRAIN_SILENT", False),
        )

    @classmethod
    def for_testing(cls) -> "BrainConfig":
        """
        Cria configuração otimizada para testes.

        - Cache desabilitado (testes devem ser independentes)
        - Histórico desabilitado (não poluir ~/.aqa)
        - Verbose habilitado (facilita debug)
        - Retries reduzidos (testes mais rápidos)
        """
        return cls(
            model="gpt-5.1",
            llm_provider="openai",
            max_llm_retries=1,
            cache_enabled=False,
            cache_global=False,
            history_enabled=False,
            verbose=True,
        )

    @classmethod
    def for_production(cls) -> "BrainConfig":
        """
        Cria configuração otimizada para produção.

        - Cache global habilitado (compartilha entre projetos)
        - TTL de 30 dias (cache não fica stale)
        - Compressão habilitada (economia de espaço)
        - Histórico habilitado (auditoria)
        - Silent (menos logs)
        - Validação estrita (mais seguro)
        - Fallback habilitado (maior disponibilidade)
        """
        return cls(
            model="gpt-5.1",
            llm_provider="openai",
            llm_fallback_enabled=True,
            max_llm_retries=3,
            cache_enabled=True,
            cache_global=True,
            cache_ttl_days=30,
            cache_compress=True,
            history_enabled=True,
            history_compress=True,
            verbose=False,
            silent=True,
            strict_validation=True,
        )

    def get_cache(self) -> "PlanCache":
        """
        Cria instância de PlanCache baseada na configuração.

        Retorna cache global ou local dependendo das configurações.

        ## Retorno:

        Instância de PlanCache configurada.

        ## Exemplo:

            >>> config = BrainConfig(cache_global=True)
            >>> cache = config.get_cache()
            >>> cache.cache_dir
            PosixPath('/home/user/.aqa/cache')
        """
        from .cache import PlanCache

        if self.cache_global:
            return PlanCache.global_cache(
                enabled=self.cache_enabled,
                ttl_days=self.cache_ttl_days if self.cache_ttl_days else 30,
                compress=self.cache_compress,
            )
        else:
            return PlanCache.local_cache(
                cache_dir=self.cache_dir,
                enabled=self.cache_enabled,
                ttl_days=self.cache_ttl_days,
                compress=self.cache_compress,
            )

    def get_history(self) -> "ExecutionHistory":
        """
        Cria instância de ExecutionHistory baseada na configuração.

        ## Retorno:

        Instância de ExecutionHistory configurada.

        ## Exemplo:

            >>> config = BrainConfig(history_enabled=True)
            >>> history = config.get_history()
            >>> history.history_dir
            PosixPath('/home/user/.aqa/history')
        """
        from .cache import ExecutionHistory

        return ExecutionHistory(
            history_dir=self.history_dir,
            enabled=self.history_enabled,
            max_records=self.history_max_records,
            compress=self.history_compress,
        )
