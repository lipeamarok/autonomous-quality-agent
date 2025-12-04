"""
================================================================================
Storage Module Tests
================================================================================

Testes para os backends de armazenamento (SQLite, S3, JSON).
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from src.storage.base import ExecutionRecord, StorageNotFoundError
from src.storage.sqlite import SQLiteStorage
from src.storage.json_backend import JsonStorage
from src.storage.factory import create_storage, get_default_storage


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_record() -> ExecutionRecord:
    """Cria um registro de execução para testes."""
    return ExecutionRecord.create(
        plan_file="test_plan.json",
        status="success",
        duration_ms=1500,
        total_steps=5,
        passed_steps=5,
        failed_steps=0,
        plan_hash="abc123",
        plan_name="Test Plan",
        runner_version="1.0.0",
        tags=["smoke", "api"],
        metadata={"env": "test"},
        runner_report={
            "execution_id": "test-123",
            "status": "passed",
            "steps": [{"id": "step1", "status": "passed"}],
        },
    )


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Cria diretório temporário para testes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sqlite_storage(temp_dir: str) -> Generator[SQLiteStorage, None, None]:
    """Cria SQLiteStorage em memória."""
    db_path = os.path.join(temp_dir, "test.db")
    storage = SQLiteStorage(db_path=db_path, compress_reports=True)
    yield storage
    storage.close()


@pytest.fixture
def json_storage(temp_dir: str) -> Generator[JsonStorage, None, None]:
    """Cria JsonStorage em diretório temporário."""
    storage = JsonStorage(history_dir=temp_dir, compress=False)
    yield storage
    storage.close()


# =============================================================================
# ExecutionRecord Tests
# =============================================================================


class TestExecutionRecord:
    """Testes para ExecutionRecord."""

    def test_create_generates_id_and_timestamp(self) -> None:
        """create() deve gerar id e timestamp automaticamente."""
        record = ExecutionRecord.create(
            plan_file="test.json",
            status="success",
            duration_ms=100,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
        )

        assert record.id is not None
        assert len(record.id) == 12
        assert record.timestamp is not None
        assert record.timestamp.endswith("Z")

    def test_create_with_explicit_id(self) -> None:
        """create() deve aceitar id explícito."""
        record = ExecutionRecord.create(
            id="custom-id",
            plan_file="test.json",
            status="failure",
            duration_ms=200,
            total_steps=2,
            passed_steps=1,
            failed_steps=1,
        )

        assert record.id == "custom-id"

    def test_to_dict_and_from_dict(self, sample_record: ExecutionRecord) -> None:
        """to_dict e from_dict devem ser inversos."""
        data = sample_record.to_dict()
        restored = ExecutionRecord.from_dict(data)

        assert restored.id == sample_record.id
        assert restored.timestamp == sample_record.timestamp
        assert restored.plan_file == sample_record.plan_file
        assert restored.status == sample_record.status
        assert restored.tags == sample_record.tags
        assert restored.runner_report == sample_record.runner_report

    def test_summary_dict_excludes_runner_report(
        self, sample_record: ExecutionRecord
    ) -> None:
        """summary_dict não deve incluir runner_report."""
        summary = sample_record.summary_dict()

        assert "runner_report" not in summary
        assert summary["id"] == sample_record.id
        assert summary["status"] == sample_record.status


# =============================================================================
# SQLiteStorage Tests
# =============================================================================


class TestSQLiteStorage:
    """Testes para SQLiteStorage."""

    def test_save_and_get(
        self, sqlite_storage: SQLiteStorage, sample_record: ExecutionRecord
    ) -> None:
        """Deve salvar e recuperar registro."""
        sqlite_storage.save(sample_record)
        retrieved = sqlite_storage.get(sample_record.id)

        assert retrieved.id == sample_record.id
        assert retrieved.plan_file == sample_record.plan_file
        assert retrieved.status == sample_record.status
        assert retrieved.runner_report == sample_record.runner_report

    def test_get_not_found_raises(self, sqlite_storage: SQLiteStorage) -> None:
        """get() deve lançar StorageNotFoundError para id inexistente."""
        with pytest.raises(StorageNotFoundError):
            sqlite_storage.get("nonexistent-id")

    def test_list_returns_records(
        self, sqlite_storage: SQLiteStorage, sample_record: ExecutionRecord
    ) -> None:
        """list() deve retornar registros salvos."""
        sqlite_storage.save(sample_record)
        records = sqlite_storage.list(limit=10)

        assert len(records) == 1
        assert records[0].id == sample_record.id
        # list() não inclui runner_report
        assert records[0].runner_report is None

    def test_list_with_status_filter(self, sqlite_storage: SQLiteStorage) -> None:
        """list() deve filtrar por status."""
        record1 = ExecutionRecord.create(
            id="rec1",
            plan_file="test.json",
            status="success",
            duration_ms=100,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
        )
        record2 = ExecutionRecord.create(
            id="rec2",
            plan_file="test.json",
            status="failure",
            duration_ms=100,
            total_steps=1,
            passed_steps=0,
            failed_steps=1,
        )

        sqlite_storage.save(record1)
        sqlite_storage.save(record2)

        success_only = sqlite_storage.list(status="success")
        assert len(success_only) == 1
        assert success_only[0].id == "rec1"

        failure_only = sqlite_storage.list(status="failure")
        assert len(failure_only) == 1
        assert failure_only[0].id == "rec2"

    def test_list_with_pagination(self, sqlite_storage: SQLiteStorage) -> None:
        """list() deve suportar paginação."""
        for i in range(5):
            record = ExecutionRecord.create(
                id=f"rec{i}",
                plan_file="test.json",
                status="success",
                duration_ms=100,
                total_steps=1,
                passed_steps=1,
                failed_steps=0,
            )
            sqlite_storage.save(record)

        page1 = sqlite_storage.list(limit=2, offset=0)
        page2 = sqlite_storage.list(limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    def test_list_with_tags_filter(self, sqlite_storage: SQLiteStorage) -> None:
        """list() deve filtrar por tags."""
        record1 = ExecutionRecord.create(
            id="rec1",
            plan_file="test.json",
            status="success",
            duration_ms=100,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
            tags=["smoke", "api"],
        )
        record2 = ExecutionRecord.create(
            id="rec2",
            plan_file="test.json",
            status="success",
            duration_ms=100,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
            tags=["regression"],
        )

        sqlite_storage.save(record1)
        sqlite_storage.save(record2)

        with_smoke = sqlite_storage.list(tags=["smoke"])
        assert len(with_smoke) == 1
        assert with_smoke[0].id == "rec1"

    def test_delete_removes_record(
        self, sqlite_storage: SQLiteStorage, sample_record: ExecutionRecord
    ) -> None:
        """delete() deve remover registro."""
        sqlite_storage.save(sample_record)
        assert sqlite_storage.delete(sample_record.id) is True

        with pytest.raises(StorageNotFoundError):
            sqlite_storage.get(sample_record.id)

    def test_delete_nonexistent_returns_false(
        self, sqlite_storage: SQLiteStorage
    ) -> None:
        """delete() deve retornar False para id inexistente."""
        assert sqlite_storage.delete("nonexistent") is False

    def test_stats_returns_counts(self, sqlite_storage: SQLiteStorage) -> None:
        """stats() deve retornar contagens corretas."""
        for status in ["success", "success", "failure", "error"]:
            record = ExecutionRecord.create(
                plan_file="test.json",
                status=status,  # type: ignore[arg-type]
                duration_ms=100,
                total_steps=1,
                passed_steps=1 if status == "success" else 0,
                failed_steps=0 if status == "success" else 1,
            )
            sqlite_storage.save(record)

        stats = sqlite_storage.stats()

        assert stats.backend == "sqlite"
        assert stats.total_records == 4
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert stats.error_count == 1

    def test_clear_removes_all(
        self, sqlite_storage: SQLiteStorage, sample_record: ExecutionRecord
    ) -> None:
        """clear() deve remover todos os registros."""
        sqlite_storage.save(sample_record)
        count = sqlite_storage.clear()

        assert count == 1
        assert sqlite_storage.list() == []

    def test_search_by_plan_file(self, sqlite_storage: SQLiteStorage) -> None:
        """search() deve buscar por plan_file."""
        record1 = ExecutionRecord.create(
            id="rec1",
            plan_file="api/users.json",
            status="success",
            duration_ms=100,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
        )
        record2 = ExecutionRecord.create(
            id="rec2",
            plan_file="api/orders.json",
            status="success",
            duration_ms=100,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
        )

        sqlite_storage.save(record1)
        sqlite_storage.save(record2)

        results = sqlite_storage.search("users")
        assert len(results) == 1
        assert results[0].id == "rec1"

    def test_get_by_plan_hash(self, sqlite_storage: SQLiteStorage) -> None:
        """get_by_plan_hash() deve retornar execuções do mesmo plano."""
        for i in range(3):
            record = ExecutionRecord.create(
                id=f"rec{i}",
                plan_file="test.json",
                plan_hash="hash123",
                status="success",
                duration_ms=100,
                total_steps=1,
                passed_steps=1,
                failed_steps=0,
            )
            sqlite_storage.save(record)

        results = sqlite_storage.get_by_plan_hash("hash123")
        assert len(results) == 3

    def test_get_latest(
        self, sqlite_storage: SQLiteStorage, sample_record: ExecutionRecord
    ) -> None:
        """get_latest() deve retornar registro mais recente."""
        sqlite_storage.save(sample_record)
        latest = sqlite_storage.get_latest()

        assert latest is not None
        assert latest.id == sample_record.id

    def test_get_latest_empty(self, sqlite_storage: SQLiteStorage) -> None:
        """get_latest() deve retornar None se vazio."""
        assert sqlite_storage.get_latest() is None

    def test_compression_works(
        self, temp_dir: str, sample_record: ExecutionRecord
    ) -> None:
        """Compressão deve funcionar transparentemente."""
        db_path = os.path.join(temp_dir, "compressed.db")
        storage = SQLiteStorage(db_path=db_path, compress_reports=True)

        try:
            storage.save(sample_record)
            retrieved = storage.get(sample_record.id)

            assert retrieved.runner_report == sample_record.runner_report
        finally:
            storage.close()

    def test_context_manager(self, temp_dir: str) -> None:
        """Deve funcionar como context manager."""
        db_path = os.path.join(temp_dir, "ctx.db")

        with SQLiteStorage(db_path=db_path) as storage:
            record = ExecutionRecord.create(
                plan_file="test.json",
                status="success",
                duration_ms=100,
                total_steps=1,
                passed_steps=1,
                failed_steps=0,
            )
            storage.save(record)

        # Conexão deve estar fechada
        # Re-abrir deve funcionar
        with SQLiteStorage(db_path=db_path) as storage:
            assert len(storage.list()) == 1


# =============================================================================
# JsonStorage Tests
# =============================================================================


class TestJsonStorage:
    """Testes para JsonStorage."""

    def test_save_and_get(
        self, json_storage: JsonStorage, sample_record: ExecutionRecord
    ) -> None:
        """Deve salvar e recuperar registro."""
        json_storage.save(sample_record)
        retrieved = json_storage.get(sample_record.id)

        assert retrieved.id == sample_record.id
        assert retrieved.status == sample_record.status

    def test_creates_date_directories(
        self, json_storage: JsonStorage, sample_record: ExecutionRecord
    ) -> None:
        """Deve criar subdiretórios por data."""
        from pathlib import Path

        json_storage.save(sample_record)

        # Verifica que o arquivo foi criado em subdiretório de data
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected_dir = Path(json_storage.history_dir) / today
        assert expected_dir.exists()

    def test_list_returns_records(
        self, json_storage: JsonStorage, sample_record: ExecutionRecord
    ) -> None:
        """list() deve retornar registros salvos."""
        json_storage.save(sample_record)
        records = json_storage.list()

        assert len(records) == 1
        assert records[0].id == sample_record.id

    def test_delete_removes_file(
        self, json_storage: JsonStorage, sample_record: ExecutionRecord
    ) -> None:
        """delete() deve remover arquivo do disco."""
        json_storage.save(sample_record)
        json_storage.delete(sample_record.id)

        with pytest.raises(StorageNotFoundError):
            json_storage.get(sample_record.id)

    def test_max_records_limit(self, temp_dir: str) -> None:
        """Deve respeitar max_records."""
        storage = JsonStorage(history_dir=temp_dir, max_records=3)

        for i in range(5):
            record = ExecutionRecord.create(
                id=f"rec{i}",
                plan_file="test.json",
                status="success",
                duration_ms=100,
                total_steps=1,
                passed_steps=1,
                failed_steps=0,
            )
            storage.save(record)

        assert len(storage.list()) == 3


# =============================================================================
# Factory Tests
# =============================================================================


class TestFactory:
    """Testes para factory functions."""

    def test_create_storage_sqlite(self, temp_dir: str) -> None:
        """create_storage deve criar SQLiteStorage."""
        db_path = os.path.join(temp_dir, "test.db")
        storage = create_storage("sqlite", db_path=db_path)

        assert isinstance(storage, SQLiteStorage)
        storage.close()

    def test_create_storage_json(self, temp_dir: str) -> None:
        """create_storage deve criar JsonStorage."""
        storage = create_storage("json", history_dir=temp_dir)

        assert isinstance(storage, JsonStorage)
        storage.close()

    def test_create_storage_invalid(self) -> None:
        """create_storage deve lançar erro para backend inválido."""
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_storage("invalid")  # type: ignore[arg-type]

    def test_get_default_storage(self, temp_dir: str, monkeypatch: Any) -> None:
        """get_default_storage deve retornar SQLite por padrão."""
        db_path = os.path.join(temp_dir, "default.db")
        monkeypatch.setenv("AQA_STORAGE_PATH", db_path)
        monkeypatch.delenv("AQA_S3_BUCKET", raising=False)
        monkeypatch.delenv("AQA_STORAGE_BACKEND", raising=False)

        storage = get_default_storage()
        assert isinstance(storage, SQLiteStorage)
        storage.close()

    def test_get_default_storage_from_env(
        self, temp_dir: str, monkeypatch: Any
    ) -> None:
        """get_default_storage deve respeitar AQA_STORAGE_BACKEND."""
        monkeypatch.setenv("AQA_STORAGE_BACKEND", "json")
        monkeypatch.setenv("AQA_STORAGE_PATH", temp_dir)
        monkeypatch.delenv("AQA_S3_BUCKET", raising=False)

        storage = get_default_storage()
        assert isinstance(storage, JsonStorage)
        storage.close()


# =============================================================================
# S3Storage Tests (Mocked)
# =============================================================================


class TestS3StorageMocked:
    """Testes para S3Storage com boto3 mockado."""

    def test_requires_bucket(self) -> None:
        """Deve exigir bucket configurado."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove env vars que poderiam definir bucket
            env_without_bucket = {
                k: v for k, v in os.environ.items() if "S3" not in k
            }
            with patch.dict(os.environ, env_without_bucket, clear=True):
                with pytest.raises(ValueError, match="S3 bucket is required"):
                    from src.storage.s3 import S3Storage

                    S3Storage()

    def test_save_calls_put_object(self, sample_record: ExecutionRecord) -> None:
        """save() deve chamar put_object no S3."""
        with patch("src.storage.s3._get_boto3_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            from src.storage.s3 import S3Storage

            storage = S3Storage(bucket="test-bucket")

            # Mock head_bucket para conexão
            mock_client.head_bucket.return_value = {}

            # Configura exception para NoSuchKey
            mock_no_such_key = type("NoSuchKey", (Exception,), {})
            mock_client.exceptions = MagicMock()
            mock_client.exceptions.NoSuchKey = mock_no_such_key
            mock_client.get_object.side_effect = mock_no_such_key()

            storage.save(sample_record)

            # Verifica que put_object foi chamado
            assert mock_client.put_object.called


# =============================================================================
# Integration Tests
# =============================================================================


class TestStorageIntegration:
    """Testes de integração entre componentes."""

    def test_migrate_json_to_sqlite(self, temp_dir: str) -> None:
        """Deve migrar registros de JSON para SQLite."""
        json_dir = os.path.join(temp_dir, "json")
        sqlite_path = os.path.join(temp_dir, "migrated.db")

        # Cria registros no JSON
        json_storage = JsonStorage(history_dir=json_dir)
        for i in range(3):
            record = ExecutionRecord.create(
                id=f"rec{i}",
                plan_file="test.json",
                status="success",
                duration_ms=100,
                total_steps=1,
                passed_steps=1,
                failed_steps=0,
            )
            json_storage.save(record)

        # Migra para SQLite
        count = json_storage.migrate_to_sqlite(sqlite_path)
        assert count == 3

        # Verifica migração
        sqlite_storage = SQLiteStorage(db_path=sqlite_path)
        assert len(sqlite_storage.list()) == 3
        sqlite_storage.close()

    def test_storage_protocol_compliance(
        self, sqlite_storage: SQLiteStorage, json_storage: JsonStorage
    ) -> None:
        """Todos os backends devem implementar StorageBackend."""
        from src.storage.base import StorageBackend

        assert isinstance(sqlite_storage, StorageBackend)
        assert isinstance(json_storage, StorageBackend)

        # Verifica métodos obrigatórios
        storages: list[SQLiteStorage | JsonStorage] = [sqlite_storage, json_storage]
        for storage in storages:
            assert hasattr(storage, "save")
            assert hasattr(storage, "get")
            assert hasattr(storage, "list")
            assert hasattr(storage, "delete")
            assert hasattr(storage, "stats")
            assert hasattr(storage, "close")
