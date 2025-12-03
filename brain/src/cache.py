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

```
.brain_cache/
├── index.json          # Mapa de hash → arquivo
├── abc123.json         # Plano cacheado
├── def456.json         # Outro plano
└── ...
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
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """
    Entrada no cache de planos.

    ## Atributos:

    - `hash`: Hash único do input
    - `created_at`: Data/hora de criação
    - `input_summary`: Resumo do input (para debug)
    - `plan`: O plano cacheado
    """
    hash: str
    created_at: str
    input_summary: str
    plan: dict[str, Any]


class PlanCache:
    """
    Cache de planos baseado em hash dos inputs.

    Este cache persiste em disco e sobrevive entre execuções.
    Usa hash SHA256 para gerar fingerprints únicos.

    ## Thread Safety:

    Este cache é thread-safe. Usa locks por hash para permitir
    operações concorrentes em entradas diferentes enquanto
    serializa operações na mesma entrada.

    ## Exemplo:

        >>> cache = PlanCache(cache_dir=".brain_cache")
        >>>
        >>> # Verifica se existe
        >>> existing = cache.get("teste API login", "https://api.example.com")
        >>>
        >>> # Armazena novo
        >>> cache.store("teste API login", "https://api.example.com", plan_dict)
    """

    INDEX_FILE = "index.json"

    def __init__(self, cache_dir: str = ".brain_cache", enabled: bool = True):
        """
        Inicializa o cache.

        ## Parâmetros:

        - `cache_dir`: Diretório para armazenar cache
        - `enabled`: Se False, cache é desabilitado (always miss)
        """
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self._index: dict[str, str] = {}  # hash → filename

        # Lock global para operações no índice
        self._index_lock = threading.Lock()

        # Locks por hash para operações em entradas individuais
        self._hash_locks: dict[str, threading.Lock] = {}
        self._hash_locks_lock = threading.Lock()

        if enabled:
            self._ensure_cache_dir()
            self._load_index()

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
                        self._index = json.load(f)
                except (json.JSONDecodeError, IOError):
                    self._index = {}

    def _save_index(self) -> None:
        """Salva índice no disco. DEVE ser chamada com _index_lock adquirido."""
        index_path = self.cache_dir / self.INDEX_FILE
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

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

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API
        - `provider`: Provedor LLM (opcional, mas recomendado)
        - `model`: Modelo LLM (opcional, mas recomendado)

        ## Retorno:

        - Dict do plano se encontrado
        - None se não encontrado ou cache desabilitado

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
                filename = self._index[hash_key]

            filepath = self.cache_dir / filename

            if not filepath.exists():
                # Arquivo foi deletado, limpa índice
                with self._index_lock:
                    if hash_key in self._index:
                        del self._index[hash_key]
                        self._save_index()
                return None

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                    return entry.get("plan")
            except (json.JSONDecodeError, IOError):
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
        filename = f"{hash_key}.json"
        filepath = self.cache_dir / filename

        with hash_lock:
            # Cria entrada
            entry: dict[str, Any] = {
                "hash": hash_key,
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "input_summary": requirements[:100] + ("..." if len(requirements) > 100 else ""),
                "base_url": base_url,
                "provider": provider,
                "model": model,
                "plan": plan,
            }

            # Salva arquivo
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)

            # Atualiza índice
            with self._index_lock:
                self._index[hash_key] = filename
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

                filename = self._index[hash_key]
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
            for filename in self._index.values():
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

    def stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas do cache.

        Thread-safe: usa lock para leitura consistente.

        ## Retorno:

        Dict com:
        - `enabled`: Se cache está habilitado
        - `entries`: Número de entries
        - `cache_dir`: Diretório do cache
        """
        if not self.enabled:
            return {"enabled": False, "entries": 0}

        with self._index_lock:
            return {
                "enabled": True,
                "entries": len(self._index),
                "cache_dir": str(self.cache_dir),
            }
