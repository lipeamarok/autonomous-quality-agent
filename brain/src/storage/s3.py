"""
================================================================================
S3 Storage Backend
================================================================================

Backend de armazenamento usando Amazon S3 para persistência em cloud.
Ideal para ambientes distribuídos e compartilhamento entre equipes.

## Vantagens:

1. **Escalável**: Sem limites práticos de armazenamento
2. **Durável**: 11 noves de durabilidade
3. **Distribuído**: Acesso de qualquer lugar
4. **Compartilhável**: Time inteiro pode acessar histórico

## Estrutura no S3:

```
s3://bucket/prefix/
├── index.json           # Índice de todos os registros
├── 2024/
│   ├── 01/
│   │   ├── 15/
│   │   │   ├── abc123.json.gz
│   │   │   └── def456.json.gz
│   │   └── 16/
│   │       └── ...
```

## Configuração:

```python
from src.storage import S3Storage

storage = S3Storage(
    bucket="my-aqa-bucket",
    prefix="history/",
    region="us-east-1",
)

# Ou via variáveis de ambiente:
# AQA_S3_BUCKET=my-bucket
# AQA_S3_PREFIX=history/
# AQA_S3_REGION=us-east-1
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
```

## Dependência:

Requer `boto3` instalado:
```bash
pip install boto3
```
"""

from __future__ import annotations

import gzip
import json
import os
import threading
from datetime import datetime
from typing import Any, Literal

from .base import (
    ExecutionRecord,
    StorageBackend,
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
    StorageStats,
)


def _get_boto3_client(region: str) -> Any:
    """Create boto3 S3 client with lazy import."""
    try:
        import boto3  # type: ignore[import-not-found]

        return boto3.client("s3", region_name=region)  # type: ignore[no-any-return]
    except ImportError as e:
        raise ImportError(
            "boto3 is required for S3 storage. "
            "Install it with: pip install boto3"
        ) from e


class S3Storage(StorageBackend):
    """
    Backend S3 para armazenamento de histórico em cloud.

    Thread-safe através de locks e índice em memória.
    Usa compressão gzip para economia de transferência e storage.

    ## Parâmetros:

    - `bucket`: Nome do bucket S3
    - `prefix`: Prefixo para objetos (default: "aqa/history/")
    - `region`: Região AWS (default: us-east-1)
    - `compress`: Se True, comprime objetos com gzip

    ## Credenciais:

    Usa chain padrão da AWS:
    1. Variáveis de ambiente (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    2. ~/.aws/credentials
    3. IAM role (EC2, ECS, Lambda)

    ## Exemplo:

        >>> storage = S3Storage(bucket="my-bucket")
        >>> storage.save(record)
        >>> recent = storage.list(limit=10)
        >>> storage.close()
    """

    INDEX_KEY = "index.json"

    def __init__(
        self,
        bucket: str | None = None,
        prefix: str = "aqa/history/",
        region: str = "us-east-1",
        compress: bool = True,
    ) -> None:
        """Inicializa o storage S3."""
        self.bucket = bucket or os.environ.get("AQA_S3_BUCKET")
        if not self.bucket:
            raise ValueError(
                "S3 bucket is required. "
                "Set AQA_S3_BUCKET environment variable or pass bucket parameter."
            )

        self.prefix = os.environ.get("AQA_S3_PREFIX", prefix).rstrip("/") + "/"
        self.region = os.environ.get("AQA_S3_REGION", region)
        self.compress = compress

        self._lock = threading.Lock()
        self._index: list[dict[str, Any]] = []
        self._index_loaded = False
        self._client: Any = None

    def _get_client(self) -> Any:
        """Obtém cliente S3 (lazy initialization)."""
        if self._client is None:
            try:
                self._client = _get_boto3_client(self.region)
                # Testa conexão
                self._client.head_bucket(Bucket=self.bucket)
            except ImportError:
                raise
            except Exception as e:
                raise StorageConnectionError(
                    f"Failed to connect to S3 bucket '{self.bucket}': {e}"
                ) from e
        return self._client

    def _load_index(self) -> None:
        """Carrega índice do S3."""
        if self._index_loaded:
            return

        with self._lock:
            if self._index_loaded:
                return

            client = self._get_client()
            key = f"{self.prefix}{self.INDEX_KEY}"

            try:
                response = client.get_object(Bucket=self.bucket, Key=key)
                data: str = response["Body"].read().decode("utf-8")
                self._index = json.loads(data)
                self._index_loaded = True
            except client.exceptions.NoSuchKey:
                self._index = []
                self._index_loaded = True
            except Exception as e:
                raise StorageError(f"Failed to load index: {e}") from e

    def _save_index(self) -> None:
        """Salva índice no S3."""
        try:
            client = self._get_client()
            key = f"{self.prefix}{self.INDEX_KEY}"

            data = json.dumps(self._index, indent=2, ensure_ascii=False)
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data.encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:
            raise StorageError(f"Failed to save index: {e}") from e

    def _make_key(self, record: ExecutionRecord) -> str:
        """Gera key S3 para um registro baseado na data."""
        # Parse timestamp para criar estrutura de diretórios
        try:
            dt = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
            date_path = dt.strftime("%Y/%m/%d")
        except ValueError:
            date_path = "unknown"

        ext = ".json.gz" if self.compress else ".json"
        return f"{self.prefix}{date_path}/{record.id}{ext}"

    def _serialize_record(self, record: ExecutionRecord) -> bytes:
        """Serializa registro para bytes."""
        data = json.dumps(record.to_dict(), ensure_ascii=False).encode("utf-8")
        if self.compress:
            return gzip.compress(data)
        return data

    def _deserialize_record(self, data: bytes) -> ExecutionRecord:
        """Deserializa bytes para registro."""
        try:
            if self.compress:
                data = gzip.decompress(data)
            record_dict = json.loads(data.decode("utf-8"))
            return ExecutionRecord.from_dict(record_dict)
        except (gzip.BadGzipFile, json.JSONDecodeError, UnicodeDecodeError) as e:
            raise StorageError(f"Failed to deserialize record: {e}") from e

    def save(self, record: ExecutionRecord) -> None:
        """Salva um registro de execução."""
        self._load_index()

        try:
            client = self._get_client()
            key = self._make_key(record)

            # Salva o objeto
            content_type = (
                "application/gzip" if self.compress else "application/json"
            )
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=self._serialize_record(record),
                ContentType=content_type,
            )

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
                    "key": key,
                }

                # Remove entrada antiga se existir
                self._index = [e for e in self._index if e.get("id") != record.id]
                self._index.insert(0, index_entry)
                self._save_index()

        except Exception as e:
            raise StorageError(f"Failed to save record: {e}") from e

    def get(self, record_id: str) -> ExecutionRecord:
        """Obtém um registro por ID."""
        self._load_index()

        with self._lock:
            entry = next(
                (e for e in self._index if e.get("id") == record_id), None
            )

        if entry is None:
            raise StorageNotFoundError(f"Record not found: {record_id}")

        try:
            client = self._get_client()
            response = client.get_object(Bucket=self.bucket, Key=entry["key"])
            data: bytes = response["Body"].read()
            return self._deserialize_record(data)
        except Exception as e:
            # Check if it's a NoSuchKey error
            if "NoSuchKey" in str(e) or "NoSuchKey" in str(type(e).__name__):
                raise StorageNotFoundError(f"Record not found: {record_id}") from e
            raise StorageError(f"Failed to get record: {e}") from e

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
        self._load_index()

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
        self._load_index()

        with self._lock:
            entry = next(
                (e for e in self._index if e.get("id") == record_id), None
            )

            if entry is None:
                return False

            try:
                client = self._get_client()
                client.delete_object(Bucket=self.bucket, Key=entry["key"])

                self._index = [e for e in self._index if e.get("id") != record_id]
                self._save_index()
                return True
            except Exception as e:
                raise StorageError(f"Failed to delete record: {e}") from e

    def stats(self) -> StorageStats:
        """Retorna estatísticas do storage."""
        self._load_index()

        with self._lock:
            total = len(self._index)
            success = sum(1 for e in self._index if e.get("status") == "success")
            failure = sum(1 for e in self._index if e.get("status") == "failure")
            error = sum(1 for e in self._index if e.get("status") == "error")

            oldest = self._index[-1]["timestamp"] if self._index else None
            newest = self._index[0]["timestamp"] if self._index else None

        return StorageStats(
            backend="s3",
            total_records=total,
            success_count=success,
            failure_count=failure,
            error_count=error,
            oldest_record=oldest,
            newest_record=newest,
        )

    def close(self) -> None:
        """Fecha conexões (noop para S3)."""
        self._client = None

    def clear(self) -> int:
        """Remove todos os registros."""
        self._load_index()

        with self._lock:
            count = len(self._index)
            if count == 0:
                return 0

            try:
                client = self._get_client()

                # Deleta objetos em batch
                objects = [{"Key": e["key"]} for e in self._index]
                client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": objects, "Quiet": True},
                )

                # Limpa índice
                self._index = []
                self._save_index()
                return count
            except Exception as e:
                raise StorageError(f"Failed to clear records: {e}") from e

    def __enter__(self) -> "S3Storage":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def sync_index(self) -> int:
        """
        Reconstrói o índice escaneando o bucket.

        Útil para recuperar de índice corrompido ou sincronizar
        após alterações diretas no S3.

        ## Retorno:

        Número de registros encontrados.
        """
        try:
            client = self._get_client()
            paginator = client.get_paginator("list_objects_v2")

            new_index: list[dict[str, Any]] = []

            for page in paginator.paginate(
                Bucket=self.bucket, Prefix=self.prefix
            ):
                for obj in page.get("Contents", []):
                    key: str = obj["Key"]

                    # Ignora o próprio índice
                    if key.endswith("index.json"):
                        continue

                    # Ignora objetos que não são registros
                    if not (key.endswith(".json") or key.endswith(".json.gz")):
                        continue

                    try:
                        response = client.get_object(Bucket=self.bucket, Key=key)
                        data: bytes = response["Body"].read()
                        record = self._deserialize_record(data)

                        new_index.append({
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
                            "key": key,
                        })
                    except Exception:
                        # Ignora objetos inválidos
                        pass

            # Ordena por timestamp desc
            new_index.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

            with self._lock:
                self._index = new_index
                self._save_index()

            return len(new_index)

        except Exception as e:
            raise StorageError(f"Failed to sync index: {e}") from e
