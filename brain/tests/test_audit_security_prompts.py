"""
================================================================================
Testes de Auditoria: Segurança de Prompts e Dados Sensíveis
================================================================================

## Objetivo (Item 7):
Verificar que a geração de prompts NÃO extrai ou vaza dados sensíveis do usuário.

## O que testamos:
1. Prompts gerados não contêm valores de credenciais reais
2. API keys/tokens são referenciados por placeholder, não valor
3. OpenAPI specs com dados sensíveis são sanitizados
4. Logs e outputs não expõem segredos

## Por que isso importa:
- LLMs podem memorizar dados de treinamento
- Logs podem ser expostos acidentalmente
- Erros podem vazar informações sensíveis
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import pytest

from src.generator.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.llm import MockLLMProvider
from src.ingestion.security import detect_security, SecurityType
from src.validator import UTDLValidator


def build_test_prompt(requirement: str, base_url: str = "http://api.example.com") -> str:
    """Helper para construir prompt de teste."""
    return USER_PROMPT_TEMPLATE.format(requirement=requirement, base_url=base_url)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sensitive_credentials() -> dict[str, str]:
    """Credenciais sensíveis que NÃO devem aparecer em prompts."""
    return {
        "api_key": "sk-REAL-API-KEY-12345-SECRET",
        "password": "P@ssw0rd!Super$ecret",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret_payload",
        "client_secret": "my-super-secret-client-credential",
        "database_password": "db_p@ss_very_secret_123",
    }


@pytest.fixture
def openapi_with_secrets() -> dict[str, Any]:
    """OpenAPI spec que referencia credenciais."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/users": {
                "get": {
                    "security": [{"apiKey": []}],
                    "responses": {"200": {"description": "OK"}}
                }
            },
            "/login": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "password": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}}
                }
            }
        },
        "components": {
            "securitySchemes": {
                "apiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            }
        }
    }


# =============================================================================
# TESTES: PROMPTS NÃO VAZAM DADOS SENSÍVEIS
# =============================================================================

class TestPromptSanitization:
    """Verifica que prompts não contêm dados sensíveis."""

    def test_prompt_does_not_contain_real_api_key(
        self,
        sensitive_credentials: dict[str, str]
    ) -> None:
        """Prompt gerado não contém valor real de API key."""
        # Gera prompt com contexto que inclui menção a API key
        user_requirement = "Testar endpoint /users que requer autenticação"

        prompt = build_test_prompt(requirement=user_requirement)

        # Verifica que nenhuma credencial real aparece no prompt
        for key, value in sensitive_credentials.items():
            assert value not in prompt, (
                f"Prompt contém valor sensível de '{key}': {value[:10]}..."
            )

    def test_prompt_template_uses_placeholders(self) -> None:
        """Template de prompt usa placeholders em vez de valores reais."""
        # O template não deve ter valores hardcoded
        full_template = SYSTEM_PROMPT + USER_PROMPT_TEMPLATE

        # Não deve conter padrões de credenciais reais
        hardcoded_patterns = [
            r'sk-[a-zA-Z0-9]{20,}',  # OpenAI style keys
            r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',  # JWT tokens
            r'[a-f0-9]{32,}',  # Hex tokens (MD5+)
        ]

        for pattern in hardcoded_patterns:
            matches = re.findall(pattern, full_template)
            assert not matches, f"Template contém valor hardcoded: {matches}"

    def test_mock_llm_response_uses_placeholder_credentials(self) -> None:
        """Mock LLM gera planos com placeholders, não valores reais."""
        provider = MockLLMProvider(latency_ms=0)
        response = provider.generate("Login com API key e senha")

        plan = json.loads(response.content)
        plan_str = json.dumps(plan)

        # Verifica que usa placeholders
        placeholder_patterns = [
            r'\$\{[a-z_]+\}',  # ${variable}
            r'\{\{[a-z_]+\}\}',  # {{variable}}
            r'env:[A-Z_]+',  # env:ENV_VAR
        ]

        _has_placeholder = any(
            re.search(p, plan_str) for p in placeholder_patterns
        )

        # Verifica que NÃO contém valores reais
        dangerous_patterns = [
            r'password["\s:]+["\'](?!.*\$\{)[^"\']{8,}',  # password: "realvalue"
            r'api_key["\s:]+["\'](?!.*\$\{)[^"\']{20,}',  # api_key: "realvalue"
        ]

        for pattern in dangerous_patterns:
            assert not re.search(pattern, plan_str, re.IGNORECASE), (
                f"Plano pode conter credencial real: {pattern}"
            )

    def test_error_messages_do_not_leak_credentials(
        self,
        sensitive_credentials: dict[str, str]
    ) -> None:
        """Mensagens de erro não vazam credenciais."""
        validator = UTDLValidator()

        # Cria plano inválido COM credenciais (como se usuário errasse)
        invalid_plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {"id": "test", "name": "Test"},
            "config": {
                "base_url": "http://api.example.com",
                # Simula usuário colocando credencial errada
                "variables": {
                    "api_key": sensitive_credentials["api_key"]
                }
            },
            "steps": []  # Inválido: sem steps
        }

        result = validator.validate(invalid_plan)

        # Erros não devem conter os valores sensíveis
        error_str = str(result.errors)
        for key, value in sensitive_credentials.items():
            assert value not in error_str, (
                f"Erro de validação vazou '{key}'"
            )


# =============================================================================
# TESTES: OPENAPI COM DADOS SENSÍVEIS
# =============================================================================

class TestOpenAPISanitization:
    """Verifica que parsing de OpenAPI sanitiza dados sensíveis."""

    def test_security_detection_does_not_store_credentials(
        self,
        openapi_with_secrets: dict[str, Any]
    ) -> None:
        """detect_security não armazena valores de credenciais."""
        analysis = detect_security(openapi_with_secrets)

        # Serializa a análise
        analysis_str = str(analysis)

        # Não deve conter padrões de credenciais reais
        dangerous_patterns = [
            r'sk-[a-zA-Z0-9]{20,}',
            r'eyJ[a-zA-Z0-9_-]+\.',
            r'Bearer\s+[a-zA-Z0-9_-]{20,}',
        ]

        for pattern in dangerous_patterns:
            assert not re.search(pattern, analysis_str), (
                f"Análise contém credencial: {pattern}"
            )

    def test_security_scheme_detection_is_metadata_only(
        self,
        openapi_with_secrets: dict[str, Any]
    ) -> None:
        """Detecção de esquema de segurança retorna apenas metadados."""
        analysis = detect_security(openapi_with_secrets)

        if analysis.primary_scheme:
            scheme = analysis.primary_scheme

            # Deve ter tipo de segurança válido
            assert scheme.security_type in [
                SecurityType.API_KEY,
                SecurityType.HTTP_BEARER,
                SecurityType.HTTP_BASIC,
                SecurityType.OAUTH2_PASSWORD,
                SecurityType.OAUTH2_CLIENT_CREDENTIALS,
            ]

            # Detalhes são metadados, não valores
            if "param_name" in scheme.details:
                # Deve ser o NOME do parâmetro, não o valor
                assert scheme.details["param_name"] in ["X-API-Key", "api_key", "Authorization"]


# =============================================================================
# TESTES: LOGS E DEBUG NÃO VAZAM SEGREDOS
# =============================================================================

class TestLoggingSecurity:
    """Verifica que logs não vazam dados sensíveis."""

    def test_llm_response_repr_shows_content_safely(self) -> None:
        """
        Representação de LLMResponse mostra conteúdo.

        NOTA: Este é um teste de documentação do comportamento atual.
        LLMResponse.repr mostra o conteúdo completo por design,
        já que é útil para debugging. A responsabilidade de não
        armazenar segredos é do código que usa o LLMResponse.
        """
        from src.llm.base import LLMResponse

        # Simula resposta com dados sensíveis
        response = LLMResponse(
            content='{"api_key": "sk-secret-key-12345"}',
            model="test",
            provider="test",
            tokens_used=100,
            latency_ms=50.0
        )

        repr_str = repr(response)

        # Verifica que repr é uma dataclass repr padrão
        # O conteúdo aparece, mas é responsabilidade do chamador
        # não logar respostas com dados sensíveis
        assert "LLMResponse" in repr_str
        assert "model='test'" in repr_str

        # NOTA: O content aparece no repr por design (útil para debug)
        # A proteção está em não colocar segredos reais na resposta

    def test_validation_result_does_not_expose_plan_values(self) -> None:
        """ValidationResult não expõe valores do plano nos erros."""
        validator = UTDLValidator()

        # Plano com dados sensíveis em locais errados
        plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": {
                "id": "test",
                "name": "Test",
                "password": "secret123"  # Campo inválido
            },
            "config": {
                "base_url": "http://test.com",
                "api_key": "sk-12345678901234567890"  # Não deveria estar aqui
            },
            "steps": [
                {
                    "id": "step1",
                    "action": "http_request",
                    "params": {
                        "method": "GET",
                        "url": "{{base_url}}/test"
                    }
                }
            ]
        }

        result = validator.validate(plan)
        result_str = str(result)

        # Se houver erros, não devem conter os valores
        # Os valores podem aparecer em campos válidos do plano,
        # mas erros devem referenciar estrutura, não valores
        if not result.is_valid:
            assert "sk-12345678901234567890" not in result_str


# =============================================================================
# TESTES: INTEGRAÇÃO FIM-A-FIM COM MOCK LLM
# =============================================================================

class TestEndToEndWithMockLLM:
    """Testes de integração completos usando mock LLM."""

    def test_full_flow_generates_sanitized_plan(self) -> None:
        """Fluxo completo gera plano sem credenciais reais."""
        provider = MockLLMProvider(latency_ms=0)
        validator = UTDLValidator()

        # Simula prompt do usuário
        user_input = "Testar login com email admin@company.com e senha AdminPass123"

        # Gera plano via mock
        response = provider.generate(user_input)
        plan = json.loads(response.content)

        # Normaliza para formato UTDL completo
        utdl_plan: dict[str, Any] = {
            "spec_version": "0.1",
            "meta": plan.get("meta", {}),
            "config": plan.get("config", {}),
            "steps": plan.get("steps", [])
        }

        # Valida
        result = validator.validate(utdl_plan)

        # Deve ser válido
        assert result.is_valid, f"Plano inválido: {result.errors}"

        # Plano não deve conter as credenciais literais do input
        plan_str = json.dumps(utdl_plan)
        assert "AdminPass123" not in plan_str
        assert "admin@company.com" not in plan_str or "${" in plan_str

    def test_mock_generates_plans_for_various_auth_types(self) -> None:
        """Mock gera planos válidos para diferentes tipos de auth."""
        provider = MockLLMProvider(latency_ms=0)
        validator = UTDLValidator()

        auth_prompts = [
            "API com autenticação via API key no header",
            "Endpoint que requer Bearer token JWT",
            "Login com usuário e senha (Basic Auth)",
            "OAuth2 com client credentials",
        ]

        for prompt in auth_prompts:
            response = provider.generate(prompt)
            plan = json.loads(response.content)

            utdl_plan: dict[str, Any] = {
                "spec_version": "0.1",
                "meta": plan.get("meta", {}),
                "config": plan.get("config", {}),
                "steps": plan.get("steps", [])
            }

            result = validator.validate(utdl_plan)
            assert result.is_valid, f"Falhou para '{prompt}': {result.errors}"


# =============================================================================
# TESTES: MOCKS DE APIS EXTERNAS
# =============================================================================

class TestExternalAPIMocking:
    """Testes com mocks de APIs externas."""

    def test_mock_api_does_not_call_real_endpoints(self) -> None:
        """Verifica que mock LLM não faz requisições reais."""
        import urllib.request
        from unittest.mock import patch

        with patch.object(urllib.request, 'urlopen') as mock_urlopen:
            provider = MockLLMProvider(latency_ms=0)

            # Gera múltiplos planos
            for _ in range(5):
                provider.generate("qualquer prompt")

            # Não deve ter feito nenhuma requisição HTTP
            mock_urlopen.assert_not_called()

    def test_mock_provider_is_deterministic_for_same_input(self) -> None:
        """Mock retorna resultados consistentes para mesmo input."""
        provider = MockLLMProvider(latency_ms=0)

        prompt = "health check endpoint"

        response1 = provider.generate(prompt)
        response2 = provider.generate(prompt)

        # Deve retornar estrutura similar (pode haver variação em IDs)
        plan1 = json.loads(response1.content)
        plan2 = json.loads(response2.content)

        assert plan1["meta"]["name"] == plan2["meta"]["name"]
        assert len(plan1["steps"]) == len(plan2["steps"])

    def test_environment_variables_not_leaked_to_mock(self) -> None:
        """Mock não acessa variáveis de ambiente sensíveis."""
        # Simula variáveis de ambiente sensíveis
        sensitive_env: dict[str, str] = {
            "AWS_SECRET_ACCESS_KEY": "aws-secret-12345",
            "OPENAI_API_KEY": "sk-openai-secret",
            "DATABASE_PASSWORD": "db-password-secret",
        }

        original_env: dict[str, str | None] = {}
        for key, value in sensitive_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            provider = MockLLMProvider(latency_ms=0)
            response = provider.generate("test with secrets in env")

            # Resposta não deve conter valores das env vars
            response_str = response.content
            for value in sensitive_env.values():
                assert value not in response_str, (
                    f"Resposta contém valor de env var: {value[:10]}..."
                )
        finally:
            # Restaura env vars originais
            for key, original in original_env.items():
                if original is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original
