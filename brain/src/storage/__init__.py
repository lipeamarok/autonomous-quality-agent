"""
================================================================================
STORAGE MODULE - Persistent Storage for Execution History
================================================================================

Este módulo fornece backends de armazenamento persistente para o histórico
de execuções do AQA, suportando SQLite (local) e S3 (cloud).

## Arquitetura:

```
                    ┌─────────────────────────────┐
                    │      StorageBackend         │
                    │       (Protocol)            │
                    └─────────────────────────────┘
                              ▲
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────┴───────┐ ┌─────┴─────┐ ┌───────┴───────┐
    │  SQLiteBackend  │ │ S3Backend │ │ JsonBackend   │
    │   (default)     │ │  (cloud)  │ │  (legacy)     │
    └─────────────────┘ └───────────┘ └───────────────┘
```

## Por que múltiplos backends?

1. **SQLite (default)**: Rápido, confiável, sem dependências externas
2. **S3**: Escalável, durável, compartilhável entre ambientes
3. **JSON (legacy)**: Compatibilidade com versões anteriores

## Uso:

```python
from src.storage import create_storage, SQLiteStorage, S3Storage

# Automático baseado em variáveis de ambiente
storage = create_storage()

# SQLite explícito
storage = SQLiteStorage(db_path="~/.aqa/history.db")

# S3 explícito
storage = S3Storage(
    bucket="my-aqa-bucket",
    prefix="history/",
    region="us-east-1",
)

# Operações
storage.save_execution(record)
recent = storage.list_executions(limit=10)
full = storage.get_execution("abc123")
storage.delete_execution("abc123")
```

## Configuração via variáveis de ambiente:

- `AQA_STORAGE_BACKEND`: "sqlite" | "s3" | "json" (default: "sqlite")
- `AQA_STORAGE_PATH`: Caminho do banco SQLite (default: ~/.aqa/history.db)
- `AQA_S3_BUCKET`: Nome do bucket S3
- `AQA_S3_PREFIX`: Prefixo para objetos no S3 (default: "aqa/history/")
- `AQA_S3_REGION`: Região AWS (default: us-east-1)
"""

from .base import (
    StorageBackend,
    ExecutionRecord,
    StorageError,
    StorageNotFoundError,
    StorageConnectionError,
    StorageStats,
)
from .sqlite import SQLiteStorage
from .s3 import S3Storage
from .json_backend import JsonStorage
from .factory import create_storage, get_default_storage

__all__ = [
    # Protocol and types
    "StorageBackend",
    "ExecutionRecord",
    "StorageError",
    "StorageNotFoundError",
    "StorageConnectionError",
    "StorageStats",
    # Backends
    "SQLiteStorage",
    "S3Storage",
    "JsonStorage",
    # Factory
    "create_storage",
    "get_default_storage",
]
