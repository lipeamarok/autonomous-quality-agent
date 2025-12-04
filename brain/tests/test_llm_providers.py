"""
Testes para o módulo LLM Providers.

## Cobertura:

1. MockLLMProvider
   - Geração baseada em palavras-chave
   - Simulação de falha
   - Contadores e reset

2. RealLLMProvider
   - Fallback entre providers
   - Detecção de disponibilidade

3. get_llm_provider()
   - Seleção por parâmetro
   - Seleção por env var
   - Seleção por config
   - Auto-detect
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from src.llm import (
    LLMResponse,
    MockLLMProvider,
    RealLLMProvider,
    get_llm_provider,
)
from src.llm.providers import get_available_modes


# =============================================================================
# Testes: LLMResponse
# =============================================================================

class TestLLMResponse:
    """Testes para a classe LLMResponse."""

    def test_basic_response(self):
        """Cria resposta básica."""
        response = LLMResponse(
            content="teste",
            model="gpt-4",
            provider="openai",
        )
        assert response.content == "teste"
        assert response.model == "gpt-4"
        assert response.provider == "openai"
        assert response.tokens_used == 0
        assert response.latency_ms == 0.0

    def test_is_mock_property(self):
        """Verifica detecção de mock."""
        real_response = LLMResponse(
            content="x",
            model="gpt-4",
            provider="openai",
        )
        mock_response = LLMResponse(
            content="x",
            model="mock-v1",
            provider="mock",
        )

        assert not real_response.is_mock
        assert mock_response.is_mock

    def test_with_metadata(self):
        """Resposta com metadados."""
        response = LLMResponse(
            content="x",
            model="gpt-4",
            provider="openai",
            metadata={"finish_reason": "stop"},
        )
        assert response.metadata["finish_reason"] == "stop"


# =============================================================================
# Testes: MockLLMProvider
# =============================================================================

class TestMockLLMProvider:
    """Testes para MockLLMProvider."""

    def test_name_and_availability(self):
        """Provider mock sempre disponível."""
        provider = MockLLMProvider()
        assert provider.name == "mock"
        assert provider.is_available() is True

    def test_generate_login_template(self):
        """Prompt com 'login' retorna template de login."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("Quero testar o fluxo de login")

        assert response.is_mock
        assert response.model == "mock-v1"

        plan = json.loads(response.content)
        assert "steps" in plan
        assert any("login" in s["id"] for s in plan["steps"])

    def test_generate_crud_template(self):
        """Prompt com 'crud' retorna template CRUD."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("Teste CRUD completo")

        plan = json.loads(response.content)
        step_ids = [s["id"] for s in plan["steps"]]
        assert "create" in step_ids
        assert "read" in step_ids
        assert "update" in step_ids
        assert "delete" in step_ids

    def test_generate_health_template(self):
        """Prompt com 'health' retorna template de health check."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("Verificar health da API")

        plan = json.loads(response.content)
        assert len(plan["steps"]) == 1
        assert plan["steps"][0]["id"] == "health"

    def test_generate_default_template(self):
        """Prompt sem palavra-chave retorna template padrão."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("algo completamente diferente xyz123")

        plan = json.loads(response.content)
        assert "steps" in plan
        assert response.metadata["template_used"] == "default"

    def test_call_counter(self):
        """Conta chamadas ao generate."""
        provider = MockLLMProvider(latency_ms=0)
        assert provider.call_count == 0

        provider.generate("teste 1")
        assert provider.call_count == 1

        provider.generate("teste 2")
        assert provider.call_count == 2

    def test_last_prompt(self):
        """Armazena último prompt."""
        provider = MockLLMProvider(latency_ms=0)
        provider.generate("meu prompt especial")
        assert provider.last_prompt == "meu prompt especial"

    def test_simulated_failure(self):
        """Simula falha para teste de fallback."""
        provider = MockLLMProvider(latency_ms=0)
        provider.set_fail_on_next(True)

        with pytest.raises(ConnectionError, match="Simulated failure"):
            provider.generate("teste")

        # Próxima chamada deve funcionar
        response = provider.generate("teste")
        assert response.content is not None

    def test_reset(self):
        """Reseta estado do provider."""
        provider = MockLLMProvider(latency_ms=0)
        provider.generate("teste")
        provider.set_fail_on_next(True)

        provider.reset()

        assert provider.call_count == 0
        assert provider.last_prompt is None
        # Não deve falhar após reset
        response = provider.generate("teste")
        assert response.content is not None


# =============================================================================
# Testes: RealLLMProvider
# =============================================================================

class TestRealLLMProvider:
    """Testes para RealLLMProvider."""

    def test_no_api_keys_not_available(self):
        """Sem API keys, provider não está disponível."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove todas as API keys
            for key in ["OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY"]:
                os.environ.pop(key, None)

            provider = RealLLMProvider()
            assert provider.is_available() is False
            assert provider.available_providers == []

    def test_generate_without_keys_raises(self):
        """Generate sem keys disponíveis levanta erro."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY"]:
                os.environ.pop(key, None)

            provider = RealLLMProvider()

            with pytest.raises(RuntimeError, match="Nenhum provider LLM disponível"):
                provider.generate("teste")

    @patch("src.llm.provider_real.RealLLMProvider._call_provider")
    def test_fallback_on_failure(self, mock_call: MagicMock) -> None:
        """Fallback quando primeiro provider falha."""
        # Simula: OpenAI falha, xAI funciona
        mock_call.side_effect = [
            ConnectionError("OpenAI down"),
            LLMResponse(content="ok", model="grok-2", provider="xai"),
        ]

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "fake-key",
            "XAI_API_KEY": "fake-key",
        }):
            provider = RealLLMProvider()
            # Força re-init dos clientes mock (usando objeto interno para teste)
            provider._clients = {"openai": MagicMock(), "xai": MagicMock()}  # type: ignore[misc]

            response = provider.generate("teste")

            assert response.provider == "xai"
            assert provider.last_provider_used == "xai"

    @patch("src.llm.provider_real.RealLLMProvider._call_provider")
    def test_no_fallback_when_disabled(self, mock_call: MagicMock) -> None:
        """Sem fallback quando desabilitado."""
        mock_call.side_effect = ConnectionError("OpenAI down")

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "fake-key",
            "XAI_API_KEY": "fake-key",
        }):
            provider = RealLLMProvider(enable_fallback=False)
            provider._clients = {"openai": MagicMock(), "xai": MagicMock()}  # type: ignore[misc]

            with pytest.raises(ConnectionError):
                provider.generate("teste")

    @patch("src.llm.provider_real.RealLLMProvider._call_provider")
    def test_preferred_provider_first(self, mock_call: MagicMock) -> None:
        """Provider preferido é tentado primeiro."""
        mock_call.return_value = LLMResponse(
            content="ok", model="grok-2", provider="xai"
        )

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "fake-key",
            "XAI_API_KEY": "fake-key",
        }):
            provider = RealLLMProvider(preferred_provider="xai")
            provider._clients = {"openai": MagicMock(), "xai": MagicMock()}  # type: ignore[misc]

            provider.generate("teste")

            # Verifica que xai foi chamado primeiro
            first_call = mock_call.call_args_list[0]
            assert first_call[0][0] == "xai"


# =============================================================================
# Testes: get_llm_provider()
# =============================================================================

class TestGetLLMProvider:
    """Testes para a factory get_llm_provider."""

    def test_explicit_mock_mode(self):
        """Modo mock explícito."""
        provider = get_llm_provider(mode="mock")
        assert isinstance(provider, MockLLMProvider)
        assert provider.name == "mock"

    def test_explicit_real_mode(self):
        """Modo real explícito."""
        provider = get_llm_provider(mode="real")
        assert isinstance(provider, RealLLMProvider)
        assert provider.name == "real"

    def test_env_var_mode(self):
        """Modo via variável de ambiente."""
        with patch.dict(os.environ, {"AQA_LLM_MODE": "mock"}):
            provider = get_llm_provider()
            assert isinstance(provider, MockLLMProvider)

    def test_config_mode(self):
        """Modo via config dict."""
        config = {"llm": {"mode": "mock"}}
        provider = get_llm_provider(config=config)
        assert isinstance(provider, MockLLMProvider)

    def test_priority_param_over_env(self):
        """Parâmetro tem prioridade sobre env."""
        with patch.dict(os.environ, {"AQA_LLM_MODE": "real"}):
            provider = get_llm_provider(mode="mock")
            assert isinstance(provider, MockLLMProvider)

    def test_priority_env_over_config(self):
        """Env tem prioridade sobre config."""
        config = {"llm": {"mode": "real"}}
        with patch.dict(os.environ, {"AQA_LLM_MODE": "mock"}):
            provider = get_llm_provider(config=config)
            assert isinstance(provider, MockLLMProvider)

    def test_auto_detect_no_keys(self):
        """Auto-detect: sem keys → mock."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY", "AQA_LLM_MODE"]:
                os.environ.pop(key, None)

            provider = get_llm_provider()
            assert isinstance(provider, MockLLMProvider)

    def test_auto_detect_with_key(self):
        """Auto-detect: com key → real."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            # Remove mode override
            os.environ.pop("AQA_LLM_MODE", None)

            provider = get_llm_provider()
            assert isinstance(provider, RealLLMProvider)


# =============================================================================
# Testes: get_available_modes()
# =============================================================================

class TestGetAvailableModes:
    """Testes para get_available_modes."""

    def test_mock_always_available(self):
        """Mock sempre disponível."""
        modes = get_available_modes()
        assert modes["mock"] is True

    def test_real_depends_on_keys(self):
        """Real depende de API keys."""
        with patch.dict(os.environ, {}, clear=True):
            for key in ["OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY"]:
                os.environ.pop(key, None)

            modes = get_available_modes()
            assert modes["real"] is False
            assert modes["available_providers"] == []


# =============================================================================
# Testes: Conformidade UTDL
# =============================================================================

class TestUTDLConformance:
    """Testes de conformidade do UTDL gerado pelo mock."""

    def test_mock_generates_valid_utdl_structure(self):
        """Mock gera estrutura UTDL válida."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("teste de login")

        plan = json.loads(response.content)

        # Campos obrigatórios
        assert "meta" in plan
        assert "config" in plan
        assert "steps" in plan

        # Meta
        assert "name" in plan["meta"]
        assert "version" in plan["meta"]

        # Config
        assert "base_url" in plan["config"]

        # Steps
        assert isinstance(plan["steps"], list)
        assert len(plan["steps"]) > 0

        for step in plan["steps"]:
            assert "id" in step
            assert "action" in step
            assert step["action"] == "http_request"
            assert "params" in step
            assert "method" in step["params"]
            assert "path" in step["params"]

    def test_mock_steps_have_assertions(self):
        """Steps do mock têm assertions."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("login")

        plan = json.loads(response.content)

        for step in plan["steps"]:
            assert "assertions" in step
            assert len(step["assertions"]) > 0

    def test_mock_login_has_extraction(self):
        """Template de login tem extração de token."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("login")

        plan = json.loads(response.content)
        login_step = plan["steps"][0]

        assert "extract" in login_step
        assert len(login_step["extract"]) > 0
        assert any(e["target"] == "auth_token" for e in login_step["extract"])


# =============================================================================
# Testes: Invariância de Prompt
# =============================================================================

class TestPromptInvariance:
    """
    Testes de invariância: variações do input devem gerar estrutura consistente.
    """

    @pytest.mark.parametrize("prompt", [
        "login",
        "faça login",
        "testar o fluxo de autenticação com login",
        "cenário: login do usuário",
        "LOGIN",
        "  login  ",
    ])
    def test_login_variations_generate_login_template(self, prompt: str):
        """Variações de 'login' geram template de login."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate(prompt)

        plan = json.loads(response.content)

        # Deve ter pelo menos 1 step
        assert len(plan["steps"]) >= 1

        # Deve ter método POST (login é POST)
        login_step = plan["steps"][0]
        assert login_step["params"]["method"] == "POST"

        # Deve ter assertions básicas
        assert len(login_step["assertions"]) > 0

    @pytest.mark.parametrize("prompt", [
        "crud",
        "CRUD completo",
        "operações crud",
        "testar crud da api",
    ])
    def test_crud_variations_generate_crud_template(self, prompt: str):
        """Variações de 'crud' geram template CRUD."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate(prompt)

        plan = json.loads(response.content)

        # CRUD deve ter 4 steps
        assert len(plan["steps"]) == 4

        methods = {s["params"]["method"] for s in plan["steps"]}
        assert methods == {"POST", "GET", "PUT", "DELETE"}
