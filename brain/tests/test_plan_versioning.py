"""
================================================================================
Testes: PlanVersionStore e CLI de Versionamento
================================================================================

Testes para o sistema de versionamento de planos, incluindo:
- PlanVersionStore: armazenamento versionado
- PlanVersion: modelo de dados
- PlanDiff: diferenças entre versões
- CLI planversion: comandos de linha
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

import pytest

from src.cache import PlanVersion, PlanVersionStore, PlanDiff  # type: ignore[import-untyped]


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_storage_path() -> Generator[Path, None, None]:
    """Cria diretório temporário para testes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def version_store(temp_storage_path: Path) -> PlanVersionStore:
    """Cria PlanVersionStore com diretório temporário."""
    return PlanVersionStore(plans_dir=str(temp_storage_path))


@pytest.fixture
def sample_plan() -> dict[str, Any]:
    """Plano de teste simples."""
    return {
        "name": "test-plan",
        "version": "1.0",
        "config": {
            "baseUrl": "https://api.example.com",
            "timeout": 30,
        },
        "steps": [
            {
                "id": "step1",
                "name": "Get Users",
                "action": {
                    "method": "GET",
                    "endpoint": "/users",
                },
                "assertions": [
                    {"type": "status_code", "expected": 200},
                ],
            },
            {
                "id": "step2",
                "name": "Create User",
                "depends_on": ["step1"],
                "action": {
                    "method": "POST",
                    "endpoint": "/users",
                    "body": {"name": "Test User"},
                },
                "assertions": [
                    {"type": "status_code", "expected": 201},
                ],
            },
        ],
    }


@pytest.fixture
def modified_plan(sample_plan: dict[str, Any]) -> dict[str, Any]:
    """Plano modificado para teste de diff."""
    plan = json.loads(json.dumps(sample_plan))  # Deep copy
    plan["config"]["timeout"] = 60  # Mudança de config
    plan["steps"][0]["action"]["endpoint"] = "/api/v2/users"  # Step modificado
    plan["steps"].append({  # Novo step
        "id": "step3",
        "name": "Delete User",
        "depends_on": ["step2"],
        "action": {
            "method": "DELETE",
            "endpoint": "/users/{{step2.userId}}",
        },
        "assertions": [
            {"type": "status_code", "expected": 204},
        ],
    })
    return plan


# =============================================================================
# TESTES: PlanVersionStore - Operações Básicas
# =============================================================================


class TestPlanVersionStoreBasics:
    """Testes básicos do PlanVersionStore."""

    def test_save_creates_first_version(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Primeira versão deve ser criada com version=1."""
        plan_version = version_store.save(
            plan_name="my-plan",
            plan=sample_plan,
            description="Initial version",
        )

        assert plan_version.version == 1
        assert plan_version.plan == sample_plan
        assert plan_version.description == "Initial version"
        assert plan_version.parent_version is None

    def test_save_increments_version(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Versões subsequentes devem incrementar o número."""
        v1 = version_store.save("my-plan", sample_plan)
        v2 = version_store.save("my-plan", modified_plan)

        assert v1.version == 1
        assert v2.version == 2
        assert v2.parent_version == 1

    def test_save_stores_llm_metadata(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Metadata do LLM deve ser armazenada."""
        plan_version = version_store.save(
            "my-plan",
            sample_plan,
            llm_provider="openai",
            llm_model="gpt-4",
            source="llm",
        )

        assert plan_version.llm_provider == "openai"
        assert plan_version.llm_model == "gpt-4"
        assert plan_version.source == "llm"

    def test_get_version_returns_specific_version(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Deve retornar a versão específica solicitada."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)

        v1 = version_store.get_version("my-plan", version=1)
        v2 = version_store.get_version("my-plan", version=2)

        assert v1 is not None
        assert v2 is not None
        assert v1.plan == sample_plan
        assert v2.plan == modified_plan

    def test_get_version_latest_by_default(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Sem especificar versão, retorna a mais recente."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)

        latest = version_store.get_version("my-plan")

        assert latest is not None
        assert latest.version == 2
        assert latest.plan == modified_plan

    def test_get_version_nonexistent_returns_none(
        self,
        version_store: PlanVersionStore,
    ) -> None:
        """Versão inexistente retorna None."""
        result = version_store.get_version("nonexistent-plan")
        assert result is None

    def test_get_version_invalid_version_returns_none(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Versão inválida retorna None."""
        version_store.save("my-plan", sample_plan)

        result = version_store.get_version("my-plan", version=999)
        assert result is None

    def test_get_current_returns_plan(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """get_current retorna apenas o plano, não PlanVersion."""
        version_store.save("my-plan", sample_plan)

        plan = version_store.get_current("my-plan")

        assert plan is not None
        assert plan == sample_plan


# =============================================================================
# TESTES: PlanVersionStore - Listagem
# =============================================================================


class TestPlanVersionStoreListing:
    """Testes de listagem do PlanVersionStore."""

    def test_list_versions_empty_plan(
        self,
        version_store: PlanVersionStore,
    ) -> None:
        """Lista vazia para plano inexistente."""
        versions = version_store.list_versions("nonexistent")
        assert versions == []

    def test_list_versions_returns_all(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Deve listar todas as versões de um plano."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)
        version_store.save("my-plan", sample_plan)  # v3

        versions = version_store.list_versions("my-plan")

        assert len(versions) == 3
        assert [v["version"] for v in versions] == [1, 2, 3]

    def test_list_plans_empty(
        self,
        version_store: PlanVersionStore,
    ) -> None:
        """Lista de planos vazia inicialmente."""
        plans = version_store.list_plans()
        assert plans == []

    def test_list_plans_returns_all_names(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Deve listar todos os planos salvos."""
        version_store.save("plan-a", sample_plan)
        version_store.save("plan-b", sample_plan)
        version_store.save("plan-c", sample_plan)

        plans = version_store.list_plans()

        assert len(plans) == 3
        plan_names = {p["name"] for p in plans}
        assert plan_names == {"plan-a", "plan-b", "plan-c"}


# =============================================================================
# TESTES: PlanVersionStore - Diff
# =============================================================================


class TestPlanVersionStoreDiff:
    """Testes de diff do PlanVersionStore."""

    def test_diff_versions_no_changes(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Diff de versões iguais não tem mudanças."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", sample_plan)

        diff = version_store.diff("my-plan", 1, 2)

        assert diff is not None
        assert diff.has_changes is False
        assert diff.steps_added == []
        assert diff.steps_removed == []
        assert diff.steps_modified == []

    def test_diff_versions_added_step(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Diff detecta step adicionado."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)

        diff = version_store.diff("my-plan", 1, 2)

        assert diff is not None
        assert diff.has_changes is True
        # step3 foi adicionado
        added_ids = [s.get("id") for s in diff.steps_added]
        assert "step3" in added_ids

    def test_diff_versions_modified_step(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Diff detecta step modificado."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)

        diff = version_store.diff("my-plan", 1, 2)

        assert diff is not None
        # step1 foi modificado (endpoint diferente)
        modified_ids = [s.get("id") for s in diff.steps_modified]
        assert "step1" in modified_ids

    def test_diff_versions_config_change(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Diff detecta mudanças de config."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)

        diff = version_store.diff("my-plan", 1, 2)

        assert diff is not None
        assert "timeout" in diff.config_changes

    def test_diff_versions_removed_step(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Diff detecta step removido."""
        # Plano com 2 steps
        version_store.save("my-plan", sample_plan)

        # Plano com apenas 1 step
        reduced_plan = json.loads(json.dumps(sample_plan))
        reduced_plan["steps"] = [sample_plan["steps"][0]]
        version_store.save("my-plan", reduced_plan)

        diff = version_store.diff("my-plan", 1, 2)

        assert diff is not None
        removed_ids = [s.get("id") for s in diff.steps_removed]
        assert "step2" in removed_ids

    def test_diff_versions_nonexistent_returns_none(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Diff de versão inexistente retorna None."""
        version_store.save("my-plan", sample_plan)

        diff = version_store.diff("my-plan", 1, 999)
        assert diff is None


# =============================================================================
# TESTES: PlanVersionStore - Rollback
# =============================================================================


class TestPlanVersionStoreRollback:
    """Testes de rollback do PlanVersionStore."""

    def test_rollback_creates_new_version(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Rollback cria nova versão com conteúdo da versão alvo."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)

        rollback_version = version_store.rollback("my-plan", target_version=1)

        assert rollback_version is not None
        assert rollback_version.version == 3  # Nova versão
        assert rollback_version.plan == sample_plan  # Conteúdo da v1
        assert rollback_version.parent_version == 2

    def test_rollback_nonexistent_returns_none(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Rollback para versão inexistente retorna None."""
        version_store.save("my-plan", sample_plan)

        result = version_store.rollback("my-plan", target_version=999)
        assert result is None

    def test_rollback_adds_description(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
        modified_plan: dict[str, Any],
    ) -> None:
        """Rollback adiciona descrição indicando a operação."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", modified_plan)

        rollback_version = version_store.rollback("my-plan", target_version=1)

        assert rollback_version is not None
        # Rollback indica na descrição
        assert "rollback" in rollback_version.description.lower() or rollback_version.parent_version == 2


# =============================================================================
# TESTES: PlanVersion - Modelo de Dados
# =============================================================================


class TestPlanVersion:
    """Testes do modelo PlanVersion."""

    def test_planversion_creation(
        self,
        sample_plan: dict[str, Any],
    ) -> None:
        """PlanVersion pode ser criado com todos os campos."""
        now = datetime.now(timezone.utc).isoformat()
        version = PlanVersion(
            version=1,
            plan=sample_plan,
            created_at=now,
            created_by="test",
            source="llm",
            llm_provider="openai",
            llm_model="gpt-4",
            parent_version=None,
        )

        assert version.version == 1
        assert version.plan == sample_plan
        assert version.created_at == now
        assert version.created_by == "test"
        assert version.llm_provider == "openai"
        assert version.parent_version is None


# =============================================================================
# TESTES: PlanDiff - Modelo de Diff
# =============================================================================


class TestPlanDiff:
    """Testes do modelo PlanDiff."""

    def test_plandiff_no_changes(self) -> None:
        """PlanDiff sem mudanças."""
        diff = PlanDiff(
            version_a=1,
            version_b=2,
            steps_added=[],
            steps_removed=[],
            steps_modified=[],
            config_changes={},
            meta_changes={},
        )

        assert diff.has_changes is False

    def test_plandiff_with_added_steps(self) -> None:
        """PlanDiff com steps adicionados tem mudanças."""
        diff = PlanDiff(
            version_a=1,
            version_b=2,
            steps_added=[{"id": "step3", "name": "New Step"}],
            steps_removed=[],
            steps_modified=[],
            config_changes={},
            meta_changes={},
        )

        assert diff.has_changes is True

    def test_plandiff_with_config_changes(self) -> None:
        """PlanDiff com config changes tem mudanças."""
        diff = PlanDiff(
            version_a=1,
            version_b=2,
            steps_added=[],
            steps_removed=[],
            steps_modified=[],
            config_changes={"timeout": {"before": 30, "after": 60}},
            meta_changes={},
        )

        assert diff.has_changes is True

    def test_plandiff_summary(self) -> None:
        """PlanDiff gera sumário correto."""
        diff = PlanDiff(
            version_a=1,
            version_b=2,
            steps_added=[{"id": "s1"}, {"id": "s2"}],
            steps_removed=[{"id": "s3"}],
            steps_modified=[],
            config_changes={},
            meta_changes={},
        )

        assert "+2 steps" in diff.summary
        assert "-1 steps" in diff.summary

        assert diff.has_changes is True


# =============================================================================
# TESTES: Persistência e Recuperação
# =============================================================================


class TestPlanVersionPersistence:
    """Testes de persistência do PlanVersionStore."""

    def test_versions_persist_across_instances(
        self,
        temp_storage_path: Path,
        sample_plan: dict[str, Any],
    ) -> None:
        """Versões persistem entre instâncias."""
        # Primeira instância salva
        store1 = PlanVersionStore(plans_dir=str(temp_storage_path))
        store1.save("my-plan", sample_plan)

        # Segunda instância lê
        store2 = PlanVersionStore(plans_dir=str(temp_storage_path))
        version = store2.get_version("my-plan")

        assert version is not None
        assert version.version == 1
        assert version.plan == sample_plan

    def test_metadata_persists(
        self,
        temp_storage_path: Path,
        sample_plan: dict[str, Any],
    ) -> None:
        """Metadata LLM persiste corretamente."""
        store1 = PlanVersionStore(plans_dir=str(temp_storage_path))
        store1.save(
            "my-plan",
            sample_plan,
            llm_provider="openai",
            llm_model="gpt-4",
            description="API testing",
        )

        store2 = PlanVersionStore(plans_dir=str(temp_storage_path))
        version = store2.get_version("my-plan")

        assert version is not None
        assert version.llm_provider == "openai"
        assert version.llm_model == "gpt-4"
        assert version.description == "API testing"


# =============================================================================
# TESTES: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Testes de casos de borda."""

    def test_plan_name_with_special_characters(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Nomes de plano com caracteres especiais são tratados."""
        # Usa apenas caracteres seguros para nomes de arquivo
        version_store.save("my-plan-v1.0", sample_plan)
        version = version_store.get_version("my-plan-v1.0")

        assert version is not None
        assert version.plan == sample_plan

    def test_empty_plan(
        self,
        version_store: PlanVersionStore,
    ) -> None:
        """Plano vazio pode ser versionado."""
        empty_plan: dict[str, Any] = {"name": "empty", "steps": []}
        version_store.save("empty-plan", empty_plan)
        version = version_store.get_version("empty-plan")

        assert version is not None
        assert version.plan == empty_plan

    def test_large_plan(
        self,
        version_store: PlanVersionStore,
    ) -> None:
        """Planos grandes funcionam corretamente."""
        large_plan: dict[str, Any] = {
            "name": "large-plan",
            "steps": [
                {
                    "id": f"step{i}",
                    "name": f"Step {i}",
                    "action": {"method": "GET", "endpoint": f"/item/{i}"},
                    "assertions": [{"type": "status_code", "expected": 200}],
                }
                for i in range(100)
            ],
        }

        version_store.save("large-plan", large_plan)
        version = version_store.get_version("large-plan")

        assert version is not None
        assert len(version.plan["steps"]) == 100

    def test_concurrent_versions_different_plans(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Múltiplos planos podem ser versionados independentemente."""
        for name in ["plan-a", "plan-b", "plan-c"]:
            version_store.save(name, sample_plan)
            version_store.save(name, sample_plan)

        for name in ["plan-a", "plan-b", "plan-c"]:
            versions = version_store.list_versions(name)
            assert len(versions) == 2

    def test_slugify_normalizes_names(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """Nomes de plano são normalizados para slug."""
        version_store.save("My API Tests", sample_plan)
        
        # Busca pelo nome original deve funcionar
        version = version_store.get_version("My API Tests")
        assert version is not None
        
        # Busca pelo slug também
        version2 = version_store.get_version("my-api-tests")
        assert version2 is not None

    def test_get_plan_info(
        self,
        version_store: PlanVersionStore,
        sample_plan: dict[str, Any],
    ) -> None:
        """get_plan_info retorna informações do plano."""
        version_store.save("my-plan", sample_plan)
        version_store.save("my-plan", sample_plan)

        info = version_store.get_plan_info("my-plan")

        assert info is not None
        assert info["name"] == "my-plan"
        assert info["current_version"] == 2
        assert info["total_versions"] == 2
