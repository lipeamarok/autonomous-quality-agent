"""
================================================================================
TESTES DE INTEGRAÇÃO END-TO-END
================================================================================

Este módulo testa o fluxo completo:
    LLM Generation → Cache → UTDLValidator → (Runner execution mock)

Para todos entenderem:

Imagine que você está testando uma linha de montagem de carros:
1. O robô monta o carro (LLM gera plano)
2. O carro vai para inspeção (UTDLValidator valida)
3. O carro é guardado no estacionamento (PlanCache armazena)
4. O carro é testado na pista (Runner executa) - MOCK

Estes testes garantem que todas as peças funcionam juntas!
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

# Adiciona o diretório brain ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cache import PlanCache
from src.validator import (
    UTDLValidator,
    ValidationMode,
)


# =============================================================================
# TYPE ALIASES
# =============================================================================

PlanDict = dict[str, Any]


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_cache_dir() -> Generator[str, None, None]:
    """Cria diretório temporário para cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def valid_plan_dict() -> PlanDict:
    """Retorna um plano UTDL válido para testes."""
    return {
        "spec_version": "0.1",
        "meta": {
            "id": "test-plan-001",
            "name": "Teste de Login API",
            "version": "1.0.0",
            "description": "Testa endpoints de autenticação"
        },
        "config": {
            "base_url": "https://api.example.com",
            "variables": {
                "username": "testuser",
                "password": "testpass123"
            }
        },
        "steps": [
            {
                "id": "step_health",
                "description": "Verifica se API está online",
                "action": "http_request",
                "depends_on": [],
                "params": {
                    "method": "GET",
                    "path": "/health"
                },
                "assertions": [
                    {"type": "status_code", "operator": "eq", "value": 200}
                ],
                "extract": []
            },
            {
                "id": "step_login",
                "description": "Faz login com credenciais",
                "action": "http_request",
                "depends_on": ["step_health"],
                "params": {
                    "method": "POST",
                    "path": "/auth/login",
                    "body": {
                        "username": "{{username}}",
                        "password": "{{password}}"
                    }
                },
                "assertions": [
                    {"type": "status_code", "operator": "eq", "value": 200},
                    {"type": "json_body", "path": "$.token", "operator": "neq", "value": ""}
                ],
                "extract": [
                    {"source": "body", "path": "$.token", "target": "auth_token"}
                ]
            },
            {
                "id": "step_profile",
                "description": "Busca perfil do usuário autenticado",
                "action": "http_request",
                "depends_on": ["step_login"],
                "params": {
                    "method": "GET",
                    "path": "/users/me",
                    "headers": {
                        "Authorization": "Bearer {{auth_token}}"
                    }
                },
                "assertions": [
                    {"type": "status_code", "operator": "eq", "value": 200},
                    {"type": "json_body", "path": "$.username", "operator": "eq", "value": "testuser"}
                ],
                "extract": []
            }
        ]
    }


@pytest.fixture
def partial_plan_dict() -> PlanDict:
    """Retorna um plano parcial (com dependência faltando)."""
    return {
        "spec_version": "0.1",
        "meta": {
            "id": "partial-plan-001",
            "name": "Plano Parcial",
            "version": "1.0.0"
        },
        "config": {
            "base_url": "https://api.example.com",
            "variables": {}
        },
        "steps": [
            {
                "id": "step_1",
                "description": "Step com dependência inexistente",
                "action": "http_request",
                "depends_on": ["step_0_missing"],  # Não existe!
                "params": {"method": "GET", "path": "/test"},
                "assertions": [],
                "extract": []
            }
        ]
    }


# =============================================================================
# TESTES DE INTEGRAÇÃO: VALIDADOR + CACHE
# =============================================================================


class TestValidatorCacheIntegration:
    """Testes de integração entre UTDLValidator e PlanCache."""

    def test_valid_plan_flows_through_validator_and_cache(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """Plano válido deve passar pelo validador e ser cacheado."""
        # Arrange
        validator = UTDLValidator(mode=ValidationMode.DEFAULT)
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)
        requirements = "testar login API"
        base_url = "https://api.example.com"

        # Act - Valida
        result = validator.validate(valid_plan_dict)

        # Assert - Validação OK
        assert result.is_valid is True
        assert result.plan is not None
        assert len(result.errors) == 0

        # Act - Cacheia
        hash_key = cache.store(requirements, base_url, valid_plan_dict)

        # Assert - Cache OK
        assert hash_key != ""
        cached = cache.get(requirements, base_url)
        assert cached is not None
        assert cached["meta"]["id"] == "test-plan-001"

    def test_strict_mode_rejects_partial_plan(self, partial_plan_dict: PlanDict) -> None:
        """Modo STRICT deve rejeitar plano parcial."""
        validator = UTDLValidator(mode=ValidationMode.STRICT)

        result = validator.validate(partial_plan_dict)

        assert result.is_valid is False
        assert any("step_0_missing" in err for err in result.errors)

    def test_lenient_mode_accepts_partial_plan(self, partial_plan_dict: PlanDict) -> None:
        """Modo LENIENT deve aceitar plano parcial com warnings."""
        validator = UTDLValidator(mode=ValidationMode.LENIENT)

        result = validator.validate(partial_plan_dict)

        # Em modo leniente, dependência faltando vira warning
        assert result.is_valid is True
        assert any("step_0_missing" in w for w in result.warnings)

    def test_cache_invalidation_works(self, temp_cache_dir: str, valid_plan_dict: PlanDict) -> None:
        """Invalidação do cache deve funcionar corretamente."""
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)
        requirements = "teste invalidação"
        base_url = "https://api.test.com"

        # Store
        cache.store(requirements, base_url, valid_plan_dict)
        assert cache.get(requirements, base_url) is not None

        # Invalidate
        removed = cache.invalidate(requirements, base_url)
        assert removed is True
        assert cache.get(requirements, base_url) is None

    def test_cache_clear_removes_all_entries(self, temp_cache_dir: str, valid_plan_dict: PlanDict) -> None:
        """Limpar cache deve remover todas as entradas."""
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)

        # Adiciona várias entradas
        cache.store("req1", "url1", valid_plan_dict)
        cache.store("req2", "url2", valid_plan_dict)
        cache.store("req3", "url3", valid_plan_dict)

        stats = cache.stats()
        assert stats.entries == 3

        # Clear
        removed = cache.clear()
        assert removed == 3

        stats = cache.stats()
        assert stats.entries == 0


# =============================================================================
# TESTES DE INTEGRAÇÃO: FLUXO COMPLETO COM MOCK DE LLM
# =============================================================================


class TestEndToEndFlow:
    """Testes do fluxo completo LLM → Cache → Validator."""

    def test_full_flow_generation_to_cache(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Simula fluxo completo:
        1. LLM gera plano (mock)
        2. Validador verifica
        3. Cache armazena
        4. Cache retorna em chamada subsequente
        """
        # Arrange
        validator = UTDLValidator(mode=ValidationMode.DEFAULT)
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)
        requirements = "Teste API de login com autenticação JWT"
        base_url = "https://api.example.com"

        # Act 1 - Mock LLM gerando plano
        generated_plan = valid_plan_dict  # Em prod seria LLM output

        # Act 2 - Valida
        result = validator.validate(generated_plan)
        assert result.is_valid is True

        # Act 3 - Cacheia (se válido)
        if result.is_valid and result.plan:
            cache.store(requirements, base_url, generated_plan)

        # Act 4 - Segunda "chamada" usa cache
        cached_plan = cache.get(requirements, base_url)

        # Assert
        assert cached_plan is not None
        assert cached_plan["meta"]["name"] == "Teste de Login API"
        assert len(cached_plan["steps"]) == 3

    def test_cache_hit_skips_llm_call(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """Cache hit deve evitar chamada ao LLM."""
        # Arrange
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)
        requirements = "teste cache hit"
        base_url = "https://api.cached.com"

        # Pre-populate cache
        cache.store(requirements, base_url, valid_plan_dict)

        # Act - Simula lógica do generator
        llm_called = False

        def mock_llm_generate():
            nonlocal llm_called
            llm_called = True
            return valid_plan_dict

        # Lógica: verifica cache antes de chamar LLM
        cached = cache.get(requirements, base_url)
        if cached is None:
            plan = mock_llm_generate()
        else:
            plan = cached

        # Assert
        assert llm_called is False  # LLM não foi chamado!
        assert plan is not None

    def test_different_inputs_create_different_cache_entries(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """Inputs diferentes devem criar entradas de cache diferentes."""
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)

        # Store com inputs diferentes
        hash1 = cache.store("requirements A", "https://api-a.com", valid_plan_dict)
        hash2 = cache.store("requirements B", "https://api-b.com", valid_plan_dict)

        # Hashes devem ser diferentes
        assert hash1 != hash2

        # Cada um deve ter sua entrada
        assert cache.get("requirements A", "https://api-a.com") is not None
        assert cache.get("requirements B", "https://api-b.com") is not None
        assert cache.get("requirements C", "https://api-c.com") is None  # Não existe


# =============================================================================
# TESTES DE SERIALIZAÇÃO E FORMATO
# =============================================================================


class TestPlanSerialization:
    """Testes de serialização de planos."""

    def test_plan_to_json_is_valid(self, valid_plan_dict: PlanDict) -> None:
        """Plano validado deve serializar para JSON válido."""
        validator = UTDLValidator()
        result = validator.validate(valid_plan_dict)

        assert result.plan is not None

        # Serializa para JSON
        json_str = result.plan.to_json()

        # Parseia de volta
        parsed = json.loads(json_str)

        assert parsed["meta"]["id"] == "test-plan-001"
        assert len(parsed["steps"]) == 3

    def test_validator_from_json_string(self, valid_plan_dict: PlanDict) -> None:
        """Validador deve aceitar string JSON."""
        validator = UTDLValidator()
        json_str = json.dumps(valid_plan_dict)

        result = validator.validate_json(json_str)

        assert result.is_valid is True
        assert result.plan is not None

    def test_validator_rejects_invalid_json(self) -> None:
        """Validador deve rejeitar JSON inválido."""
        validator = UTDLValidator()

        result = validator.validate_json("{ invalid json }")

        assert result.is_valid is False
        assert any("JSON inválido" in err for err in result.errors)


# =============================================================================
# TESTES DE CONCORRÊNCIA (BÁSICO)
# =============================================================================


class TestCacheConcurrency:
    """Testes básicos de concorrência do cache."""

    def test_concurrent_reads_same_entry(self, temp_cache_dir: str, valid_plan_dict: PlanDict) -> None:
        """Múltiplas leituras concorrentes do mesmo entry devem funcionar."""
        import threading

        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)
        cache.store("concurrent-req", "https://concurrent.com", valid_plan_dict)

        results: list[bool] = []
        errors: list[str] = []

        def read_cache():
            try:
                result = cache.get("concurrent-req", "https://concurrent.com")
                results.append(result is not None)
            except Exception as e:
                errors.append(str(e))

        # Cria 10 threads de leitura
        threads = [threading.Thread(target=read_cache) for _ in range(10)]

        # Inicia todas
        for t in threads:
            t.start()

        # Aguarda todas
        for t in threads:
            t.join()

        # Verifica
        assert len(errors) == 0
        assert all(results)  # Todas as leituras retornaram dados

    def test_concurrent_writes_different_entries(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """Escritas concorrentes em entries diferentes devem funcionar."""
        import threading

        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)
        errors: list[str] = []

        def write_cache(idx: int):
            try:
                cache.store(f"req-{idx}", f"https://url-{idx}.com", valid_plan_dict)
            except Exception as e:
                errors.append(str(e))

        # Cria 10 threads de escrita
        threads = [threading.Thread(target=write_cache, args=(i,)) for i in range(10)]

        # Inicia todas
        for t in threads:
            t.start()

        # Aguarda todas
        for t in threads:
            t.join()

        # Verifica
        assert len(errors) == 0
        stats = cache.stats()
        assert stats.entries == 10


# =============================================================================
# TESTES DE CACHE COM PROVIDER/MODEL
# =============================================================================


class TestCacheProviderModel:
    """
    Testes para garantir que provider/model afetam o hash do cache.

    Isso é crucial para evitar que planos de modelos menos capazes
    sejam retornados quando o usuário espera qualidade premium.
    """

    def test_same_input_different_providers_different_hashes(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Mesmo input com providers diferentes = hashes diferentes.

        Cenário: Usuário gera plano com grok-4-fast (barato),
        depois muda para gpt-5.1 (premium). Deve receber plano novo!
        """
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)

        # Armazena com OpenAI
        hash_openai = cache.store(
            requirements="teste login API",
            base_url="https://api.example.com",
            plan=valid_plan_dict,
            provider="openai",
            model="gpt-5.1"
        )

        # Armazena com xAI
        hash_xai = cache.store(
            requirements="teste login API",
            base_url="https://api.example.com",
            plan=valid_plan_dict,
            provider="xai",
            model="grok-4"
        )

        # Hashes devem ser diferentes
        assert hash_openai != hash_xai

        # Deve haver 2 entradas no cache
        stats = cache.stats()
        assert stats.entries == 2

    def test_same_provider_different_models_different_hashes(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Mesmo provider com modelos diferentes = hashes diferentes.

        Cenário: Usuário usa gpt-4 para draft, gpt-5.1 para produção.
        """
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)

        hash_gpt4 = cache.store(
            requirements="teste API",
            base_url="https://api.example.com",
            plan=valid_plan_dict,
            provider="openai",
            model="gpt-4"
        )

        hash_gpt5 = cache.store(
            requirements="teste API",
            base_url="https://api.example.com",
            plan=valid_plan_dict,
            provider="openai",
            model="gpt-5.1"
        )

        assert hash_gpt4 != hash_gpt5

    def test_get_returns_correct_plan_for_provider_model(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Get com provider/model retorna apenas plano do mesmo provider/model.
        """
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)

        # Modifica plano para diferenciar
        plan_openai: PlanDict = {**valid_plan_dict, "meta": {**valid_plan_dict["meta"], "name": "OpenAI Plan"}}
        plan_xai: PlanDict = {**valid_plan_dict, "meta": {**valid_plan_dict["meta"], "name": "xAI Plan"}}

        cache.store("req", "https://api.com", plan_openai, provider="openai", model="gpt-5.1")
        cache.store("req", "https://api.com", plan_xai, provider="xai", model="grok-4")

        # Busca específica por provider/model
        result_openai = cache.get("req", "https://api.com", provider="openai", model="gpt-5.1")
        result_xai = cache.get("req", "https://api.com", provider="xai", model="grok-4")

        assert result_openai is not None
        assert result_xai is not None
        assert result_openai["meta"]["name"] == "OpenAI Plan"
        assert result_xai["meta"]["name"] == "xAI Plan"

    def test_backward_compatible_without_provider_model(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Cache funciona sem provider/model (backward compatible).
        """
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)

        # Armazena sem provider/model
        hash_key = cache.store("req", "https://api.com", valid_plan_dict)
        assert hash_key != ""

        # Busca sem provider/model
        result = cache.get("req", "https://api.com")
        assert result is not None
        assert result["meta"]["id"] == valid_plan_dict["meta"]["id"]

    def test_entry_stores_provider_model_metadata(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Entry armazenada contém metadados de provider/model para debug.
        """
        import json
        from pathlib import Path

        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True)

        hash_key = cache.store(
            "req", "https://api.com", valid_plan_dict,
            provider="openai", model="gpt-5.1"
        )

        # Lê arquivo diretamente
        filepath = Path(temp_cache_dir) / f"{hash_key}.json"
        with open(filepath, "r") as f:
            entry = json.load(f)

        assert entry["provider"] == "openai"
        assert entry["model"] == "gpt-5.1"


# =============================================================================
# TESTES DE CACHE COM TTL E COMPRESSÃO
# =============================================================================


class TestCacheTTLAndCompression:
    """
    Testes para funcionalidades de TTL e compressão do cache.
    """

    def test_cache_with_ttl_stores_expiry(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Cache com TTL armazena data de expiração.
        """
        from datetime import datetime, timezone, timedelta

        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True, ttl_days=7)

        hash_key = cache.store("req", "https://api.com", valid_plan_dict)

        # Verifica que entry tem expires_at
        assert hash_key in cache._index
        entry_meta = cache._index[hash_key]
        assert entry_meta["expires_at"] is not None

        # Verifica que expiração é aproximadamente 7 dias
        expires = datetime.fromisoformat(entry_meta["expires_at"].replace("Z", "+00:00"))
        expected = datetime.now(timezone.utc) + timedelta(days=7)
        diff = abs((expires - expected).total_seconds())
        assert diff < 60  # Menos de 1 minuto de diferença

    def test_cache_without_ttl_no_expiry(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Cache sem TTL não tem data de expiração.
        """
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True, ttl_days=None)

        hash_key = cache.store("req", "https://api.com", valid_plan_dict)

        entry_meta = cache._index[hash_key]
        assert entry_meta["expires_at"] is None

    def test_cache_with_compression_creates_gzip(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Cache com compressão cria arquivos .gz.
        """
        import gzip
        from pathlib import Path

        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True, compress=True)

        hash_key = cache.store("req", "https://api.com", valid_plan_dict)

        # Verifica que arquivo é .json.gz
        filepath = Path(temp_cache_dir) / f"{hash_key}.json.gz"
        assert filepath.exists()

        # Verifica que é gzip válido
        with gzip.open(filepath, "rt", encoding="utf-8") as f:
            entry = json.load(f)
        assert entry["plan"]["meta"]["id"] == valid_plan_dict["meta"]["id"]

    def test_cache_compressed_can_be_retrieved(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Cache comprimido pode ser lido corretamente.
        """
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True, compress=True)

        cache.store("req", "https://api.com", valid_plan_dict)
        result = cache.get("req", "https://api.com")

        assert result is not None
        assert result["meta"]["id"] == valid_plan_dict["meta"]["id"]

    def test_cache_stats_shows_compression_info(
        self, temp_cache_dir: str, valid_plan_dict: PlanDict
    ) -> None:
        """
        Stats mostra informações sobre compressão.
        """
        cache = PlanCache(cache_dir=temp_cache_dir, enabled=True, compress=True)

        cache.store("req1", "https://api.com", valid_plan_dict)
        cache.store("req2", "https://api.com", valid_plan_dict)

        stats = cache.stats()
        assert stats.compressed_entries == 2
        assert stats.size_bytes > 0


# =============================================================================
# TESTES DE HISTÓRICO DE EXECUÇÕES
# =============================================================================


class TestExecutionHistory:
    """
    Testes para o sistema de histórico de execuções.
    """

    def test_record_execution_creates_entry(
        self, temp_cache_dir: str
    ) -> None:
        """
        Registrar execução cria entrada no histórico.
        """
        from src.cache import ExecutionHistory

        history = ExecutionHistory(history_dir=temp_cache_dir, enabled=True)

        record = history.record_execution(
            plan_file="test_plan.json",
            duration_ms=1500,
            total_steps=5,
            passed_steps=4,
            failed_steps=1,
            status="failure",
        )

        assert record.id != "disabled"
        assert record.plan_file == "test_plan.json"
        assert record.status == "failure"

    def test_get_recent_returns_latest(
        self, temp_cache_dir: str
    ) -> None:
        """
        get_recent retorna execuções mais recentes primeiro.
        """
        from src.cache import ExecutionHistory

        history = ExecutionHistory(history_dir=temp_cache_dir, enabled=True)

        # Registra 3 execuções
        history.record_execution(
            plan_file="plan1.json", duration_ms=100,
            total_steps=1, passed_steps=1, failed_steps=0, status="success"
        )
        history.record_execution(
            plan_file="plan2.json", duration_ms=200,
            total_steps=2, passed_steps=2, failed_steps=0, status="success"
        )
        history.record_execution(
            plan_file="plan3.json", duration_ms=300,
            total_steps=3, passed_steps=3, failed_steps=0, status="success"
        )

        recent = history.get_recent(limit=2)

        assert len(recent) == 2
        assert recent[0]["plan_file"] == "plan3.json"  # Mais recente primeiro
        assert recent[1]["plan_file"] == "plan2.json"

    def test_get_by_status_filters_correctly(
        self, temp_cache_dir: str
    ) -> None:
        """
        get_by_status filtra por status corretamente.
        """
        from src.cache import ExecutionHistory

        history = ExecutionHistory(history_dir=temp_cache_dir, enabled=True)

        history.record_execution(
            plan_file="pass1.json", duration_ms=100,
            total_steps=1, passed_steps=1, failed_steps=0, status="success"
        )
        history.record_execution(
            plan_file="fail1.json", duration_ms=200,
            total_steps=2, passed_steps=1, failed_steps=1, status="failure"
        )
        history.record_execution(
            plan_file="pass2.json", duration_ms=300,
            total_steps=3, passed_steps=3, failed_steps=0, status="success"
        )

        successes = history.get_by_status("success")
        failures = history.get_by_status("failure")

        assert len(successes) == 2
        assert len(failures) == 1
        assert failures[0]["plan_file"] == "fail1.json"

    def test_history_stats(
        self, temp_cache_dir: str
    ) -> None:
        """
        Stats retorna contagens corretas.
        """
        from src.cache import ExecutionHistory

        history = ExecutionHistory(history_dir=temp_cache_dir, enabled=True)

        history.record_execution(
            plan_file="p1.json", duration_ms=100,
            total_steps=1, passed_steps=1, failed_steps=0, status="success"
        )
        history.record_execution(
            plan_file="p2.json", duration_ms=100,
            total_steps=1, passed_steps=0, failed_steps=1, status="failure"
        )
        history.record_execution(
            plan_file="p3.json", duration_ms=100,
            total_steps=1, passed_steps=0, failed_steps=0, status="error"
        )

        stats = history.stats()

        assert stats["enabled"] is True
        assert stats["total_records"] == 3
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["error_count"] == 1

    def test_history_disabled_returns_empty(
        self, temp_cache_dir: str
    ) -> None:
        """
        Histórico desabilitado retorna listas vazias.
        """
        from src.cache import ExecutionHistory

        history = ExecutionHistory(history_dir=temp_cache_dir, enabled=False)

        record = history.record_execution(
            plan_file="test.json", duration_ms=100,
            total_steps=1, passed_steps=1, failed_steps=0, status="success"
        )

        assert record.id == "disabled"
        assert history.get_recent() == []
        assert history.stats()["enabled"] is False


# =============================================================================
# TESTES DE CONFIG COM CACHE E HISTÓRICO
# =============================================================================


class TestConfigCacheIntegration:
    """
    Testes de integração entre BrainConfig e cache/history.
    """

    def test_config_get_cache_local(
        self, temp_cache_dir: str
    ) -> None:
        """
        Config cria cache local corretamente.
        """
        from src.config import BrainConfig

        config = BrainConfig(
            cache_enabled=True,
            cache_global=False,
            cache_dir=temp_cache_dir,
        )

        cache = config.get_cache()

        assert cache.enabled is True
        assert str(cache.cache_dir) == temp_cache_dir

    def test_config_for_production_uses_global_cache(self) -> None:
        """
        Config de produção usa cache global por padrão.
        """
        from src.config import BrainConfig

        config = BrainConfig.for_production()

        assert config.cache_global is True
        assert config.cache_ttl_days == 30
        assert config.cache_compress is True

    def test_config_for_testing_disables_cache(self) -> None:
        """
        Config de testes desabilita cache.
        """
        from src.config import BrainConfig

        config = BrainConfig.for_testing()

        assert config.cache_enabled is False
        assert config.history_enabled is False
