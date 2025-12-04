"""
================================================================================
SQLite Storage Backend
================================================================================

Backend de armazenamento usando SQLite para persistência local.
É o backend padrão e recomendado para a maioria dos casos de uso.

## Vantagens:

1. **Zero dependências**: SQLite vem com Python
2. **Rápido**: Acesso local, sem latência de rede
3. **Robusto**: ACID compliant, transações atômicas
4. **Portável**: Um único arquivo .db

## Schema:

```sql
CREATE TABLE executions (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    plan_file TEXT NOT NULL,
    plan_hash TEXT,
    plan_name TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    total_steps INTEGER NOT NULL,
    passed_steps INTEGER NOT NULL,
    failed_steps INTEGER NOT NULL,
    runner_version TEXT,
    runner_report TEXT,  -- JSON compressed
    tags TEXT,           -- JSON array
    metadata TEXT,       -- JSON object
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timestamp ON executions(timestamp DESC);
CREATE INDEX idx_status ON executions(status);
CREATE INDEX idx_plan_hash ON executions(plan_hash);
```

## Uso:

```python
from src.storage import SQLiteStorage

# Padrão: ~/.aqa/history.db
storage = SQLiteStorage()

# Caminho customizado
storage = SQLiteStorage(db_path="/path/to/history.db")

# Em memória (testes)
storage = SQLiteStorage(db_path=":memory:")

# Com compressão de reports
storage = SQLiteStorage(compress_reports=True)
```
"""

from __future__ import annotations

import gzip
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Literal

from .base import (
    ExecutionRecord,
    StorageBackend,
    StorageError,
    StorageNotFoundError,
    StorageStats,
)


# Constantes
DEFAULT_DB_PATH = "~/.aqa/history.db"
SCHEMA_VERSION = 1


class SQLiteStorage(StorageBackend):
    """
    Backend SQLite para armazenamento de histórico.

    Thread-safe através de connection pooling e locks.
    Suporta compressão de runner_report para economia de espaço.

    ## Parâmetros:

    - `db_path`: Caminho do arquivo .db (default: ~/.aqa/history.db)
    - `compress_reports`: Se True, comprime runner_report com gzip
    - `max_connections`: Pool de conexões (default: 5)

    ## Exemplo:

        >>> storage = SQLiteStorage()
        >>> storage.save(record)
        >>> recent = storage.list(limit=10)
        >>> storage.close()
    """

    def __init__(
        self,
        db_path: str | None = None,
        compress_reports: bool = True,
        max_connections: int = 5,
    ) -> None:
        """Inicializa o storage SQLite."""
        if db_path is None:
            db_path = os.environ.get("AQA_STORAGE_PATH", DEFAULT_DB_PATH)

        # Expande ~ e variáveis de ambiente
        self.db_path = Path(os.path.expanduser(os.path.expandvars(db_path)))
        self.compress_reports = compress_reports
        self._local = threading.local()
        self._lock = threading.Lock()
        self._closed = False

        # Cria diretório pai se necessário
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Inicializa schema
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Obtém conexão thread-local."""
        if self._closed:
            raise StorageError("Storage is closed")

        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            conn.row_factory = sqlite3.Row
            # Otimizações de performance
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            self._local.connection = conn

        return conn

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager para transações."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_schema(self) -> None:
        """Inicializa o schema do banco."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                # Tabela principal de execuções
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS executions (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        plan_file TEXT NOT NULL,
                        plan_hash TEXT,
                        plan_name TEXT,
                        status TEXT NOT NULL CHECK(status IN ('success', 'failure', 'error')),
                        duration_ms INTEGER NOT NULL,
                        total_steps INTEGER NOT NULL,
                        passed_steps INTEGER NOT NULL,
                        failed_steps INTEGER NOT NULL,
                        runner_version TEXT,
                        runner_report BLOB,
                        tags TEXT DEFAULT '[]',
                        metadata TEXT DEFAULT '{}',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Índices para consultas frequentes
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_executions_timestamp "
                    "ON executions(timestamp DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_executions_status "
                    "ON executions(status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_executions_plan_hash "
                    "ON executions(plan_hash)"
                )

                # Tabela de metadados do schema
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                    """
                )

                # Verifica versão do schema
                cursor.execute(
                    "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, ?)",
                    ("version", str(SCHEMA_VERSION)),
                )

                conn.commit()
            finally:
                cursor.close()

    def _serialize_report(self, report: dict[str, Any] | None) -> bytes | None:
        """Serializa runner_report, opcionalmente comprimindo."""
        if report is None:
            return None

        json_bytes = json.dumps(report, ensure_ascii=False).encode("utf-8")

        if self.compress_reports:
            return gzip.compress(json_bytes)
        return json_bytes

    def _deserialize_report(self, data: bytes | None) -> dict[str, Any] | None:
        """Deserializa runner_report."""
        if data is None:
            return None

        try:
            # Tenta descomprimir
            if self.compress_reports:
                try:
                    decompressed = gzip.decompress(data)
                    return json.loads(decompressed.decode("utf-8"))
                except gzip.BadGzipFile:
                    # Fallback para não comprimido
                    pass

            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def save(self, record: ExecutionRecord) -> None:
        """Salva um registro de execução."""
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO executions (
                        id, timestamp, plan_file, plan_hash, plan_name,
                        status, duration_ms, total_steps, passed_steps,
                        failed_steps, runner_version, runner_report,
                        tags, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.timestamp,
                        record.plan_file,
                        record.plan_hash,
                        record.plan_name,
                        record.status,
                        record.duration_ms,
                        record.total_steps,
                        record.passed_steps,
                        record.failed_steps,
                        record.runner_version,
                        self._serialize_report(record.runner_report),
                        json.dumps(record.tags),
                        json.dumps(record.metadata),
                    ),
                )
        except sqlite3.Error as e:
            raise StorageError(f"Failed to save record: {e}") from e

    def get(self, record_id: str) -> ExecutionRecord:
        """Obtém um registro por ID."""
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    "SELECT * FROM executions WHERE id = ?",
                    (record_id,),
                )
                row = cursor.fetchone()

                if row is None:
                    raise StorageNotFoundError(f"Record not found: {record_id}")

                return self._row_to_record(row, include_report=True)
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get record: {e}") from e

    def _row_to_record(
        self, row: sqlite3.Row, include_report: bool = False
    ) -> ExecutionRecord:
        """Converte uma row do SQLite para ExecutionRecord."""
        return ExecutionRecord(
            id=row["id"],
            timestamp=row["timestamp"],
            plan_file=row["plan_file"],
            plan_hash=row["plan_hash"],
            plan_name=row["plan_name"],
            status=row["status"],
            duration_ms=row["duration_ms"],
            total_steps=row["total_steps"],
            passed_steps=row["passed_steps"],
            failed_steps=row["failed_steps"],
            runner_version=row["runner_version"],
            runner_report=(
                self._deserialize_report(row["runner_report"])
                if include_report
                else None
            ),
            tags=json.loads(row["tags"]) if row["tags"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

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
        try:
            query = """
                SELECT id, timestamp, plan_file, plan_hash, plan_name,
                       status, duration_ms, total_steps, passed_steps,
                       failed_steps, runner_version, tags, metadata
                FROM executions
                WHERE 1=1
            """
            params: list[Any] = []

            if status is not None:
                query += " AND status = ?"
                params.append(status)

            if start_date is not None:
                query += " AND timestamp >= ?"
                params.append(start_date)

            if end_date is not None:
                query += " AND timestamp <= ?"
                params.append(end_date)

            # Tags filter (AND logic)
            if tags:
                for tag in tags:
                    query += " AND tags LIKE ?"
                    params.append(f'%"{tag}"%')

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            with self._transaction() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_record(row, include_report=False) for row in rows]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to list records: {e}") from e

    def delete(self, record_id: str) -> bool:
        """Remove um registro."""
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    "DELETE FROM executions WHERE id = ?",
                    (record_id,),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete record: {e}") from e

    def stats(self) -> StorageStats:
        """Retorna estatísticas do storage."""
        try:
            with self._transaction() as cursor:
                # Contagens
                cursor.execute("SELECT COUNT(*) as total FROM executions")
                total = cursor.fetchone()["total"]

                cursor.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM executions
                    GROUP BY status
                    """
                )
                status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

                # Datas extremas
                cursor.execute(
                    """
                    SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
                    FROM executions
                    """
                )
                dates = cursor.fetchone()

                # Tamanho do arquivo
                size_bytes = None
                if str(self.db_path) != ":memory:" and self.db_path.exists():
                    size_bytes = self.db_path.stat().st_size

                return StorageStats(
                    backend="sqlite",
                    total_records=total,
                    success_count=status_counts.get("success", 0),
                    failure_count=status_counts.get("failure", 0),
                    error_count=status_counts.get("error", 0),
                    storage_size_bytes=size_bytes,
                    oldest_record=dates["oldest"],
                    newest_record=dates["newest"],
                )
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get stats: {e}") from e

    def close(self) -> None:
        """Fecha conexões."""
        self._closed = True
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            conn.close()
            self._local.connection = None

    def clear(self) -> int:
        """Remove todos os registros."""
        try:
            with self._transaction() as cursor:
                cursor.execute("SELECT COUNT(*) FROM executions")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM executions")
                return count
        except sqlite3.Error as e:
            raise StorageError(f"Failed to clear records: {e}") from e

    def vacuum(self) -> None:
        """Compacta o banco de dados."""
        try:
            conn = self._get_connection()
            conn.execute("VACUUM")
        except sqlite3.Error as e:
            raise StorageError(f"Failed to vacuum: {e}") from e

    def __enter__(self) -> "SQLiteStorage":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def search(
        self,
        query: str,
        limit: int = 50,
    ) -> list[ExecutionRecord]:
        """
        Busca registros por texto em plan_file ou plan_name.

        ## Parâmetros:

        - `query`: Texto a buscar
        - `limit`: Máximo de resultados

        ## Retorno:

        Lista de registros que correspondem à busca.
        """
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    """
                    SELECT id, timestamp, plan_file, plan_hash, plan_name,
                           status, duration_ms, total_steps, passed_steps,
                           failed_steps, runner_version, tags, metadata
                    FROM executions
                    WHERE plan_file LIKE ? OR plan_name LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                rows = cursor.fetchall()
                return [self._row_to_record(row, include_report=False) for row in rows]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to search records: {e}") from e

    def get_by_plan_hash(self, plan_hash: str) -> list[ExecutionRecord]:
        """
        Obtém todas as execuções de um plano pelo hash.

        Útil para análise de tendências do mesmo plano.

        ## Parâmetros:

        - `plan_hash`: Hash do plano

        ## Retorno:

        Lista de execuções ordenadas por timestamp DESC.
        """
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    """
                    SELECT id, timestamp, plan_file, plan_hash, plan_name,
                           status, duration_ms, total_steps, passed_steps,
                           failed_steps, runner_version, tags, metadata
                    FROM executions
                    WHERE plan_hash = ?
                    ORDER BY timestamp DESC
                    """,
                    (plan_hash,),
                )
                rows = cursor.fetchall()
                return [self._row_to_record(row, include_report=False) for row in rows]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get by plan hash: {e}") from e

    def get_latest(self) -> ExecutionRecord | None:
        """
        Obtém a execução mais recente.

        ## Retorno:

        ExecutionRecord mais recente ou None se vazio.
        """
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM executions
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_record(row, include_report=True)
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get latest: {e}") from e
