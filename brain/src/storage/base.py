"""
================================================================================
STORAGE BASE - Abstract Protocol and Data Types
================================================================================

Define a interface comum para todos os backends de armazenamento.
"""

from __future__ import annotations

import uuid
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, runtime_checkable


# =============================================================================
# Exceptions
# =============================================================================


class StorageError(Exception):
    """Erro base para operações de storage."""

    pass


class StorageNotFoundError(StorageError):
    """Registro não encontrado no storage."""

    pass


class StorageConnectionError(StorageError):
    """Erro de conexão com o backend de storage."""

    pass


# =============================================================================
# Data Types
# =============================================================================


@dataclass
class ExecutionRecord:
    """
    Registro de uma execução de plano de teste.

    ## Atributos obrigatórios:

    - `id`: Identificador único (UUID)
    - `timestamp`: Data/hora ISO 8601
    - `plan_file`: Caminho do arquivo de plano
    - `status`: success | failure | error
    - `duration_ms`: Duração em milissegundos
    - `total_steps`: Total de steps no plano
    - `passed_steps`: Steps que passaram
    - `failed_steps`: Steps que falharam

    ## Atributos opcionais:

    - `plan_hash`: Hash do plano (para cache)
    - `plan_name`: Nome legível do plano
    - `runner_version`: Versão do runner
    - `runner_report`: Relatório completo (JSON)
    - `tags`: Tags para categorização
    - `metadata`: Metadados adicionais
    """

    id: str
    timestamp: str
    plan_file: str
    status: Literal["success", "failure", "error"]
    duration_ms: int
    total_steps: int
    passed_steps: int
    failed_steps: int
    plan_hash: str | None = None
    plan_name: str | None = None
    runner_version: str | None = None
    runner_report: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=lambda: [])
    metadata: dict[str, Any] = field(default_factory=lambda: {})

    @classmethod
    def create(
        cls,
        plan_file: str,
        status: Literal["success", "failure", "error"],
        duration_ms: int,
        total_steps: int,
        passed_steps: int,
        failed_steps: int,
        **kwargs: Any,
    ) -> "ExecutionRecord":
        """
        Cria um novo registro com ID e timestamp automáticos.

        ## Parâmetros:

        - `plan_file`: Caminho do arquivo de plano
        - `status`: Status da execução
        - `duration_ms`: Duração em ms
        - `total_steps`: Total de steps
        - `passed_steps`: Steps que passaram
        - `failed_steps`: Steps que falharam
        - `**kwargs`: Campos opcionais

        ## Retorno:

        ExecutionRecord com ID e timestamp preenchidos.

        ## Exemplo:

            >>> record = ExecutionRecord.create(
            ...     plan_file="test_plan.json",
            ...     status="success",
            ...     duration_ms=1500,
            ...     total_steps=5,
            ...     passed_steps=5,
            ...     failed_steps=0,
            ... )
        """
        record_id = kwargs.pop("id", None) or uuid.uuid4().hex[:12]
        timestamp = kwargs.pop("timestamp", None) or datetime.now(
            timezone.utc
        ).isoformat().replace("+00:00", "Z")

        return cls(
            id=record_id,
            timestamp=timestamp,
            plan_file=plan_file,
            status=status,
            duration_ms=duration_ms,
            total_steps=total_steps,
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "plan_file": self.plan_file,
            "plan_hash": self.plan_hash,
            "plan_name": self.plan_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "runner_version": self.runner_version,
            "runner_report": self.runner_report,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionRecord":
        """Cria instância a partir de dicionário."""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            plan_file=data["plan_file"],
            status=data["status"],
            duration_ms=data["duration_ms"],
            total_steps=data["total_steps"],
            passed_steps=data["passed_steps"],
            failed_steps=data["failed_steps"],
            plan_hash=data.get("plan_hash"),
            plan_name=data.get("plan_name"),
            runner_version=data.get("runner_version"),
            runner_report=data.get("runner_report"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    def summary_dict(self) -> dict[str, Any]:
        """
        Retorna apenas metadados (sem runner_report).

        Útil para listagens e índices.
        """
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "plan_file": self.plan_file,
            "plan_hash": self.plan_hash,
            "plan_name": self.plan_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "tags": self.tags,
        }


@dataclass
class StorageStats:
    """
    Estatísticas do storage.

    ## Atributos:

    - `backend`: Nome do backend (sqlite, s3, json)
    - `total_records`: Total de registros
    - `success_count`: Execuções bem-sucedidas
    - `failure_count`: Execuções com falhas
    - `error_count`: Execuções com erros
    - `storage_size_bytes`: Tamanho em bytes (quando disponível)
    - `oldest_record`: Data do registro mais antigo
    - `newest_record`: Data do registro mais recente
    """

    backend: str
    total_records: int
    success_count: int = 0
    failure_count: int = 0
    error_count: int = 0
    storage_size_bytes: int | None = None
    oldest_record: str | None = None
    newest_record: str | None = None


# =============================================================================
# Protocol Definition
# =============================================================================


@runtime_checkable
class StorageBackend(Protocol):
    """
    Protocolo para backends de armazenamento.

    Todos os backends devem implementar estes métodos para
    garantir compatibilidade com o sistema de histórico.

    ## Operações principais:

    - `save`: Salvar registro
    - `get`: Obter registro por ID
    - `list`: Listar registros com filtros
    - `delete`: Remover registro
    - `stats`: Estatísticas do storage

    ## Thread Safety:

    Implementações DEVEM ser thread-safe para operações
    concorrentes.

    ## Exemplo de implementação:

    ```python
    class MyStorage:
        def save(self, record: ExecutionRecord) -> None:
            ...

        def get(self, record_id: str) -> ExecutionRecord:
            ...

        def list(
            self,
            limit: int = 100,
            offset: int = 0,
            status: str | None = None,
            start_date: str | None = None,
            end_date: str | None = None,
            tags: list[str] | None = None,
        ) -> list[ExecutionRecord]:
            ...

        def delete(self, record_id: str) -> bool:
            ...

        def stats(self) -> StorageStats:
            ...

        def close(self) -> None:
            ...
    ```
    """

    @abstractmethod
    def save(self, record: ExecutionRecord) -> None:
        """
        Salva um registro de execução.

        ## Parâmetros:

        - `record`: ExecutionRecord a salvar

        ## Raises:

        - `StorageError`: Em caso de erro ao salvar
        """
        ...

    @abstractmethod
    def get(self, record_id: str) -> ExecutionRecord:
        """
        Obtém um registro por ID.

        ## Parâmetros:

        - `record_id`: ID do registro

        ## Retorno:

        ExecutionRecord completo (com runner_report).

        ## Raises:

        - `StorageNotFoundError`: Se registro não existe
        - `StorageError`: Em caso de erro ao ler
        """
        ...

    @abstractmethod
    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Literal["success", "failure", "error"] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        tags: list[str] | None = None,
    ) -> list[ExecutionRecord]:
        """
        Lista registros com filtros opcionais.

        ## Parâmetros:

        - `limit`: Número máximo de registros (default: 100)
        - `offset`: Offset para paginação (default: 0)
        - `status`: Filtrar por status
        - `start_date`: Data inicial (ISO 8601)
        - `end_date`: Data final (ISO 8601)
        - `tags`: Filtrar por tags (AND)

        ## Retorno:

        Lista de ExecutionRecord (sem runner_report para economia).

        ## Ordenação:

        Resultados são ordenados por timestamp DESC (mais recentes primeiro).
        """
        ...

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        """
        Remove um registro.

        ## Parâmetros:

        - `record_id`: ID do registro a remover

        ## Retorno:

        True se removido, False se não existia.
        """
        ...

    @abstractmethod
    def stats(self) -> StorageStats:
        """
        Retorna estatísticas do storage.

        ## Retorno:

        StorageStats com contagens e metadados.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """
        Fecha conexões e libera recursos.

        Deve ser chamado ao finalizar uso do storage.
        """
        ...

    def clear(self) -> int:
        """
        Remove todos os registros.

        ## Retorno:

        Número de registros removidos.

        ## Nota:

        Implementação opcional. Por padrão, levanta NotImplementedError.
        """
        raise NotImplementedError("clear() not supported by this backend")

    def vacuum(self) -> None:
        """
        Otimiza o storage (compacta, remove lixo, etc).

        ## Nota:

        Implementação opcional. Por padrão, não faz nada.
        """
        pass
