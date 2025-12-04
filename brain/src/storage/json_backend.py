"""
================================================================================
JSON File Storage Backend (Legacy)
================================================================================

Backend de armazenamento usando arquivos JSON para compatibilidade
com versões anteriores do AQA.

## Estrutura:

```
~/.aqa/history/
├── index.json           # Índice de todos os registros
├── 2024-01-15/          # Subdiretório por data
│   ├── abc123.json      # Registro individual
│   └── def456.json.gz   # Registro comprimido
└── 2024-01-16/
    └── ...
```

## Uso:

```python
from src.storage import JsonStorage

storage = JsonStorage(history_dir="~/.aqa/history")
storage.save(record)
```

## Migração:

Para migrar de JsonStorage para SQLiteStorage:

```python
from src.storage import JsonStorage, SQLiteStorage

# Carrega do JSON
json_storage = JsonStorage()
records = json_storage.list(limit=10000)

# Migra para SQLite
sqlite_storage = SQLiteStorage()
for record in records:
    full_record = json_storage.get(record.id)
    sqlite_storage.save(full_record)
```
"""

from __future__ import annotations

import gzip
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .base import (
    ExecutionRecord,
    StorageBackend,
    StorageError,
    StorageNotFoundError,
    StorageStats,
)


# Constantes
DEFAULT_HISTORY_DIR = "~/.aqa/history"


class JsonStorage(StorageBackend):
    """
    Backend JSON para armazenamento de histórico (legacy).

    Mantém compatibilidade com a estrutura de arquivos anterior.
    Recomendamos migrar para SQLiteStorage para melhor performance.

    ## Parâmetros:

    - `history_dir`: Diretório para arquivos (default: ~/.aqa/history)
    - `compress`: Se True, comprime registros com gzip
    - `max_records`: Número máximo de registros no índice

    ## Exemplo:

        >>> storage = JsonStorage()
        >>> storage.save(record)
        >>> recent = storage.list(limit=10)
        >>> storage.close()
    """

    INDEX_FILE = "index.json"

    def __init__(
        self,
        history_dir: str | None = None,
        compress: bool = True,
        max_records: int = 1000,
    ) -> None:
        """Inicializa o storage JSON."""
        if history_dir is None:
            history_dir = os.environ.get("AQA_STORAGE_PATH", DEFAULT_HISTORY_DIR)

        self.history_dir = Path(os.path.expanduser(os.path.expandvars(history_dir)))
        self.compress = compress
        self.max_records = max_records
        self._index: list[dict[str, Any]] = []
        self._lock = threading.Lock()

        # Cria diretório se necessário
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._load_index()

    def _load_index(self) -> None:
        """Carrega índice do disco."""
        index_path = self.history_dir / self.INDEX_FILE
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._index = []

    def _save_index(self) -> None:
        """Salva índice no disco."""
        index_path = self.history_dir / self.INDEX_FILE
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _make_path(self, record: ExecutionRecord) -> Path:
        """Gera caminho para um registro baseado na data."""
        try:
            dt = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
            date_dir = dt.strftime("%Y-%m-%d")
        except ValueError:
            date_dir = "unknown"

        subdir = self.history_dir / date_dir
        subdir.mkdir(parents=True, exist_ok=True)

        ext = ".json.gz" if self.compress else ".json"
        return subdir / f"{record.id}{ext}"

    def save(self, record: ExecutionRecord) -> None:
        """Salva um registro de execução."""
        try:
            file_path = self._make_path(record)

            # Serializa registro
            data = json.dumps(record.to_dict(), indent=2, ensure_ascii=False)

            # Salva arquivo
            if self.compress:
                with gzip.open(file_path, "wt", encoding="utf-8") as f:
                    f.write(data)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(data)

            with self._lock:
                # Atualiza índice
                index_entry: dict[str, Any] = {
                    "id": record.id,
                    "timestamp": record.timestamp,
                    "plan_file": record.plan_file,
                    "plan_hash": record.plan_hash,
                    "plan_name": record.plan_name,
                    "status": record.status,
                    "duration_ms": record.duration_ms,
                    "total_steps": record.total_steps,
                    "passed_steps": record.passed_steps,
                    "failed_steps": record.failed_steps,
                    "tags": record.tags,
                    "file": str(file_path.relative_to(self.history_dir)),
                }

                # Remove entrada antiga se existir
                self._index = [e for e in self._index if e.get("id") != record.id]
                self._index.insert(0, index_entry)

                # Limita tamanho
                if len(self._index) > self.max_records:
                    self._index = self._index[: self.max_records]

                self._save_index()

        except Exception as e:
            raise StorageError(f"Failed to save record: {e}") from e

    def get(self, record_id: str) -> ExecutionRecord:
        """Obtém um registro por ID."""
        with self._lock:
            entry = next(
                (e for e in self._index if e.get("id") == record_id), None
            )

        if entry is None:
            raise StorageNotFoundError(f"Record not found: {record_id}")

        try:
            file_path = self.history_dir / entry["file"]

            if not file_path.exists():
                raise StorageNotFoundError(f"Record file not found: {record_id}")

            if str(file_path).endswith(".gz"):
                with gzip.open(file_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            return ExecutionRecord.from_dict(data)

        except (json.JSONDecodeError, gzip.BadGzipFile, IOError) as e:
            raise StorageError(f"Failed to read record: {e}") from e

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Literal["success", "failure", "error"] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        tags: list[str] | None = None,
    ) -> list[ExecutionRecord]:
        """Lista registros com filtros opcionais."""
        with self._lock:
            filtered = self._index.copy()

        # Aplica filtros
        if status is not None:
            filtered = [e for e in filtered if e.get("status") == status]

        if start_date is not None:
            filtered = [e for e in filtered if e.get("timestamp", "") >= start_date]

        if end_date is not None:
            filtered = [e for e in filtered if e.get("timestamp", "") <= end_date]

        if tags:
            filtered = [
                e
                for e in filtered
                if all(tag in e.get("tags", []) for tag in tags)
            ]

        # Paginação
        paginated = filtered[offset : offset + limit]

        # Converte para ExecutionRecord (sem runner_report)
        return [
            ExecutionRecord(
                id=e["id"],
                timestamp=e["timestamp"],
                plan_file=e["plan_file"],
                plan_hash=e.get("plan_hash"),
                plan_name=e.get("plan_name"),
                status=e["status"],
                duration_ms=e["duration_ms"],
                total_steps=e["total_steps"],
                passed_steps=e["passed_steps"],
                failed_steps=e["failed_steps"],
                tags=e.get("tags", []),
            )
            for e in paginated
        ]

    def delete(self, record_id: str) -> bool:
        """Remove um registro."""
        with self._lock:
            entry = next(
                (e for e in self._index if e.get("id") == record_id), None
            )

            if entry is None:
                return False

            try:
                file_path = self.history_dir / entry["file"]
                if file_path.exists():
                    file_path.unlink()

                self._index = [e for e in self._index if e.get("id") != record_id]
                self._save_index()
                return True

            except Exception as e:
                raise StorageError(f"Failed to delete record: {e}") from e

    def stats(self) -> StorageStats:
        """Retorna estatísticas do storage."""
        with self._lock:
            total = len(self._index)
            success = sum(1 for e in self._index if e.get("status") == "success")
            failure = sum(1 for e in self._index if e.get("status") == "failure")
            error = sum(1 for e in self._index if e.get("status") == "error")

            oldest = self._index[-1]["timestamp"] if self._index else None
            newest = self._index[0]["timestamp"] if self._index else None

        # Calcula tamanho do diretório
        size_bytes = 0
        try:
            for path in self.history_dir.rglob("*"):
                if path.is_file():
                    size_bytes += path.stat().st_size
        except OSError:
            pass

        return StorageStats(
            backend="json",
            total_records=total,
            success_count=success,
            failure_count=failure,
            error_count=error,
            storage_size_bytes=size_bytes,
            oldest_record=oldest,
            newest_record=newest,
        )

    def close(self) -> None:
        """Fecha o storage (noop para JSON)."""
        pass

    def clear(self) -> int:
        """Remove todos os registros."""
        with self._lock:
            count = len(self._index)

            # Remove arquivos
            for entry in self._index:
                try:
                    file_path = self.history_dir / entry["file"]
                    if file_path.exists():
                        file_path.unlink()
                except OSError:
                    pass

            # Limpa índice
            self._index = []
            self._save_index()
            return count

    def __enter__(self) -> "JsonStorage":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def migrate_to_sqlite(self, sqlite_path: str | None = None) -> int:
        """
        Migra registros para SQLite.

        ## Parâmetros:

        - `sqlite_path`: Caminho do banco SQLite (default: ~/.aqa/history.db)

        ## Retorno:

        Número de registros migrados.
        """
        from .sqlite import SQLiteStorage

        sqlite_storage = SQLiteStorage(db_path=sqlite_path)
        migrated = 0

        try:
            for entry in self._index:
                try:
                    record = self.get(entry["id"])
                    sqlite_storage.save(record)
                    migrated += 1
                except Exception:
                    pass  # Ignora registros inválidos

            return migrated
        finally:
            sqlite_storage.close()
