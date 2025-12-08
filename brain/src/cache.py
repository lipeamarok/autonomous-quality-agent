"""
================================================================================
CACHE DE HASH DOS INSUMOS
================================================================================

Este módulo implementa cache baseado em hash para evitar regenerar planos
quando os mesmos inputs são fornecidos.

## Para todos entenderem:

Imagine que você pede uma pizza de pepperoni toda sexta-feira.
O pizzaiolo pode:
1. Fazer do zero toda vez (caro e demorado)
2. Lembrar que você pediu isso antes e entregar uma igual (rápido e barato)

Este módulo faz a opção 2 para planos de teste:
- Calcula um "fingerprint" único do input
- Se já temos um plano para esse fingerprint, retorna ele
- Caso contrário, gera um novo e guarda no cache

## Por que isso é importante?

1. **Economia**: Chamadas de LLM custam dinheiro
2. **Velocidade**: Cache é instantâneo vs segundos do LLM
3. **Consistência**: Mesmo input = mesmo output
4. **Debugging**: Facilita reproduzir problemas

## Estrutura do cache:

Suporta dois modos de armazenamento:

### Cache Local (padrão legacy):
```
.brain_cache/
├── index.json          # Mapa de hash → arquivo
├── abc123.json         # Plano cacheado
└── ...
```

### Cache Global (recomendado):
```
~/.aqa/
├── cache/
│   ├── index.json      # Índice com metadados e TTL
│   ├── abc123.json.gz  # Plano comprimido (opcional)
│   └── def456.json     # Plano não comprimido
├── history/            # Histórico de execuções
│   └── ...
└── config.yaml         # Configuração global
```

## Exemplo de uso:

    >>> cache = PlanCache()
    >>>
    >>> # Primeira vez: gera e cacheia
    >>> plan = generator.generate(requirements, base_url)
    >>> cache.store(requirements, base_url, plan)
    >>>
    >>> # Segunda vez: retorna do cache
    >>> cached = cache.get(requirements, base_url)
    >>> if cached:
    ...     print("Usando plano do cache!")

    >>> # Cache global com TTL de 7 dias
    >>> global_cache = PlanCache.global_cache(ttl_days=7)
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Literal


# Constantes para localização do cache global
AQA_HOME_DIR = ".aqa"
AQA_CACHE_SUBDIR = "cache"
AQA_HISTORY_SUBDIR = "history"
DEFAULT_TTL_DAYS = 30


@dataclass
class CacheEntry:
    """
    Entrada no cache de planos.

    ## Atributos:

    - `hash`: Hash único do input
    - `created_at`: Data/hora de criação
    - `expires_at`: Data/hora de expiração (opcional)
    - `input_summary`: Resumo do input (para debug)
    - `plan`: O plano cacheado
    - `compressed`: Se o arquivo está comprimido
    """
    hash: str
    created_at: str
    input_summary: str
    plan: dict[str, Any]
    expires_at: str | None = None
    compressed: bool = False


@dataclass
class CacheStats:
    """
    Estatísticas do cache.

    ## Atributos:

    - `enabled`: Se cache está habilitado
    - `entries`: Número total de entries
    - `expired_entries`: Número de entries expiradas
    - `cache_dir`: Diretório do cache
    - `size_bytes`: Tamanho total em bytes
    - `compressed_entries`: Número de entries comprimidas
    """
    enabled: bool
    entries: int
    cache_dir: str
    expired_entries: int = 0
    size_bytes: int = 0
    compressed_entries: int = 0


def get_global_cache_dir() -> Path:
    """
    Retorna o diretório global de cache (~/.aqa/cache/).

    Respeita variável de ambiente AQA_HOME se definida.

    ## Retorno:

    Path para o diretório de cache global.
    """
    aqa_home = os.environ.get("AQA_HOME")
    if aqa_home:
        return Path(aqa_home) / AQA_CACHE_SUBDIR
    return Path.home() / AQA_HOME_DIR / AQA_CACHE_SUBDIR


def get_global_history_dir() -> Path:
    """
    Retorna o diretório global de histórico (~/.aqa/history/).

    Respeita variável de ambiente AQA_HOME se definida.

    ## Retorno:

    Path para o diretório de histórico global.
    """
    aqa_home = os.environ.get("AQA_HOME")
    if aqa_home:
        return Path(aqa_home) / AQA_HISTORY_SUBDIR
    return Path.home() / AQA_HOME_DIR / AQA_HISTORY_SUBDIR


class PlanCache:
    """
    Cache de planos baseado em hash dos inputs.

    Este cache persiste em disco e sobrevive entre execuções.
    Usa hash SHA256 para gerar fingerprints únicos.

    ## Thread Safety:

    Este cache é thread-safe. Usa locks por hash para permitir
    operações concorrentes em entradas diferentes enquanto
    serializa operações na mesma entrada.

    ## TTL (Time-to-Live):

    Entries podem expirar automaticamente. Configure `ttl_days`
    para definir por quanto tempo entries são válidas.

    ## Compressão:

    Entries podem ser comprimidas com gzip para economizar espaço.
    Útil para planos grandes. Configure `compress=True`.

    ## Exemplo:

        >>> cache = PlanCache(cache_dir=".brain_cache")
        >>>
        >>> # Verifica se existe
        >>> existing = cache.get("teste API login", "https://api.example.com")
        >>>
        >>> # Armazena novo
        >>> cache.store("teste API login", "https://api.example.com", plan_dict)

        >>> # Cache global com TTL e compressão
        >>> global_cache = PlanCache.global_cache(ttl_days=7, compress=True)
    """

    INDEX_FILE = "index.json"

    def __init__(
        self,
        cache_dir: str = ".brain_cache",
        enabled: bool = True,
        ttl_days: int | None = None,
        compress: bool = False,
    ):
        """
        Inicializa o cache.

        ## Parâmetros:

        - `cache_dir`: Diretório para armazenar cache
        - `enabled`: Se False, cache é desabilitado (always miss)
        - `ttl_days`: Dias até expiração (None = nunca expira)
        - `compress`: Se True, comprime entries com gzip
        """
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.ttl_days = ttl_days
        self.compress = compress
        self._index: dict[str, dict[str, Any]] = {}  # hash → {filename, expires_at, compressed}

        # Lock global para operações no índice
        self._index_lock = threading.Lock()

        # Locks por hash para operações em entradas individuais
        self._hash_locks: dict[str, threading.Lock] = {}
        self._hash_locks_lock = threading.Lock()

        if enabled:
            self._ensure_cache_dir()
            self._load_index()

    @classmethod
    def global_cache(
        cls,
        enabled: bool = True,
        ttl_days: int = DEFAULT_TTL_DAYS,
        compress: bool = True,
    ) -> "PlanCache":
        """
        Cria cache global em ~/.aqa/cache/.

        Esta é a forma recomendada de usar o cache para
        compartilhar entries entre projetos.

        ## Parâmetros:

        - `enabled`: Se False, cache é desabilitado
        - `ttl_days`: Dias até expiração (default: 30)
        - `compress`: Se True, comprime entries (default: True)

        ## Retorno:

        Instância de PlanCache configurada para uso global.

        ## Exemplo:

            >>> cache = PlanCache.global_cache()
            >>> cache.cache_dir
            PosixPath('/home/user/.aqa/cache')
        """
        cache_dir = get_global_cache_dir()
        return cls(
            cache_dir=str(cache_dir),
            enabled=enabled,
            ttl_days=ttl_days,
            compress=compress,
        )

    @classmethod
    def local_cache(
        cls,
        cache_dir: str = ".brain_cache",
        enabled: bool = True,
        ttl_days: int | None = None,
        compress: bool = False,
    ) -> "PlanCache":
        """
        Cria cache local no diretório especificado.

        Mantém compatibilidade com comportamento anterior.

        ## Parâmetros:

        - `cache_dir`: Diretório para cache (default: .brain_cache)
        - `enabled`: Se False, cache é desabilitado
        - `ttl_days`: Dias até expiração (None = nunca expira)
        - `compress`: Se True, comprime entries

        ## Retorno:

        Instância de PlanCache para uso local.
        """
        return cls(
            cache_dir=cache_dir,
            enabled=enabled,
            ttl_days=ttl_days,
            compress=compress,
        )

    def _get_hash_lock(self, hash_key: str) -> threading.Lock:
        """
        Obtém ou cria um lock para um hash específico.

        Thread-safe: usa lock global para gerenciar o dicionário de locks.
        """
        with self._hash_locks_lock:
            if hash_key not in self._hash_locks:
                self._hash_locks[hash_key] = threading.Lock()
            return self._hash_locks[hash_key]

    def _ensure_cache_dir(self) -> None:
        """Cria diretório de cache se não existir."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Carrega índice do disco."""
        with self._index_lock:
            index_path = self.cache_dir / self.INDEX_FILE
            if index_path.exists():
                try:
                    with open(index_path, "r", encoding="utf-8") as f:
                        raw_index = json.load(f)
                        # Migra índice antigo (string) para novo formato (dict)
                        self._index = {}
                        for hash_key, value in raw_index.items():
                            if isinstance(value, str):
                                # Formato antigo: hash → filename
                                self._index[hash_key] = {
                                    "filename": value,
                                    "expires_at": None,
                                    "compressed": value.endswith(".gz"),
                                }
                            else:
                                # Formato novo: hash → {filename, expires_at, compressed}
                                self._index[hash_key] = value
                except (json.JSONDecodeError, IOError):
                    self._index = {}

    def _save_index(self) -> None:
        """Salva índice no disco. DEVE ser chamada com _index_lock adquirido."""
        index_path = self.cache_dir / self.INDEX_FILE
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _is_expired(self, entry_meta: dict[str, Any]) -> bool:
        """
        Verifica se uma entry está expirada.

        ## Parâmetros:

        - `entry_meta`: Metadados da entry do índice

        ## Retorno:

        True se expirada, False caso contrário.
        """
        expires_at = entry_meta.get("expires_at")
        if not expires_at:
            return False

        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > expiry
        except (ValueError, TypeError):
            return False

    def _read_entry_file(self, filepath: Path, compressed: bool = False) -> dict[str, Any] | None:
        """
        Lê arquivo de entry, descomprimindo se necessário.

        ## Parâmetros:

        - `filepath`: Caminho do arquivo
        - `compressed`: Se arquivo está comprimido com gzip

        ## Retorno:

        Dict da entry ou None se falhar.
        """
        try:
            if compressed or filepath.suffix == ".gz":
                with gzip.open(filepath, "rt", encoding="utf-8") as f:
                    return json.load(f)
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError, gzip.BadGzipFile):
            return None

    def _write_entry_file(self, filepath: Path, entry: dict[str, Any], compress: bool = False) -> bool:
        """
        Escreve arquivo de entry, comprimindo se solicitado.

        ## Parâmetros:

        - `filepath`: Caminho do arquivo
        - `entry`: Dict da entry a salvar
        - `compress`: Se deve comprimir com gzip

        ## Retorno:

        True se sucesso, False se falhar.
        """
        try:
            if compress:
                # Garante extensão .gz
                if filepath.suffix != ".gz":
                    filepath = filepath.with_suffix(filepath.suffix + ".gz")
                with gzip.open(filepath, "wt", encoding="utf-8") as f:
                    json.dump(entry, f, indent=2, ensure_ascii=False)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(entry, f, indent=2, ensure_ascii=False)
            return True
        except IOError:
            return False

    def _compute_hash(
        self,
        requirements: str,
        base_url: str,
        provider: str | None = None,
        model: str | None = None
    ) -> str:
        """
        Calcula hash único do input.

        Usa SHA256 para garantir unicidade.
        Normaliza o input antes de hashear.

        ## Por que incluir provider/model?

        Modelos diferentes geram planos de qualidade diferente.
        Sem isso, um plano gerado por um modelo barato seria
        retornado quando o usuário espera resultado de um modelo
        premium.

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API
        - `provider`: Provedor LLM (ex: "openai", "xai")
        - `model`: Identificador do modelo (ex: "gpt-5.1", "grok-4")
        """
        # Normaliza: lowercase, trim
        parts = [
            requirements.strip().lower(),
            base_url.strip().lower(),
        ]

        # Inclui provider/model se fornecidos (backward compatible)
        if provider:
            parts.append(f"provider:{provider.strip().lower()}")
        if model:
            parts.append(f"model:{model.strip().lower()}")

        normalized = "|".join(parts)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def get(
        self,
        requirements: str,
        base_url: str,
        provider: str | None = None,
        model: str | None = None
    ) -> dict[str, Any] | None:
        """
        Busca plano no cache.

        Thread-safe: usa lock por hash para acesso concorrente.
        Respeita TTL: entries expiradas retornam None.

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API
        - `provider`: Provedor LLM (opcional, mas recomendado)
        - `model`: Modelo LLM (opcional, mas recomendado)

        ## Retorno:

        - Dict do plano se encontrado e não expirado
        - None se não encontrado, expirado, ou cache desabilitado

        ## Nota:

        Se provider/model não forem fornecidos, busca apenas pelo
        hash de requirements+base_url (backward compatible).
        """
        if not self.enabled:
            return None

        hash_key = self._compute_hash(requirements, base_url, provider, model)
        hash_lock = self._get_hash_lock(hash_key)

        with hash_lock:
            with self._index_lock:
                if hash_key not in self._index:
                    return None
                entry_meta = self._index[hash_key]

                # Verifica expiração
                if self._is_expired(entry_meta):
                    # Remove entry expirada
                    filename = entry_meta["filename"]
                    filepath = self.cache_dir / filename
                    if filepath.exists():
                        filepath.unlink()
                    del self._index[hash_key]
                    self._save_index()
                    return None

                filename = entry_meta["filename"]
                compressed = entry_meta.get("compressed", False)

            filepath = self.cache_dir / filename

            if not filepath.exists():
                # Arquivo foi deletado, limpa índice
                with self._index_lock:
                    if hash_key in self._index:
                        del self._index[hash_key]
                        self._save_index()
                return None

            entry = self._read_entry_file(filepath, compressed)
            if entry:
                return entry.get("plan")
            return None

    def store(
        self,
        requirements: str,
        base_url: str,
        plan: dict[str, Any],
        provider: str | None = None,
        model: str | None = None
    ) -> str:
        """
        Armazena plano no cache.

        Thread-safe: usa lock por hash para acesso concorrente.
        Suporta TTL e compressão configurados na instância.

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API
        - `plan`: Plano UTDL a cachear
        - `provider`: Provedor LLM que gerou o plano
        - `model`: Modelo LLM que gerou o plano

        ## Retorno:

        Hash do entry (para referência)

        ## Importante:

        Incluir provider/model garante que planos de modelos
        diferentes são cacheados separadamente. Um usuário que
        muda de grok-4-fast para gpt-5.1 receberá um plano novo.
        """
        if not self.enabled:
            return ""

        hash_key = self._compute_hash(requirements, base_url, provider, model)
        hash_lock = self._get_hash_lock(hash_key)

        # Define nome do arquivo com extensão apropriada
        extension = ".json.gz" if self.compress else ".json"
        filename = f"{hash_key}{extension}"
        filepath = self.cache_dir / filename

        with hash_lock:
            # Calcula data de expiração se TTL definido
            expires_at: str | None = None
            if self.ttl_days is not None:
                expiry = datetime.now(timezone.utc) + timedelta(days=self.ttl_days)
                expires_at = expiry.isoformat().replace("+00:00", "Z")

            # Cria entrada
            entry: dict[str, Any] = {
                "hash": hash_key,
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "expires_at": expires_at,
                "input_summary": requirements[:100] + ("..." if len(requirements) > 100 else ""),
                "base_url": base_url,
                "provider": provider,
                "model": model,
                "compressed": self.compress,
                "plan": plan,
            }

            # Salva arquivo
            if not self._write_entry_file(filepath, entry, self.compress):
                return ""

            # Atualiza índice com metadados
            with self._index_lock:
                self._index[hash_key] = {
                    "filename": filename,
                    "expires_at": expires_at,
                    "compressed": self.compress,
                }
                self._save_index()

        return hash_key

    def invalidate(
        self,
        requirements: str,
        base_url: str,
        provider: str | None = None,
        model: str | None = None
    ) -> bool:
        """
        Remove entrada do cache.

        Thread-safe: usa lock por hash para acesso concorrente.

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API
        - `provider`: Provedor LLM (opcional)
        - `model`: Modelo LLM (opcional)

        ## Retorno:

        True se entry foi removida, False se não existia
        """
        if not self.enabled:
            return False

        hash_key = self._compute_hash(requirements, base_url, provider, model)
        hash_lock = self._get_hash_lock(hash_key)

        with hash_lock:
            with self._index_lock:
                if hash_key not in self._index:
                    return False

                entry_meta = self._index[hash_key]
                filename = entry_meta["filename"]
                filepath = self.cache_dir / filename

                # Remove arquivo
                if filepath.exists():
                    filepath.unlink()

                # Remove do índice
                del self._index[hash_key]
                self._save_index()

        return True

    def clear(self) -> int:
        """
        Limpa todo o cache.

        Thread-safe: usa lock global para limpeza completa.

        ## Retorno:

        Número de entries removidas
        """
        if not self.enabled:
            return 0

        with self._index_lock:
            count = len(self._index)

            # Remove todos os arquivos
            for entry_meta in self._index.values():
                filename = entry_meta["filename"]
                filepath = self.cache_dir / filename
                if filepath.exists():
                    filepath.unlink()

            # Limpa índice
            self._index = {}
            self._save_index()

            # Limpa locks de hash (já que não há mais entradas)
            with self._hash_locks_lock:
                self._hash_locks.clear()

        return count

    def cleanup_expired(self) -> int:
        """
        Remove todas as entries expiradas do cache.

        Útil para manutenção periódica do cache.

        Thread-safe: usa lock global para consistência.

        ## Retorno:

        Número de entries removidas.
        """
        if not self.enabled:
            return 0

        with self._index_lock:
            expired_keys = [
                key for key, meta in self._index.items()
                if self._is_expired(meta)
            ]

            for hash_key in expired_keys:
                entry_meta = self._index[hash_key]
                filename = entry_meta["filename"]
                filepath = self.cache_dir / filename
                if filepath.exists():
                    filepath.unlink()
                del self._index[hash_key]

            if expired_keys:
                self._save_index()

            return len(expired_keys)

    def stats(self) -> CacheStats:
        """
        Retorna estatísticas detalhadas do cache.

        Thread-safe: usa lock para leitura consistente.

        ## Retorno:

        CacheStats com:
        - `enabled`: Se cache está habilitado
        - `entries`: Número de entries
        - `expired_entries`: Número de entries expiradas
        - `cache_dir`: Diretório do cache
        - `size_bytes`: Tamanho total em bytes
        - `compressed_entries`: Número de entries comprimidas
        """
        if not self.enabled:
            return CacheStats(
                enabled=False,
                entries=0,
                cache_dir=str(self.cache_dir),
            )

        with self._index_lock:
            total_size = 0
            expired_count = 0
            compressed_count = 0

            for entry_meta in self._index.values():
                if self._is_expired(entry_meta):
                    expired_count += 1

                if entry_meta.get("compressed", False):
                    compressed_count += 1

                filename = entry_meta["filename"]
                filepath = self.cache_dir / filename
                if filepath.exists():
                    total_size += filepath.stat().st_size

            return CacheStats(
                enabled=True,
                entries=len(self._index),
                expired_entries=expired_count,
                cache_dir=str(self.cache_dir),
                size_bytes=total_size,
                compressed_entries=compressed_count,
            )


# =============================================================================
# HISTÓRICO DE EXECUÇÕES
# =============================================================================


@dataclass
class ExecutionRecord:
    """
    Registro de uma execução de plano.

    ## Atributos:

    - `id`: ID único da execução (UUID)
    - `timestamp`: Data/hora da execução
    - `plan_file`: Arquivo do plano executado
    - `plan_hash`: Hash do plano (se cacheado)
    - `duration_ms`: Duração total em milissegundos
    - `total_steps`: Número total de steps
    - `passed_steps`: Número de steps que passaram
    - `failed_steps`: Número de steps que falharam
    - `status`: Status final ("success", "failure", "error")
    - `runner_report`: Relatório completo do Runner (opcional)
    """
    id: str
    timestamp: str
    plan_file: str
    duration_ms: int
    total_steps: int
    passed_steps: int
    failed_steps: int
    status: Literal["success", "failure", "error"]
    plan_hash: str | None = None
    runner_report: dict[str, Any] | None = None


class ExecutionHistory:
    """
    Armazena histórico de execuções para análise e debugging.

    O histórico é persistido em ~/.aqa/history/ por padrão,
    permitindo consultar execuções passadas.

    ## Estrutura:

    ```
    ~/.aqa/history/
    ├── index.json           # Índice com metadados de todas execuções
    ├── 2024-01-15/          # Subdiretório por data
    │   ├── abc123.json      # Execução individual
    │   └── def456.json
    └── 2024-01-16/
        └── ...
    ```

    ## Exemplo:

        >>> history = ExecutionHistory()
        >>> record = history.record_execution(
        ...     plan_file="test_plan.json",
        ...     duration_ms=1500,
        ...     total_steps=5,
        ...     passed_steps=4,
        ...     failed_steps=1,
        ...     status="failure",
        ... )
        >>>
        >>> # Consulta últimas execuções
        >>> recent = history.get_recent(limit=10)
    """

    INDEX_FILE = "index.json"

    def __init__(
        self,
        history_dir: str | None = None,
        enabled: bool = True,
        max_records: int = 1000,
        compress: bool = True,
    ):
        """
        Inicializa o histórico.

        ## Parâmetros:

        - `history_dir`: Diretório para histórico (default: ~/.aqa/history)
        - `enabled`: Se False, histórico é desabilitado
        - `max_records`: Número máximo de registros a manter
        - `compress`: Se True, comprime registros antigos
        """
        if history_dir:
            self.history_dir = Path(history_dir)
        else:
            self.history_dir = get_global_history_dir()

        self.enabled = enabled
        self.max_records = max_records
        self.compress = compress
        self._index: list[dict[str, Any]] = []
        self._lock = threading.Lock()

        if enabled:
            self._ensure_dir()
            self._load_index()

    def _ensure_dir(self) -> None:
        """Cria diretório de histórico se não existir."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Carrega índice do disco."""
        with self._lock:
            index_path = self.history_dir / self.INDEX_FILE
            if index_path.exists():
                try:
                    with open(index_path, "r", encoding="utf-8") as f:
                        self._index = json.load(f)
                except (json.JSONDecodeError, IOError):
                    self._index = []

    def _save_index(self) -> None:
        """Salva índice no disco. DEVE ser chamada com _lock adquirido."""
        index_path = self.history_dir / self.INDEX_FILE
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _generate_id(self) -> str:
        """Gera ID único para execução."""
        import uuid
        return uuid.uuid4().hex[:12]

    def record_execution(
        self,
        plan_file: str,
        duration_ms: int,
        total_steps: int,
        passed_steps: int,
        failed_steps: int,
        status: Literal["success", "failure", "error"],
        plan_hash: str | None = None,
        runner_report: dict[str, Any] | None = None,
    ) -> ExecutionRecord:
        """
        Registra uma execução no histórico.

        ## Parâmetros:

        - `plan_file`: Caminho do arquivo de plano executado
        - `duration_ms`: Duração total em milissegundos
        - `total_steps`: Número total de steps
        - `passed_steps`: Número de steps que passaram
        - `failed_steps`: Número de steps que falharam
        - `status`: Status final da execução
        - `plan_hash`: Hash do plano (se cacheado)
        - `runner_report`: Relatório completo do Runner

        ## Retorno:

        ExecutionRecord com os dados registrados.
        """
        if not self.enabled:
            return ExecutionRecord(
                id="disabled",
                timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                plan_file=plan_file,
                duration_ms=duration_ms,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps,
                status=status,
                plan_hash=plan_hash,
            )

        record_id = self._generate_id()
        timestamp = datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat().replace("+00:00", "Z")

        record = ExecutionRecord(
            id=record_id,
            timestamp=timestamp_str,
            plan_file=plan_file,
            duration_ms=duration_ms,
            total_steps=total_steps,
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            status=status,
            plan_hash=plan_hash,
            runner_report=runner_report,
        )

        # Cria subdiretório por data
        date_dir = self.history_dir / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        # Salva registro
        record_file = date_dir / f"{record_id}.json"
        record_data = {
            "id": record.id,
            "timestamp": record.timestamp,
            "plan_file": record.plan_file,
            "plan_hash": record.plan_hash,
            "duration_ms": record.duration_ms,
            "total_steps": record.total_steps,
            "passed_steps": record.passed_steps,
            "failed_steps": record.failed_steps,
            "status": record.status,
            "runner_report": record.runner_report,
        }

        with self._lock:
            # Salva arquivo do registro
            if self.compress:
                with gzip.open(str(record_file) + ".gz", "wt", encoding="utf-8") as f:
                    json.dump(record_data, f, indent=2, ensure_ascii=False)
            else:
                with open(record_file, "w", encoding="utf-8") as f:
                    json.dump(record_data, f, indent=2, ensure_ascii=False)

            # Atualiza índice (sem runner_report para economia de espaço)
            index_entry = {
                "id": record.id,
                "timestamp": record.timestamp,
                "plan_file": record.plan_file,
                "plan_hash": record.plan_hash,
                "duration_ms": record.duration_ms,
                "total_steps": record.total_steps,
                "passed_steps": record.passed_steps,
                "failed_steps": record.failed_steps,
                "status": record.status,
                "file": str(record_file.relative_to(self.history_dir)) + (".gz" if self.compress else ""),
            }
            self._index.insert(0, index_entry)

            # Limita número de registros
            if len(self._index) > self.max_records:
                self._index = self._index[:self.max_records]

            self._save_index()

        return record

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Retorna execuções recentes.

        ## Parâmetros:

        - `limit`: Número máximo de registros a retornar

        ## Retorno:

        Lista de metadados das execuções (sem runner_report).
        """
        if not self.enabled:
            return []

        with self._lock:
            return self._index[:limit]

    def get_by_status(
        self,
        status: Literal["success", "failure", "error"],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Filtra execuções por status.

        ## Parâmetros:

        - `status`: Status a filtrar
        - `limit`: Número máximo de registros

        ## Retorno:

        Lista de execuções com o status especificado.
        """
        if not self.enabled:
            return []

        with self._lock:
            filtered = [r for r in self._index if r.get("status") == status]
            return filtered[:limit]

    def get_full_record(self, record_id: str) -> dict[str, Any] | None:
        """
        Retorna registro completo (incluindo runner_report).

        ## Parâmetros:

        - `record_id`: ID do registro

        ## Retorno:

        Dict completo do registro ou None se não encontrado.
        """
        if not self.enabled:
            return None

        with self._lock:
            # Busca no índice
            for entry in self._index:
                if entry.get("id") == record_id:
                    file_path = self.history_dir / entry["file"]
                    if not file_path.exists():
                        return None

                    try:
                        if str(file_path).endswith(".gz"):
                            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                                return json.load(f)
                        else:
                            with open(file_path, "r", encoding="utf-8") as f:
                                return json.load(f)
                    except (json.JSONDecodeError, IOError, gzip.BadGzipFile):
                        return None

            return None

    def stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas do histórico.

        ## Retorno:

        Dict com:
        - `enabled`: Se histórico está habilitado
        - `total_records`: Número total de registros
        - `success_count`: Número de execuções bem-sucedidas
        - `failure_count`: Número de execuções com falhas
        - `error_count`: Número de execuções com erros
        - `history_dir`: Diretório do histórico
        """
        if not self.enabled:
            return {"enabled": False, "total_records": 0}

        with self._lock:
            success = sum(1 for r in self._index if r.get("status") == "success")
            failure = sum(1 for r in self._index if r.get("status") == "failure")
            error = sum(1 for r in self._index if r.get("status") == "error")

            return {
                "enabled": True,
                "total_records": len(self._index),
                "success_count": success,
                "failure_count": failure,
                "error_count": error,
                "history_dir": str(self.history_dir),
            }

    def count(self) -> int:
        """
        Retorna o número total de registros no histórico.

        ## Retorno:

        Número inteiro de registros (0 se desabilitado).

        ## Exemplo:

            >>> history = ExecutionHistory()
            >>> history.count()
            42
        """
        if not self.enabled:
            return 0

        with self._lock:
            return len(self._index)

    def delete(self, record_id: str) -> bool:
        """
        Remove um registro específico do histórico.

        ## Parâmetros:

        - `record_id`: ID do registro a remover

        ## Retorno:

        True se o registro foi removido, False se não encontrado.

        ## Exemplo:

            >>> history = ExecutionHistory()
            >>> history.delete("abc123")
            True
        """
        if not self.enabled:
            return False

        with self._lock:
            # Busca no índice
            for i, entry in enumerate(self._index):
                if entry.get("id") == record_id:
                    # Remove arquivo físico
                    file_path = self.history_dir / entry["file"]
                    if file_path.exists():
                        try:
                            file_path.unlink()
                        except (IOError, OSError):
                            pass  # Ignora erro ao deletar arquivo

                    # Remove do índice
                    self._index.pop(i)
                    self._save_index()
                    return True

            return False

    def delete_bulk(self, record_ids: list[str]) -> int:
        """
        Remove múltiplos registros do histórico de uma vez.

        ## Parâmetros:

        - `record_ids`: Lista de IDs dos registros a remover

        ## Retorno:

        Número de registros efetivamente removidos.

        ## Exemplo:

            >>> history = ExecutionHistory()
            >>> history.delete_bulk(["abc123", "def456"])
            2
        """
        if not self.enabled or not record_ids:
            return 0

        ids_set = set(record_ids)
        deleted = 0

        with self._lock:
            new_index: list[dict[str, Any]] = []
            for entry in self._index:
                if entry.get("id") in ids_set:
                    # Remove arquivo físico
                    file_path = self.history_dir / entry["file"]
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            deleted += 1
                        except (IOError, OSError):
                            pass
                else:
                    new_index.append(entry)

            self._index = new_index
            self._save_index()

        return deleted

    def clear_all(self) -> None:
        """
        Remove todos os registros do histórico.

        ## Uso:

            >>> history = ExecutionHistory()
            >>> history.clear_all()  # Remove tudo
        """
        if not self.enabled:
            return

        with self._lock:
            self._ensure_dir()
            self._index = []
            self._save_index()


# =============================================================================
# VERSIONAMENTO DE PLANOS
# =============================================================================


@dataclass
class PlanVersion:
    """
    Representa uma versão de um plano aprovado.

    ## Atributos:

    - `version`: Número da versão (1, 2, 3, ...)
    - `plan`: O plano UTDL completo
    - `created_at`: Data/hora de criação
    - `created_by`: Quem criou (usuário ou "auto")
    - `source`: Origem do plano ("llm", "manual", "import")
    - `llm_provider`: Provedor LLM usado (se aplicável)
    - `llm_model`: Modelo LLM usado (se aplicável)
    - `input_hash`: Hash do input que gerou o plano
    - `description`: Descrição/comentário da versão
    - `tags`: Tags para categorização
    - `parent_version`: Versão anterior (se for update)
    """

    version: int
    plan: dict[str, Any]
    created_at: str
    created_by: str = "auto"
    source: Literal["llm", "manual", "import"] = "llm"
    llm_provider: str | None = None
    llm_model: str | None = None
    input_hash: str | None = None
    description: str = ""
    tags: list[str] | None = None
    parent_version: int | None = None


@dataclass
class PlanDiff:
    """
    Resultado da comparação entre duas versões de um plano.

    ## Atributos:

    - `version_a`: Número da versão A
    - `version_b`: Número da versão B
    - `steps_added`: Steps adicionados em B
    - `steps_removed`: Steps removidos de A
    - `steps_modified`: Steps modificados (existem em ambos mas diferentes)
    - `config_changes`: Mudanças na configuração
    - `meta_changes`: Mudanças nos metadados
    """

    version_a: int
    version_b: int
    steps_added: list[dict[str, Any]]
    steps_removed: list[dict[str, Any]]
    steps_modified: list[dict[str, Any]]
    config_changes: dict[str, Any]
    meta_changes: dict[str, Any]

    @property
    def has_changes(self) -> bool:
        """Retorna True se houver alguma diferença."""
        return bool(
            self.steps_added
            or self.steps_removed
            or self.steps_modified
            or self.config_changes
            or self.meta_changes
        )

    @property
    def summary(self) -> str:
        """Retorna resumo das mudanças."""
        parts = []
        if self.steps_added:
            parts.append(f"+{len(self.steps_added)} steps")
        if self.steps_removed:
            parts.append(f"-{len(self.steps_removed)} steps")
        if self.steps_modified:
            parts.append(f"~{len(self.steps_modified)} modified")
        if self.config_changes:
            parts.append("config changed")
        if self.meta_changes:
            parts.append("meta changed")
        return ", ".join(parts) if parts else "no changes"


def get_global_plans_dir() -> Path:
    """
    Retorna o diretório global de planos versionados (~/.aqa/plans/).

    Respeita variável de ambiente AQA_HOME se definida.

    ## Retorno:

    Path para o diretório de planos versionados.
    """
    aqa_home = os.environ.get("AQA_HOME")
    if aqa_home:
        return Path(aqa_home) / "plans"
    return Path.home() / AQA_HOME_DIR / "plans"


class PlanVersionStore:
    """
    Armazena versões de planos aprovados com histórico completo.

    Diferente do PlanCache (que cacheia respostas LLM), este store
    mantém versões "oficiais" de planos que foram aprovados/validados.

    ## Estrutura:

    ```
    ~/.aqa/plans/
    ├── index.json              # Índice de todos os planos
    ├── my-api-tests/           # Diretório por plano (slug do nome)
    │   ├── metadata.json       # Metadados do plano
    │   ├── v1.json             # Versão 1
    │   ├── v2.json             # Versão 2
    │   └── current -> v2.json  # Link para versão atual
    └── another-plan/
        └── ...
    ```

    ## Exemplo:

        >>> store = PlanVersionStore()
        >>>
        >>> # Salva primeira versão
        >>> v1 = store.save(
        ...     plan_name="my-api-tests",
        ...     plan=plan_dict,
        ...     source="llm",
        ...     llm_provider="openai",
        ...     llm_model="gpt-4",
        ...     description="Initial version from Swagger",
        ... )
        >>>
        >>> # Atualiza para nova versão
        >>> v2 = store.save(
        ...     plan_name="my-api-tests",
        ...     plan=updated_plan,
        ...     description="Added auth steps",
        ... )
        >>>
        >>> # Compara versões
        >>> diff = store.diff("my-api-tests", 1, 2)
        >>> print(diff.summary)
        '+2 steps, ~1 modified'
    """

    INDEX_FILE = "index.json"
    METADATA_FILE = "metadata.json"
    CURRENT_LINK = "current.json"

    def __init__(
        self,
        plans_dir: str | None = None,
        enabled: bool = True,
    ):
        """
        Inicializa o store de versões.

        ## Parâmetros:

        - `plans_dir`: Diretório para planos (default: ~/.aqa/plans)
        - `enabled`: Se False, operações são no-op
        """
        if plans_dir:
            self.plans_dir = Path(plans_dir)
        else:
            self.plans_dir = get_global_plans_dir()

        self.enabled = enabled
        self._index: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

        if enabled:
            self._ensure_dir()
            self._load_index()

    @classmethod
    def global_store(cls, enabled: bool = True) -> "PlanVersionStore":
        """
        Cria store global em ~/.aqa/plans/.

        ## Parâmetros:

        - `enabled`: Se False, store é desabilitado

        ## Retorno:

        Instância configurada para uso global.
        """
        return cls(plans_dir=None, enabled=enabled)

    def _ensure_dir(self) -> None:
        """Cria diretório de planos se não existir."""
        self.plans_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Carrega índice do disco."""
        with self._lock:
            index_path = self.plans_dir / self.INDEX_FILE
            if index_path.exists():
                try:
                    with open(index_path, "r", encoding="utf-8") as f:
                        self._index = json.load(f)
                except (json.JSONDecodeError, IOError):
                    self._index = {}

    def _save_index(self) -> None:
        """Salva índice no disco. DEVE ser chamada com _lock adquirido."""
        index_path = self.plans_dir / self.INDEX_FILE
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _slugify(self, name: str) -> str:
        """
        Converte nome do plano para slug válido para diretório.

        ## Parâmetros:

        - `name`: Nome do plano

        ## Retorno:

        Slug válido (lowercase, sem espaços, sem caracteres especiais)
        """
        import re
        # Lowercase e substitui espaços por hífens
        slug = name.lower().strip().replace(" ", "-")
        # Remove caracteres não alfanuméricos (exceto hífens)
        slug = re.sub(r"[^a-z0-9\-]", "", slug)
        # Remove hífens duplicados
        slug = re.sub(r"-+", "-", slug)
        # Remove hífens no início/fim
        slug = slug.strip("-")
        return slug or "unnamed-plan"

    def _get_plan_dir(self, plan_name: str) -> Path:
        """Retorna diretório de um plano específico."""
        slug = self._slugify(plan_name)
        return self.plans_dir / slug

    def list_plans(self) -> list[dict[str, Any]]:
        """
        Lista todos os planos versionados.

        ## Retorno:

        Lista de metadados dos planos.
        """
        if not self.enabled:
            return []

        with self._lock:
            return list(self._index.values())

    def get_plan_info(self, plan_name: str) -> dict[str, Any] | None:
        """
        Retorna informações de um plano.

        ## Parâmetros:

        - `plan_name`: Nome do plano

        ## Retorno:

        Metadados do plano ou None se não existir.
        """
        if not self.enabled:
            return None

        slug = self._slugify(plan_name)
        with self._lock:
            return self._index.get(slug)

    def get_version(
        self,
        plan_name: str,
        version: int | None = None,
    ) -> PlanVersion | None:
        """
        Retorna uma versão específica do plano.

        ## Parâmetros:

        - `plan_name`: Nome do plano
        - `version`: Número da versão (None = versão atual)

        ## Retorno:

        PlanVersion ou None se não existir.
        """
        if not self.enabled:
            return None

        plan_dir = self._get_plan_dir(plan_name)
        if not plan_dir.exists():
            return None

        # Determina arquivo da versão
        if version is None:
            version_file = plan_dir / self.CURRENT_LINK
        else:
            version_file = plan_dir / f"v{version}.json"

        if not version_file.exists():
            return None

        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return PlanVersion(
                    version=data.get("version", 1),
                    plan=data.get("plan", {}),
                    created_at=data.get("created_at", ""),
                    created_by=data.get("created_by", "auto"),
                    source=data.get("source", "llm"),
                    llm_provider=data.get("llm_provider"),
                    llm_model=data.get("llm_model"),
                    input_hash=data.get("input_hash"),
                    description=data.get("description", ""),
                    tags=data.get("tags"),
                    parent_version=data.get("parent_version"),
                )
        except (json.JSONDecodeError, IOError):
            return None

    def get_current(self, plan_name: str) -> dict[str, Any] | None:
        """
        Retorna o plano da versão atual.

        Atalho para `get_version(plan_name, None).plan`.

        ## Parâmetros:

        - `plan_name`: Nome do plano

        ## Retorno:

        Dict do plano ou None se não existir.
        """
        version = self.get_version(plan_name, None)
        return version.plan if version else None

    def list_versions(self, plan_name: str) -> list[dict[str, Any]]:
        """
        Lista todas as versões de um plano.

        ## Parâmetros:

        - `plan_name`: Nome do plano

        ## Retorno:

        Lista de metadados das versões (sem o plano completo).
        """
        if not self.enabled:
            return []

        plan_dir = self._get_plan_dir(plan_name)
        if not plan_dir.exists():
            return []

        versions = []
        for file in sorted(plan_dir.glob("v*.json")):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    versions.append({
                        "version": data.get("version", 1),
                        "created_at": data.get("created_at", ""),
                        "created_by": data.get("created_by", "auto"),
                        "source": data.get("source", "llm"),
                        "description": data.get("description", ""),
                        "llm_provider": data.get("llm_provider"),
                        "llm_model": data.get("llm_model"),
                    })
            except (json.JSONDecodeError, IOError):
                continue

        return versions

    def save(
        self,
        plan_name: str,
        plan: dict[str, Any],
        *,
        source: Literal["llm", "manual", "import"] = "llm",
        llm_provider: str | None = None,
        llm_model: str | None = None,
        input_hash: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
        created_by: str = "auto",
    ) -> PlanVersion:
        """
        Salva uma nova versão do plano.

        Se o plano não existir, cria versão 1.
        Se existir, incrementa o número da versão.

        ## Parâmetros:

        - `plan_name`: Nome do plano (será convertido para slug)
        - `plan`: O plano UTDL completo
        - `source`: Origem ("llm", "manual", "import")
        - `llm_provider`: Provedor LLM usado
        - `llm_model`: Modelo LLM usado
        - `input_hash`: Hash do input (para referência ao cache)
        - `description`: Descrição da versão
        - `tags`: Tags para categorização
        - `created_by`: Identificador de quem criou

        ## Retorno:

        PlanVersion criada.
        """
        if not self.enabled:
            return PlanVersion(
                version=0,
                plan=plan,
                created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )

        slug = self._slugify(plan_name)
        plan_dir = self._get_plan_dir(plan_name)
        plan_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            # Determina próxima versão
            current_info = self._index.get(slug, {})
            current_version = current_info.get("current_version", 0)
            new_version = current_version + 1
            parent_version = current_version if current_version > 0 else None

            # Cria dados da versão
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            version_data = {
                "version": new_version,
                "plan": plan,
                "created_at": timestamp,
                "created_by": created_by,
                "source": source,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "input_hash": input_hash,
                "description": description,
                "tags": tags or [],
                "parent_version": parent_version,
            }

            # Salva arquivo da versão
            version_file = plan_dir / f"v{new_version}.json"
            with open(version_file, "w", encoding="utf-8") as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)

            # Atualiza current.json (cópia do arquivo atual)
            current_file = plan_dir / self.CURRENT_LINK
            with open(current_file, "w", encoding="utf-8") as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)

            # Atualiza índice
            self._index[slug] = {
                "name": plan_name,
                "slug": slug,
                "current_version": new_version,
                "total_versions": new_version,
                "created_at": current_info.get("created_at", timestamp),
                "updated_at": timestamp,
                "path": str(plan_dir.relative_to(self.plans_dir)),
            }
            self._save_index()

            return PlanVersion(
                version=new_version,
                plan=plan,
                created_at=timestamp,
                created_by=created_by,
                source=source,
                llm_provider=llm_provider,
                llm_model=llm_model,
                input_hash=input_hash,
                description=description,
                tags=tags,
                parent_version=parent_version,
            )

    def diff(
        self,
        plan_name: str,
        version_a: int,
        version_b: int | None = None,
    ) -> PlanDiff | None:
        """
        Compara duas versões de um plano.

        ## Parâmetros:

        - `plan_name`: Nome do plano
        - `version_a`: Primeira versão (mais antiga)
        - `version_b`: Segunda versão (None = versão atual)

        ## Retorno:

        PlanDiff com as diferenças ou None se versões não existirem.

        ## Exemplo:

            >>> diff = store.diff("my-plan", 1, 2)
            >>> print(diff.summary)
            '+1 steps, ~2 modified'
        """
        if not self.enabled:
            return None

        v_a = self.get_version(plan_name, version_a)
        v_b = self.get_version(plan_name, version_b)

        if not v_a or not v_b:
            return None

        plan_a = v_a.plan
        plan_b = v_b.plan

        # Compara steps
        steps_a = {s.get("id"): s for s in plan_a.get("steps", [])}
        steps_b = {s.get("id"): s for s in plan_b.get("steps", [])}

        steps_added = [s for sid, s in steps_b.items() if sid not in steps_a]
        steps_removed = [s for sid, s in steps_a.items() if sid not in steps_b]
        steps_modified = []

        for sid in steps_a:
            if sid in steps_b and steps_a[sid] != steps_b[sid]:
                steps_modified.append({
                    "id": sid,
                    "before": steps_a[sid],
                    "after": steps_b[sid],
                })

        # Compara config
        config_a = plan_a.get("config", {})
        config_b = plan_b.get("config", {})
        config_changes = {}
        all_keys = set(config_a.keys()) | set(config_b.keys())
        for key in all_keys:
            if config_a.get(key) != config_b.get(key):
                config_changes[key] = {
                    "before": config_a.get(key),
                    "after": config_b.get(key),
                }

        # Compara meta
        meta_a = plan_a.get("meta", {})
        meta_b = plan_b.get("meta", {})
        meta_changes = {}
        all_meta_keys = set(meta_a.keys()) | set(meta_b.keys())
        for key in all_meta_keys:
            if meta_a.get(key) != meta_b.get(key):
                meta_changes[key] = {
                    "before": meta_a.get(key),
                    "after": meta_b.get(key),
                }

        return PlanDiff(
            version_a=version_a,
            version_b=v_b.version,
            steps_added=steps_added,
            steps_removed=steps_removed,
            steps_modified=steps_modified,
            config_changes=config_changes,
            meta_changes=meta_changes,
        )

    def delete_version(self, plan_name: str, version: int) -> bool:
        """
        Remove uma versão específica do plano.

        Não permite remover a versão atual.

        ## Parâmetros:

        - `plan_name`: Nome do plano
        - `version`: Número da versão a remover

        ## Retorno:

        True se removida, False se não existia ou é a versão atual.
        """
        if not self.enabled:
            return False

        slug = self._slugify(plan_name)
        plan_dir = self._get_plan_dir(plan_name)

        with self._lock:
            info = self._index.get(slug)
            if not info:
                return False

            # Não permite remover versão atual
            if info.get("current_version") == version:
                return False

            version_file = plan_dir / f"v{version}.json"
            if not version_file.exists():
                return False

            version_file.unlink()
            return True

    def delete_plan(self, plan_name: str) -> bool:
        """
        Remove um plano e todas as suas versões.

        ## Parâmetros:

        - `plan_name`: Nome do plano

        ## Retorno:

        True se removido, False se não existia.
        """
        if not self.enabled:
            return False

        slug = self._slugify(plan_name)
        plan_dir = self._get_plan_dir(plan_name)

        with self._lock:
            if slug not in self._index:
                return False

            # Remove diretório e conteúdo
            import shutil
            if plan_dir.exists():
                shutil.rmtree(plan_dir)

            # Remove do índice
            del self._index[slug]
            self._save_index()
            return True

    def rollback(
        self,
        plan_name: str,
        target_version: int,
        description: str = "",
    ) -> PlanVersion | None:
        """
        Restaura uma versão anterior criando nova versão com o conteúdo antigo.

        O rollback não apaga versões - cria uma nova versão com o conteúdo
        da versão alvo, mantendo histórico completo.

        ## Parâmetros:

        - `plan_name`: Nome do plano
        - `target_version`: Versão para restaurar
        - `description`: Descrição opcional do rollback

        ## Retorno:

        Nova PlanVersion ou None se versão alvo não existir.

        ## Exemplo:

            >>> store.rollback("my-plan", target_version=1)
            PlanVersion(version=3, ...)  # Nova versão com conteúdo de v1
        """
        if not self.enabled:
            return None

        # Obtém versão alvo
        target = self.get_version(plan_name, target_version)
        if not target:
            return None

        # Obtém versão atual para referência
        current = self.get_version(plan_name)
        current_version = current.version if current else 0

        # Monta descrição
        if not description:
            description = f"Rollback from v{current_version} to v{target_version}"

        # Salva como nova versão
        return self.save(
            plan_name=plan_name,
            plan=target.plan,
            source="manual",
            description=description,
        )
