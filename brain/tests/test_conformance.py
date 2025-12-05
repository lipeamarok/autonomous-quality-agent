"""
================================================================================
Testes de Conformidade Cross-Validation
================================================================================

Testes que geram planos aleatórios e validam em ambas as camadas:
- Python (Pydantic)
- Rust (Runner via subprocess)

Garante que mudanças em um lado não quebrem o outro.
"""

from __future__ import annotations

import json
import os
import random
import string
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.validator.models import (
    Plan,
    Meta,
    Config,
    Step,
    Assertion,
    Extraction,
    RecoveryPolicy,
)
from src.validator.utdl_validator import UTDLValidator


# =============================================================================
# GERADOR DE PLANOS ALEATÓRIOS
# =============================================================================


class RandomPlanGenerator:
    """Gera planos UTDL aleatórios para testes de conformidade."""
    
    HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    ASSERTION_TYPES = ["status_code", "json_body", "header", "latency"]
    ASSERTION_OPERATORS = ["eq", "neq", "lt", "gt", "contains"]
    EXTRACTION_SOURCES = ["body", "header", "status_code"]
    RECOVERY_STRATEGIES = ["retry", "fail_fast", "ignore"]
    
    def __init__(self, seed: int | None = None):
        """Inicializa com seed opcional para reprodutibilidade."""
        if seed is not None:
            random.seed(seed)
        self.step_counter = 0
    
    def random_string(self, length: int = 8) -> str:
        """Gera string aleatória."""
        return "".join(random.choices(string.ascii_lowercase, k=length))
    
    def random_id(self) -> str:
        """Gera ID de step válido."""
        self.step_counter += 1
        return f"step_{self.step_counter}_{self.random_string(4)}"
    
    def random_meta(self) -> dict[str, Any]:
        """Gera metadados aleatórios."""
        return {
            "id": str(uuid4()),
            "name": f"Test Plan {self.random_string()}",
            "description": f"Auto-generated test plan for conformance testing",
            "tags": [self.random_string(4) for _ in range(random.randint(0, 3))],
        }
    
    def random_config(self) -> dict[str, Any]:
        """Gera configuração aleatória."""
        return {
            "base_url": f"https://api.{self.random_string()}.com",
            "timeout_ms": random.choice([1000, 5000, 10000, 30000]),
            "global_headers": {
                "Content-Type": "application/json",
                "X-Test-Header": self.random_string(),
            },
            "variables": {
                "env": random.choice(["dev", "staging", "prod"]),
                "user_id": str(random.randint(1, 1000)),
            },
        }
    
    def random_http_params(self) -> dict[str, Any]:
        """Gera parâmetros HTTP aleatórios."""
        method = random.choice(self.HTTP_METHODS)
        params: dict[str, Any] = {
            "method": method,
            "path": f"/{self.random_string()}/{random.randint(1, 100)}",
        }
        
        # Headers opcionais
        if random.random() > 0.5:
            params["headers"] = {"X-Custom": self.random_string()}
        
        # Query params opcionais
        if random.random() > 0.7:
            params["query"] = {"page": str(random.randint(1, 10))}
        
        # Body para métodos que suportam
        if method in ["POST", "PUT", "PATCH"] and random.random() > 0.3:
            params["body"] = {
                "name": self.random_string(),
                "value": random.randint(1, 100),
            }
        
        return params
    
    def random_wait_params(self) -> dict[str, Any]:
        """Gera parâmetros de wait aleatórios."""
        return {"duration_ms": random.choice([100, 500, 1000, 2000])}
    
    def random_assertion(self) -> dict[str, Any]:
        """Gera assertion aleatória."""
        assertion_type = random.choice(self.ASSERTION_TYPES)
        operator = random.choice(self.ASSERTION_OPERATORS)
        
        assertion: dict[str, Any] = {
            "type": assertion_type,
            "operator": operator,
        }
        
        if assertion_type == "status_code":
            assertion["value"] = random.choice([200, 201, 204, 400, 404, 500])
        elif assertion_type == "json_body":
            assertion["path"] = f"$.{self.random_string()}"
            assertion["value"] = random.choice([True, False, self.random_string(), random.randint(1, 100)])
        elif assertion_type == "header":
            assertion["path"] = random.choice(["Content-Type", "X-Request-Id", "Cache-Control"])
            assertion["value"] = self.random_string()
        elif assertion_type == "latency":
            assertion["value"] = random.choice([100, 500, 1000, 5000])
        
        return assertion
    
    def random_extraction(self) -> dict[str, Any]:
        """Gera extraction aleatória."""
        source = random.choice(self.EXTRACTION_SOURCES)
        
        extraction: dict[str, Any] = {
            "source": source,
            "target": f"var_{self.random_string(4)}",
        }
        
        if source == "body":
            extraction["path"] = f"$.{self.random_string()}"
        elif source == "header":
            extraction["path"] = random.choice(["X-Request-Id", "Content-Type", "X-Custom"])
        # status_code não precisa de path
        
        if random.random() > 0.8:
            extraction["all_values"] = True
        
        if random.random() > 0.9:
            extraction["critical"] = True
        
        return extraction
    
    def random_recovery_policy(self) -> dict[str, Any] | None:
        """Gera recovery policy aleatória."""
        if random.random() > 0.5:
            return None
        
        return {
            "strategy": random.choice(self.RECOVERY_STRATEGIES),
            "max_attempts": random.randint(1, 5),
            "backoff_ms": random.choice([100, 500, 1000]),
            "backoff_factor": random.choice([1.5, 2.0, 3.0]),
        }
    
    def random_step(self, available_deps: list[str] | None = None) -> dict[str, Any]:
        """Gera step aleatório."""
        action = random.choice(["http_request", "http_request", "http_request", "wait"])
        
        step: dict[str, Any] = {
            "id": self.random_id(),
            "action": action,
        }
        
        # Descrição opcional
        if random.random() > 0.3:
            step["description"] = f"Test step: {self.random_string()}"
        
        # Dependências (de steps anteriores)
        if available_deps and random.random() > 0.5:
            num_deps = random.randint(1, min(2, len(available_deps)))
            step["depends_on"] = random.sample(available_deps, num_deps)
        
        # Params baseado na action
        if action == "http_request":
            step["params"] = self.random_http_params()
        else:
            step["params"] = self.random_wait_params()
        
        # Assertions para HTTP requests
        if action == "http_request" and random.random() > 0.3:
            num_assertions = random.randint(1, 3)
            step["assertions"] = [self.random_assertion() for _ in range(num_assertions)]
        
        # Extractions para HTTP requests
        if action == "http_request" and random.random() > 0.5:
            num_extractions = random.randint(1, 2)
            step["extract"] = [self.random_extraction() for _ in range(num_extractions)]
        
        # Recovery policy
        recovery = self.random_recovery_policy()
        if recovery:
            step["recovery_policy"] = recovery
        
        return step
    
    def generate_plan(self, num_steps: int = 5) -> dict[str, Any]:
        """Gera plano completo com N steps."""
        self.step_counter = 0
        
        steps: list[dict[str, Any]] = []
        step_ids: list[str] = []
        
        for _ in range(num_steps):
            step = self.random_step(available_deps=step_ids if step_ids else None)
            steps.append(step)
            step_ids.append(step["id"])
        
        return {
            "spec_version": "0.1",
            "meta": self.random_meta(),
            "config": self.random_config(),
            "steps": steps,
        }


# =============================================================================
# TESTES DE CONFORMIDADE
# =============================================================================


class TestSchemaConformance:
    """Testes de conformidade do schema UTDL."""
    
    def test_pydantic_schema_generation(self) -> None:
        """Schema Pydantic pode ser gerado."""
        from src.schema import generate_pydantic_schema
        
        schema = generate_pydantic_schema()
        
        assert "$schema" in schema
        assert "properties" in schema
        assert "spec_version" in schema["properties"]
    
    def test_canonical_schema_exists(self) -> None:
        """Schema canônico existe."""
        from src.schema import CANONICAL_SCHEMA_PATH
        
        assert CANONICAL_SCHEMA_PATH.exists(), f"Schema não encontrado: {CANONICAL_SCHEMA_PATH}"
    
    def test_canonical_schema_valid_json(self) -> None:
        """Schema canônico é JSON válido."""
        from src.schema import load_canonical_schema
        
        schema = load_canonical_schema()
        
        assert "$schema" in schema
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


class TestCrossValidation:
    """Testes de validação cruzada Python/Rust."""
    
    @pytest.fixture
    def generator(self) -> RandomPlanGenerator:
        """Gerador com seed fixa para reprodutibilidade."""
        return RandomPlanGenerator(seed=42)
    
    @pytest.fixture
    def runner_path(self) -> Path | None:
        """Caminho para o executável do Runner."""
        # Tenta encontrar o runner compilado
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "runner" / "target" / "release" / "runner.exe",
            Path(__file__).parent.parent.parent.parent / "runner" / "target" / "release" / "runner",
            Path(__file__).parent.parent.parent.parent / "runner" / "target" / "debug" / "runner.exe",
            Path(__file__).parent.parent.parent.parent / "runner" / "target" / "debug" / "runner",
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    def test_random_plan_validates_in_pydantic(self, generator: RandomPlanGenerator) -> None:
        """Planos aleatórios validam em Pydantic."""
        for _ in range(10):
            plan_dict = generator.generate_plan(num_steps=random.randint(1, 10))
            
            # Deve validar sem erros
            plan = Plan(**plan_dict)
            
            assert plan.spec_version == "0.1"
            assert len(plan.steps) > 0
    
    def test_random_plan_validates_in_utdl_validator(self, generator: RandomPlanGenerator) -> None:
        """Planos aleatórios passam no UTDLValidator."""
        validator = UTDLValidator(validate_limits=False)
        
        for _ in range(10):
            plan_dict = generator.generate_plan(num_steps=random.randint(1, 10))
            result = validator.validate(plan_dict)
            
            assert result.is_valid, f"Validation failed: {result.errors}"
    
    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip in CI - requires compiled runner"
    )
    def test_random_plan_validates_in_rust(
        self,
        generator: RandomPlanGenerator,
        runner_path: Path | None,
    ) -> None:
        """Planos aleatórios validam no Runner Rust."""
        if runner_path is None:
            pytest.skip("Runner não compilado")
        
        for _ in range(5):
            plan_dict = generator.generate_plan(num_steps=random.randint(1, 5))
            
            # Escreve plano em arquivo temporário
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                delete=False,
                encoding="utf-8",
            ) as f:
                json.dump(plan_dict, f)
                plan_path = f.name
            
            try:
                # Executa runner com --validate-only
                result = subprocess.run(
                    [str(runner_path), "--validate-only", plan_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                
                # Código 0 = válido, código 1 = erro de validação
                assert result.returncode == 0, f"Runner validation failed:\n{result.stderr}\nPlan: {json.dumps(plan_dict, indent=2)}"
            finally:
                os.unlink(plan_path)
    
    def test_cross_validation_pydantic_to_json_roundtrip(self, generator: RandomPlanGenerator) -> None:
        """Plano Pydantic -> JSON -> Pydantic mantém estrutura."""
        for _ in range(10):
            plan_dict = generator.generate_plan(num_steps=5)
            
            # Pydantic
            plan = Plan(**plan_dict)
            
            # Para JSON e volta
            json_str = plan.model_dump_json()
            plan_dict_2 = json.loads(json_str)
            plan_2 = Plan(**plan_dict_2)
            
            # Deve ser equivalente
            assert plan.spec_version == plan_2.spec_version
            assert plan.meta.name == plan_2.meta.name
            assert len(plan.steps) == len(plan_2.steps)
            
            for s1, s2 in zip(plan.steps, plan_2.steps):
                assert s1.id == s2.id
                assert s1.action == s2.action


class TestSpecificStructures:
    """Testes para estruturas específicas do schema."""
    
    def test_assertion_types(self) -> None:
        """Todos os tipos de assertion são suportados."""
        types = ["status_code", "json_body", "header", "latency"]
        
        for t in types:
            assertion = Assertion(
                type=t,  # type: ignore
                operator="eq",
                value=200 if t != "json_body" else "test",
                path="$.test" if t in ["json_body", "header"] else None,
            )
            assert assertion.type == t
    
    def test_extraction_sources(self) -> None:
        """Todas as fontes de extraction são suportadas."""
        sources = ["body", "header", "status_code"]
        
        for source in sources:
            extraction = Extraction(
                source=source,  # type: ignore
                target="var",
                path="$.test" if source in ["body", "header"] else None,
            )
            assert extraction.source == source
    
    def test_recovery_strategies(self) -> None:
        """Todas as estratégias de recovery são suportadas."""
        strategies = ["retry", "fail_fast", "ignore"]
        
        for strategy in strategies:
            policy = RecoveryPolicy(strategy=strategy)  # type: ignore
            assert policy.strategy == strategy
    
    def test_http_methods(self) -> None:
        """Todos os métodos HTTP são aceitos."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        
        for method in methods:
            step = Step(
                id="test",
                action="http_request",
                params={"method": method, "path": "/test"},
            )
            assert step.params["method"] == method


class TestEdgeCases:
    """Testes de casos limite."""
    
    def test_minimal_plan(self) -> None:
        """Plano mínimo válido."""
        plan = Plan(
            meta=Meta(name="Minimal"),
            config=Config(base_url="https://api.test.com"),
            steps=[
                Step(
                    id="only",
                    action="http_request",
                    params={"method": "GET", "path": "/"},
                )
            ],
        )
        
        assert plan.spec_version == "0.1"
        assert len(plan.steps) == 1
    
    def test_plan_with_all_optional_fields(self) -> None:
        """Plano com todos os campos opcionais preenchidos."""
        plan = Plan(
            meta=Meta(
                id="test-id",
                name="Full Plan",
                description="A complete plan",
                tags=["test", "full"],
            ),
            config=Config(
                base_url="https://api.test.com",
                timeout_ms=10000,
                global_headers={"X-Test": "value"},
                variables={"env": "test"},
            ),
            steps=[
                Step(
                    id="step1",
                    action="http_request",
                    description="First step",
                    params={
                        "method": "POST",
                        "path": "/test",
                        "headers": {"Custom": "header"},
                        "body": {"key": "value"},
                    },
                    assertions=[
                        Assertion(type="status_code", operator="eq", value=200),
                    ],
                    extract=[
                        Extraction(source="body", path="$.id", target="item_id"),
                    ],
                    recovery_policy=RecoveryPolicy(
                        strategy="retry",
                        max_attempts=3,
                        backoff_ms=1000,
                        backoff_factor=2.0,
                    ),
                ),
            ],
        )
        
        assert plan.meta.description == "A complete plan"
        assert len(plan.meta.tags) == 2
        assert plan.steps[0].recovery_policy is not None


class TestSchemaValidation:
    """Testes de validação contra schema JSON."""
    
    @pytest.fixture
    def generator(self) -> RandomPlanGenerator:
        return RandomPlanGenerator(seed=123)
    
    def test_validate_random_plan_against_schema(self, generator: RandomPlanGenerator) -> None:
        """Planos aleatórios validam contra schema canônico."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema não instalado")
        
        from src.schema import load_canonical_schema, get_schema_validation_errors
        
        schema = load_canonical_schema()
        validator = jsonschema.Draft7Validator(schema)
        
        for _ in range(10):
            plan = generator.generate_plan(num_steps=5)
            
            validation_errors = get_schema_validation_errors(validator, plan)
            assert len(validation_errors) == 0, f"Schema validation failed: {[e.message for e in validation_errors]}"
    
    def test_invalid_plan_fails_schema(self) -> None:
        """Plano inválido falha na validação de schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema não instalado")
        
        from src.schema import load_canonical_schema, get_schema_validation_errors
        
        schema = load_canonical_schema()
        validator = jsonschema.Draft7Validator(schema)
        
        invalid_plan: dict[str, Any] = {
            "spec_version": "0.1",
            # Faltando meta
            "config": {"base_url": "https://test.com"},
            "steps": [],  # Vazio
        }
        
        validation_errors = get_schema_validation_errors(validator, invalid_plan)
        assert len(validation_errors) > 0
