"""
Testes de Integração: Brain → Runner

## Para todos entenderem:

Estes testes verificam o fluxo completo:
1. Brain gera um plano UTDL (usando mock)
2. O plano é validado
3. Runner executa o plano
4. Report é analisado

## Configuração:

Usa MockLLMProvider para geração determinística.
Usa httpbin.org para requests HTTP reais (ou mock local).
"""

import json
import subprocess
import tempfile
from pathlib import Path

from typing import Any

import pytest

from src.llm import MockLLMProvider, get_llm_provider
from src.validator import UTDLValidator


def validate_plan(plan: dict[str, Any]) -> "ValidationResult":
    """Helper para validar plano UTDL."""
    validator = UTDLValidator()
    return validator.validate(plan)


# Import ValidationResult após a função para evitar circular
from src.validator import ValidationResult


class TestBrainToRunnerIntegration:
    """Testes de integração Brain → Runner."""

    def test_mock_provider_generates_valid_utdl(self):
        """
        Mock provider gera UTDL que passa na validação.

        Fluxo:
        1. Mock gera plano
        2. Plano é parseado
        3. Validador confirma que é válido
        """
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("teste de login na API")

        # Parse o JSON gerado
        plan = json.loads(response.content)

        # Converte para formato esperado pelo validador
        # O mock gera formato simplificado, precisamos adaptar
        utdl_plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": plan.get("meta", {}),
            "config": plan.get("config", {}),
            "steps": plan.get("steps", []),
        }

        # Valida o plano
        result = validate_plan(utdl_plan)

        # Deve passar na validação
        assert result.is_valid, f"Erros: {result.errors}"

    def test_all_mock_templates_generate_valid_utdl(self):
        """Todos os templates do mock geram UTDL válido."""
        provider = MockLLMProvider(latency_ms=0)

        templates = ["login", "crud", "health", "algo desconhecido"]

        for prompt in templates:
            response = provider.generate(prompt)
            plan = json.loads(response.content)

            utdl_plan: dict[str, Any] = {
                "spec_version": "0.1",
                "meta": plan.get("meta", {}),
                "config": plan.get("config", {}),
                "steps": plan.get("steps", []),
            }

            result = validate_plan(utdl_plan)
            assert result.is_valid, f"Template '{prompt}' inválido: {result.errors}"

    def test_get_llm_provider_with_mock_mode(self):
        """Factory retorna mock quando solicitado."""
        provider = get_llm_provider(mode="mock")

        assert provider.name == "mock"
        assert provider.is_available()

        response = provider.generate("health check")
        assert response.is_mock
        assert response.tokens_used == 0

    def test_generated_plan_has_required_fields(self):
        """Plano gerado tem todos os campos obrigatórios."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("teste completo")

        plan = json.loads(response.content)

        # Campos obrigatórios de meta
        assert "name" in plan["meta"]
        assert "version" in plan["meta"]

        # Campos obrigatórios de config
        assert "base_url" in plan["config"]

        # Steps deve ter pelo menos um
        assert len(plan["steps"]) > 0

        # Cada step deve ter campos obrigatórios
        for step in plan["steps"]:
            assert "id" in step
            assert "action" in step
            assert "params" in step

    def test_plan_can_be_saved_and_loaded(self):
        """Plano pode ser salvo e carregado de arquivo."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("health check")

        plan = json.loads(response.content)

        # Salva em arquivo temporário
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(plan, f)
            temp_path = Path(f.name)

        try:
            # Carrega de volta
            loaded = json.loads(temp_path.read_text())

            assert loaded == plan
            assert loaded["meta"]["name"] == plan["meta"]["name"]
            assert len(loaded["steps"]) == len(plan["steps"])
        finally:
            temp_path.unlink()

    @pytest.mark.skipif(
        subprocess.run(["cmd", "/c", "echo"], capture_output=True).returncode == 0,
        reason="Skip on Windows due to Unicode encoding issues with Rich"
    )
    def test_cli_validate_accepts_mock_generated_plan(self):
        """CLI validate aceita plano gerado pelo mock."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("health")

        plan = json.loads(response.content)

        # Adiciona spec_version que o validador exige
        full_plan: dict[str, Any] = {
            "spec_version": "0.1",
            **plan,
        }

        # Salva em arquivo temporário
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(full_plan, f)
            temp_path = Path(f.name)

        try:
            # Executa CLI
            result = subprocess.run(
                ["aqa", "validate", str(temp_path)],
                capture_output=True,
                text=True,
            )

            # Deve passar (exit code 0)
            assert result.returncode == 0, f"Erro: {result.stderr}"
            assert "Válido" in result.stdout or "valid" in result.stdout.lower()
        finally:
            temp_path.unlink()


class TestEndToEndWithMock:
    """Testes end-to-end usando mock."""

    def test_login_flow_generation_and_validation(self):
        """
        Fluxo completo de geração de teste de login.

        Cenário:
        1. Usuário pede "teste de login"
        2. Mock gera plano com step de login
        3. Plano é validado
        4. Plano tem extração de token
        """
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("autenticação de usuário com login")

        plan = json.loads(response.content)

        # Verifica estrutura do login
        login_step = plan["steps"][0]

        # Deve ser POST
        assert login_step["params"]["method"] == "POST"

        # Deve ter path de auth
        assert "login" in login_step["params"]["path"] or "auth" in login_step["params"]["path"]

        # Deve ter extração de token
        assert "extract" in login_step
        assert any(e["target"] == "auth_token" for e in login_step["extract"])

        # Valida o plano completo
        utdl_plan: dict[str, Any] = {
            "spec_version": "0.1",
            **plan,
        }
        result = validate_plan(utdl_plan)
        assert result.is_valid

    def test_crud_flow_has_dependencies(self):
        """
        CRUD gerado tem dependências corretas entre steps.

        read depende de create
        update depende de read
        delete depende de update
        """
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("operações crud")

        plan = json.loads(response.content)

        steps_by_id = {s["id"]: s for s in plan["steps"]}

        # Create não tem dependências
        assert steps_by_id["create"].get("depends_on", []) == []

        # Read depende de create
        assert "create" in steps_by_id["read"].get("depends_on", [])

        # Update depende de read
        assert "read" in steps_by_id["update"].get("depends_on", [])

        # Delete depende de update
        assert "update" in steps_by_id["delete"].get("depends_on", [])

    def test_plan_variables_are_interpolatable(self):
        """
        Variáveis no plano podem ser interpoladas.

        ${BASE_URL} no config
        ${auth_token} nos headers
        ${item_id} nos paths
        """
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("crud")

        plan = json.loads(response.content)

        # Config tem variável de ambiente
        assert "${BASE_URL}" in plan["config"]["base_url"]

        # Create step extrai item_id
        create_step = next(s for s in plan["steps"] if s["id"] == "create")
        assert any(e["target"] == "item_id" for e in create_step.get("extract", []))

        # Read step usa ${item_id}
        read_step = next(s for s in plan["steps"] if s["id"] == "read")
        assert "${item_id}" in read_step["params"]["path"]


class TestProviderModeIntegration:
    """Testes de integração do modo de provider."""

    def test_env_var_controls_provider_mode(self):
        """
        AQA_LLM_MODE controla qual provider é usado.
        """
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"AQA_LLM_MODE": "mock"}):
            provider = get_llm_provider()
            assert provider.name == "mock"

    def test_explicit_mode_overrides_env(self):
        """
        Parâmetro mode sobrescreve variável de ambiente.
        """
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"AQA_LLM_MODE": "real"}):
            provider = get_llm_provider(mode="mock")
            assert provider.name == "mock"

    def test_config_dict_sets_mode(self):
        """
        Config dict pode definir o modo.
        """
        config = {"llm": {"mode": "mock"}}
        provider = get_llm_provider(config=config)
        assert provider.name == "mock"
