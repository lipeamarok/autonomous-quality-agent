"""
================================================================================
Autenticação da API
================================================================================

Implementa autenticação via API Key para a API REST do AQA.

## Modos de Autenticação:

- `none`: Sem autenticação (desenvolvimento local)
- `apikey`: Autenticação via header X-API-Key

## Configuração:

```bash
# Modo de autenticação
AQA_AUTH_MODE=apikey  # none | apikey

# Chave mestra (para gerar/revogar keys)
AQA_AUTH_MASTER_KEY=sua-chave-secreta

# Keys válidas (separadas por vírgula)
AQA_API_KEYS=key1,key2,key3
```

## Uso:

```python
from fastapi import Depends
from src.api.auth import require_api_key

@router.get("/protected")
async def protected_endpoint(api_key: str = Depends(require_api_key)):
    return {"message": "Authenticated!", "key_prefix": api_key[:8]}
```
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================


class AuthMode(str, Enum):
    """Modos de autenticação suportados."""

    NONE = "none"
    API_KEY = "apikey"


@dataclass
class AuthConfig:
    """
    Configuração de autenticação.

    ## Atributos:

    - `mode`: Modo de autenticação (none, apikey)
    - `master_key`: Chave mestra para gerenciar API keys
    - `api_keys`: Set de API keys válidas
    - `key_prefix`: Prefixo das API keys geradas
    """

    mode: AuthMode = AuthMode.NONE
    master_key: str | None = None
    api_keys: set[str] = field(default_factory=lambda: set())
    key_prefix: str = "aqa_"

    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        mode_str = os.environ.get("AQA_AUTH_MODE", "none").lower()
        try:
            mode = AuthMode(mode_str)
        except ValueError:
            mode = AuthMode.NONE

        # Carrega API keys do ambiente
        keys_str = os.environ.get("AQA_API_KEYS", "")
        api_keys = {k.strip() for k in keys_str.split(",") if k.strip()}

        return cls(
            mode=mode,
            master_key=os.environ.get("AQA_AUTH_MASTER_KEY"),
            api_keys=api_keys,
            key_prefix=os.environ.get("AQA_API_KEY_PREFIX", "aqa_"),
        )

    @property
    def is_enabled(self) -> bool:
        """Retorna True se autenticação está habilitada."""
        return self.mode != AuthMode.NONE


# Configuração global (lazy loading)
_auth_config: AuthConfig | None = None


def get_auth_config() -> AuthConfig:
    """Retorna configuração de autenticação (singleton)."""
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthConfig.from_env()
    return _auth_config


def reset_auth_config() -> None:
    """Reseta configuração (para testes)."""
    global _auth_config
    _auth_config = None


# =============================================================================
# API KEY MANAGEMENT
# =============================================================================


def generate_api_key(prefix: str = "aqa_") -> str:
    """
    Gera uma nova API key segura.

    ## Formato:

    `{prefix}{32 caracteres aleatórios}`

    ## Exemplo:

        >>> key = generate_api_key()
        >>> key
        'aqa_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
    """
    random_part = secrets.token_hex(16)  # 32 caracteres hex
    return f"{prefix}{random_part}"


def hash_api_key(key: str) -> str:
    """
    Gera hash seguro de uma API key para armazenamento.

    Usa SHA-256 com salt derivado do próprio key prefix.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str, config: AuthConfig | None = None) -> bool:
    """
    Verifica se uma API key é válida.

    ## Parâmetros:

    - `key`: API key a verificar
    - `config`: Configuração (usa global se None)

    ## Retorna:

    True se a key é válida, False caso contrário.
    """
    if config is None:
        config = get_auth_config()

    # Em modo none, qualquer key é válida
    if not config.is_enabled:
        return True

    # Verifica se a key está na lista de keys válidas
    return key in config.api_keys


# =============================================================================
# FASTAPI DEPENDENCIES
# =============================================================================

# Header para API Key
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API Key para autenticação. Obtenha em /api/v1/auth/keys",
)


async def get_api_key_from_request(
    request: Request,
    api_key_header_value: str | None = Depends(api_key_header),
) -> str | None:
    """
    Extrai API key do request (header ou query param).

    Ordem de prioridade:
    1. Header X-API-Key
    2. Query param ?api_key=xxx
    """
    # Tenta header primeiro
    if api_key_header_value:
        return api_key_header_value

    # Fallback para query param
    return request.query_params.get("api_key")


async def require_api_key(
    api_key: str | None = Depends(get_api_key_from_request),
) -> str:
    """
    Dependency que exige API key válida.

    ## Uso:

        >>> @router.get("/protected")
        >>> async def endpoint(key: str = Depends(require_api_key)):
        ...     pass

    ## Erros:

    - 401: API key não fornecida
    - 403: API key inválida
    """
    config = get_auth_config()

    # Em modo none, não exige autenticação
    if not config.is_enabled:
        return "anonymous"

    # Verifica se key foi fornecida
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "E4001",
                "message": "API key não fornecida",
                "hint": "Inclua header X-API-Key ou query param ?api_key=xxx",
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Verifica se key é válida
    if not verify_api_key(api_key, config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "E4003",
                "message": "API key inválida",
                "hint": "Verifique se a key está correta e não foi revogada",
            },
        )

    return api_key


async def require_master_key(
    api_key: str | None = Depends(get_api_key_from_request),
) -> str:
    """
    Dependency que exige a master key (para gerenciamento de keys).

    Usada apenas em endpoints de criação/revogação de API keys.
    """
    config = get_auth_config()

    # Verifica se key foi fornecida
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "E4001",
                "message": "Master key não fornecida",
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Verifica se é a master key
    if not config.master_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "E5003",
                "message": "Gerenciamento de keys não configurado",
                "hint": "Configure AQA_AUTH_MASTER_KEY no servidor",
            },
        )

    # Comparação segura contra timing attacks
    if not hmac.compare_digest(api_key, config.master_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "E4003",
                "message": "Master key inválida",
            },
        )

    return api_key


def optional_api_key(
    api_key: str | None = Depends(get_api_key_from_request),
) -> str | None:
    """
    Dependency que aceita API key opcional.

    Útil para endpoints que funcionam com ou sem autenticação,
    mas oferecem mais funcionalidades para usuários autenticados.
    """
    if api_key and verify_api_key(api_key):
        return api_key
    return None


# =============================================================================
# API KEY STORE (In-Memory para MVP)
# =============================================================================


@dataclass
class APIKeyInfo:
    """Informações sobre uma API key."""

    key_hash: str
    key_prefix: str  # Primeiros 8 caracteres para identificação
    created_at: float
    description: str = ""
    last_used_at: float | None = None
    usage_count: int = 0


class APIKeyStore:
    """
    Armazena e gerencia API keys.

    ## Para MVP:

    Armazenamento em memória. Em produção, usar banco de dados.

    ## Uso:

        >>> store = APIKeyStore()
        >>> key = store.create_key("Minha aplicação")
        >>> store.validate(key)
        True
        >>> store.revoke(key)
        >>> store.validate(key)
        False
    """

    def __init__(self) -> None:
        self._keys: dict[str, APIKeyInfo] = {}
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Carrega keys pré-configuradas do ambiente."""
        config = get_auth_config()
        for key in config.api_keys:
            key_hash = hash_api_key(key)
            self._keys[key_hash] = APIKeyInfo(
                key_hash=key_hash,
                key_prefix=key[:8] if len(key) >= 8 else key,
                created_at=time.time(),
                description="Pre-configured key from environment",
            )

    def create_key(self, description: str = "") -> str:
        """
        Cria uma nova API key.

        Retorna a key em texto plano (só mostrada uma vez).
        """
        config = get_auth_config()
        key = generate_api_key(config.key_prefix)
        key_hash = hash_api_key(key)

        self._keys[key_hash] = APIKeyInfo(
            key_hash=key_hash,
            key_prefix=key[:8],
            created_at=time.time(),
            description=description,
        )

        # Adiciona à config para validação
        config.api_keys.add(key)

        return key

    def validate(self, key: str) -> bool:
        """Valida uma API key."""
        key_hash = hash_api_key(key)
        if key_hash in self._keys:
            # Atualiza estatísticas
            info = self._keys[key_hash]
            info.last_used_at = time.time()
            info.usage_count += 1
            return True
        return False

    def revoke(self, key: str) -> bool:
        """Revoga uma API key."""
        key_hash = hash_api_key(key)
        if key_hash in self._keys:
            del self._keys[key_hash]
            # Remove da config
            config = get_auth_config()
            config.api_keys.discard(key)
            return True
        return False

    def list_keys(self) -> list[dict[str, Any]]:
        """Lista todas as keys (sem revelar os valores)."""
        return [
            {
                "prefix": info.key_prefix + "...",
                "created_at": info.created_at,
                "description": info.description,
                "last_used_at": info.last_used_at,
                "usage_count": info.usage_count,
            }
            for info in self._keys.values()
        ]


# Store global (singleton)
_key_store: APIKeyStore | None = None


def get_key_store() -> APIKeyStore:
    """Retorna o store de API keys (singleton)."""
    global _key_store
    if _key_store is None:
        _key_store = APIKeyStore()
    return _key_store


def reset_key_store() -> None:
    """Reseta o store (para testes)."""
    global _key_store
    _key_store = None
