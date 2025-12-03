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

    Este cache NÃO é thread-safe. Para uso concorrente,
    use locks externos ou uma instância por thread.

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

        if enabled:
            self._ensure_cache_dir()
            self._load_index()

    def _ensure_cache_dir(self) -> None:
        """Cria diretório de cache se não existir."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Carrega índice do disco."""
        index_path = self.cache_dir / self.INDEX_FILE
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._index = {}

    def _save_index(self) -> None:
        """Salva índice no disco."""
        index_path = self.cache_dir / self.INDEX_FILE
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _compute_hash(self, requirements: str, base_url: str) -> str:
        """
        Calcula hash único do input.

        Usa SHA256 para garantir unicidade.
        Normaliza o input antes de hashear.
        """
        # Normaliza: lowercase, trim, ordena URLs
        normalized = f"{requirements.strip().lower()}|{base_url.strip().lower()}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def get(self, requirements: str, base_url: str) -> dict[str, Any] | None:
        """
        Busca plano no cache.

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API

        ## Retorno:

        - Dict do plano se encontrado
        - None se não encontrado ou cache desabilitado
        """
        if not self.enabled:
            return None

        hash_key = self._compute_hash(requirements, base_url)

        if hash_key not in self._index:
            return None

        filename = self._index[hash_key]
        filepath = self.cache_dir / filename

        if not filepath.exists():
            # Arquivo foi deletado, limpa índice
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
        plan: dict[str, Any]
    ) -> str:
        """
        Armazena plano no cache.

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API
        - `plan`: Plano UTDL a cachear

        ## Retorno:

        Hash do entry (para referência)
        """
        if not self.enabled:
            return ""

        hash_key = self._compute_hash(requirements, base_url)
        filename = f"{hash_key}.json"
        filepath = self.cache_dir / filename

        # Cria entrada
        entry: dict[str, Any] = {
            "hash": hash_key,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "input_summary": requirements[:100] + ("..." if len(requirements) > 100 else ""),
            "base_url": base_url,
            "plan": plan,
        }

        # Salva arquivo
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

        # Atualiza índice
        self._index[hash_key] = filename
        self._save_index()

        return hash_key

    def invalidate(self, requirements: str, base_url: str) -> bool:
        """
        Remove entrada do cache.

        ## Parâmetros:

        - `requirements`: Requisitos em linguagem natural
        - `base_url`: URL base da API

        ## Retorno:

        True se entry foi removida, False se não existia
        """
        if not self.enabled:
            return False

        hash_key = self._compute_hash(requirements, base_url)

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

        ## Retorno:

        Número de entries removidas
        """
        if not self.enabled:
            return 0

        count = len(self._index)

        # Remove todos os arquivos
        for filename in self._index.values():
            filepath = self.cache_dir / filename
            if filepath.exists():
                filepath.unlink()

        # Limpa índice
        self._index = {}
        self._save_index()

        return count

    def stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas do cache.

        ## Retorno:

        Dict com:
        - `enabled`: Se cache está habilitado
        - `entries`: Número de entries
        - `cache_dir`: Diretório do cache
        """
        if not self.enabled:
            return {"enabled": False, "entries": 0}

        return {
            "enabled": True,
            "entries": len(self._index),
            "cache_dir": str(self.cache_dir),
        }
