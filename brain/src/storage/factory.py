"""
================================================================================
Storage Factory
================================================================================

Factory para criar instâncias de storage baseado em configuração.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from .base import StorageBackend
from .json_backend import JsonStorage
from .s3 import S3Storage
from .sqlite import SQLiteStorage


BackendType = Literal["sqlite", "s3", "json"]


def create_storage(
    backend: BackendType | None = None,
    **kwargs: Any,
) -> StorageBackend:
    """
    Cria uma instância de storage baseada no backend especificado.

    ## Parâmetros:

    - `backend`: Tipo de backend ("sqlite", "s3", "json")
    - `**kwargs`: Argumentos específicos do backend

    ## Variáveis de Ambiente:

    - `AQA_STORAGE_BACKEND`: Tipo de backend (default: "sqlite")
    - `AQA_STORAGE_PATH`: Caminho do armazenamento
    - `AQA_S3_BUCKET`: Nome do bucket S3
    - `AQA_S3_PREFIX`: Prefixo S3 (default: "aqa/history/")
    - `AQA_S3_REGION`: Região AWS (default: "us-east-1")

    ## Retorno:

    Instância de StorageBackend.

    ## Exemplo:

        >>> # Automático baseado em env vars
        >>> storage = create_storage()

        >>> # SQLite explícito
        >>> storage = create_storage("sqlite", db_path="./history.db")

        >>> # S3 explícito
        >>> storage = create_storage("s3", bucket="my-bucket")

        >>> # JSON (legacy)
        >>> storage = create_storage("json", history_dir="./history")
    """
    if backend is None:
        backend = os.environ.get("AQA_STORAGE_BACKEND", "sqlite")  # type: ignore

    backend = backend.lower()  # type: ignore

    if backend == "sqlite":
        return SQLiteStorage(
            db_path=kwargs.get("db_path"),
            compress_reports=kwargs.get("compress_reports", True),
        )
    elif backend == "s3":
        return S3Storage(
            bucket=kwargs.get("bucket"),
            prefix=kwargs.get("prefix", "aqa/history/"),
            region=kwargs.get("region", "us-east-1"),
            compress=kwargs.get("compress", True),
        )
    elif backend == "json":
        return JsonStorage(
            history_dir=kwargs.get("history_dir"),
            compress=kwargs.get("compress", True),
            max_records=kwargs.get("max_records", 1000),
        )
    else:
        raise ValueError(
            f"Unknown storage backend: {backend}. "
            f"Valid options: sqlite, s3, json"
        )


def get_default_storage() -> StorageBackend:
    """
    Cria storage com configuração padrão.

    Detecta automaticamente o melhor backend baseado em variáveis
    de ambiente.

    ## Lógica de detecção:

    1. Se `AQA_S3_BUCKET` definido → S3Storage
    2. Se `AQA_STORAGE_BACKEND` definido → usa esse backend
    3. Fallback → SQLiteStorage

    ## Retorno:

    Instância de StorageBackend pronta para uso.

    ## Exemplo:

        >>> storage = get_default_storage()
        >>> storage.save(record)
    """
    # Verifica se S3 está configurado
    if os.environ.get("AQA_S3_BUCKET"):
        return create_storage("s3")

    # Usa backend configurado ou SQLite como default
    return create_storage()


def migrate_json_to_sqlite(
    json_dir: str | None = None,
    sqlite_path: str | None = None,
    delete_json: bool = False,
) -> int:
    """
    Utilitário para migrar de JsonStorage para SQLiteStorage.

    ## Parâmetros:

    - `json_dir`: Diretório do JsonStorage (default: ~/.aqa/history)
    - `sqlite_path`: Caminho do SQLite (default: ~/.aqa/history.db)
    - `delete_json`: Se True, remove arquivos JSON após migração

    ## Retorno:

    Número de registros migrados.

    ## Exemplo:

        >>> count = migrate_json_to_sqlite()
        >>> print(f"Migrated {count} records")
    """
    json_storage = JsonStorage(history_dir=json_dir)
    sqlite_storage = SQLiteStorage(db_path=sqlite_path)

    migrated = 0
    errors = 0

    try:
        records = json_storage.list(limit=10000)
        for record_summary in records:
            try:
                record = json_storage.get(record_summary.id)
                sqlite_storage.save(record)
                migrated += 1
            except Exception:
                errors += 1

        if delete_json and migrated > 0:
            json_storage.clear()

        return migrated
    finally:
        sqlite_storage.close()
