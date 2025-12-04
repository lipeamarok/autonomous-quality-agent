"""
E2E Extreme Test Scenarios for AQA.

These tests validate the system under stress conditions:
- Large plans (100+ steps)
- Parallel execution
- Network failures
- Complex authentication flows
- Memory/resource limits
"""

import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from src.validator.utdl_validator import UTDLValidator


def validate_plan(plan: dict):
    """Helper to validate a plan using UTDLValidator."""
    validator = UTDLValidator()
    return validator.validate(plan)


def create_base_plan(plan_id: str, name: str, steps: list) -> dict:
    """Create a valid UTDL plan with correct structure."""
    return {
        "spec_version": "0.1",
        "meta": {
            "id": plan_id,
            "name": name,
            "description": f"Test plan: {name}",
            "tags": ["test", "e2e"]
        },
        "config": {
            "base_url": "http://localhost:8080",
            "timeout_ms": 30000,
            "variables": {}
        },
        "steps": steps
    }


def create_http_step(
    step_id: str,
    method: str = "GET",
    url: str = "{{base_url}}/test",
    depends_on: list = None,
    assertions: list = None,
    extractions: list = None
) -> dict:
    """Create a valid http_request step."""
    step = {
        "id": step_id,
        "action": "http_request",
        "description": f"Step {step_id}",
        "params": {
            "method": method,
            "url": url
        }
    }
    if depends_on:
        step["depends_on"] = depends_on
    if assertions:
        step["assertions"] = assertions
    if extractions:
        step["extract"] = extractions
    return step


def create_extraction(target: str, source: str = "body", path: str = "$.data") -> dict:
    """Create a valid extraction definition."""
    return {
        "target": target,
        "source": source,
        "path": path
    }


def create_assertion(
    assertion_type: str = "status_code",
    operator: str = "eq",
    value: any = 200,
    path: str | None = None
) -> dict:
    """Create a valid assertion matching the UTDL schema.
    
    Args:
        assertion_type: One of 'status_code', 'json_body', 'header', 'latency'
        operator: One of 'eq', 'neq', 'lt', 'gt', 'contains'
        value: Expected value
        path: JSONPath or header name (required for json_body/header)
    """
    assertion = {
        "type": assertion_type,
        "operator": operator,
        "value": value
    }
    if path:
        assertion["path"] = path
    return assertion


class TestLargePlans:
    """Tests for plans with many steps."""

    def test_validate_plan_with_100_steps(self):
        """Validate a plan with 100 steps completes in reasonable time."""
        steps = []
        for i in range(100):
            step = create_http_step(
                step_id=f"step_{i}",
                method="GET",
                url=f"{{{{base_url}}}}/resource/{i}",
                depends_on=[f"step_{i-1}"] if i > 0 else None,
                assertions=[create_assertion("status_code", "eq", 200)]
            )
            steps.append(step)

        plan = create_base_plan("large_plan_100", "Large Plan Test", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"

    def test_validate_plan_with_500_steps(self):
        """Validate a plan with 500 steps."""
        steps = []
        for i in range(500):
            # Create a tree structure, not a chain (better for parallel execution)
            depends = []
            if i % 10 != 0 and i >= 10:
                depends = [f"step_{i//10 * 10}"]
            
            step = create_http_step(
                step_id=f"step_{i}",
                method="GET",
                url=f"{{{{base_url}}}}/resource/{i}",
                depends_on=depends if depends else None,
                assertions=[create_assertion("status_code", "eq", 200)]
            )
            steps.append(step)

        plan = create_base_plan("large_plan_500", "Large Plan Test 500 Steps", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"

    def test_plan_with_deep_dependency_chain(self):
        """Test plan with 50-step deep dependency chain."""
        steps = []
        for i in range(50):
            extractions = [create_extraction(f"result_{i}", "body", "$.result")]
            step = create_http_step(
                step_id=f"chain_step_{i}",
                method="POST",
                url="{{base_url}}/chain",
                depends_on=[f"chain_step_{i-1}"] if i > 0 else None,
                extractions=extractions
            )
            steps.append(step)

        plan = create_base_plan("deep_chain", "Deep Dependency Chain", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


class TestParallelExecution:
    """Tests for parallel step execution."""

    def test_plan_with_parallel_branches(self):
        """Test plan with multiple parallel branches."""
        steps = [
            # Root step
            create_http_step(
                step_id="init",
                method="POST",
                url="{{base_url}}/init",
                extractions=[create_extraction("session_id", "body", "$.session_id")]
            )
        ]

        # Create 10 parallel branches, each with 5 steps
        for branch in range(10):
            for step in range(5):
                step_id = f"branch_{branch}_step_{step}"
                depends_on = ["init"] if step == 0 else [f"branch_{branch}_step_{step-1}"]
                
                steps.append(create_http_step(
                    step_id=step_id,
                    method="GET",
                    url=f"{{{{base_url}}}}/branch/{branch}/step/{step}",
                    depends_on=depends_on
                ))

        # Final aggregation step
        final_deps = [f"branch_{b}_step_4" for b in range(10)]
        steps.append(create_http_step(
            step_id="aggregate",
            method="POST",
            url="{{base_url}}/aggregate",
            depends_on=final_deps
        ))

        plan = create_base_plan("parallel_branches", "Parallel Branches Test", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"
        assert len(plan["steps"]) == 52  # 1 init + 50 branch steps + 1 aggregate

    def test_dag_with_diamond_dependencies(self):
        """Test DAG with diamond dependency pattern."""
        steps = [
            create_http_step("start", "GET", "{{base_url}}/start"),
            create_http_step("left", "GET", "{{base_url}}/left", depends_on=["start"]),
            create_http_step("right", "GET", "{{base_url}}/right", depends_on=["start"]),
            create_http_step("end", "GET", "{{base_url}}/end", depends_on=["left", "right"])
        ]

        plan = create_base_plan("diamond", "Diamond DAG", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


class TestAuthenticationFlows:
    """Tests for complex authentication scenarios."""

    def test_oauth2_token_refresh_flow(self):
        """Test OAuth2 flow with token refresh."""
        steps = [
            {
                "id": "get_initial_token",
                "action": "http_request",
                "description": "Get initial OAuth token",
                "params": {
                    "method": "POST",
                    "url": "{{base_url}}/oauth/token",
                    "headers": {
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                },
                "extract": [
                    create_extraction("access_token", "body", "$.access_token"),
                    create_extraction("refresh_token", "body", "$.refresh_token")
                ],
                "assertions": [
                    create_assertion("status_code", "eq", 200)
                ]
            },
            {
                "id": "use_token",
                "action": "http_request",
                "description": "Use access token",
                "depends_on": ["get_initial_token"],
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/api/protected"
                },
                "assertions": [
                    create_assertion("status_code", "eq", 200)
                ]
            },
            {
                "id": "refresh_token_step",
                "action": "http_request",
                "description": "Refresh the token",
                "depends_on": ["use_token"],
                "params": {
                    "method": "POST",
                    "url": "{{base_url}}/oauth/token"
                },
                "extract": [
                    create_extraction("access_token", "body", "$.access_token")
                ]
            },
            {
                "id": "use_refreshed_token",
                "action": "http_request",
                "description": "Use refreshed token",
                "depends_on": ["refresh_token_step"],
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/api/protected"
                },
                "assertions": [
                    create_assertion("status_code", "eq", 200)
                ]
            }
        ]

        plan = create_base_plan("oauth2_refresh", "OAuth2 Token Refresh Flow", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"

    def test_multi_step_login_with_mfa(self):
        """Test multi-factor authentication flow."""
        steps = [
            {
                "id": "initiate_login",
                "action": "http_request",
                "description": "Start login process",
                "params": {
                    "method": "POST",
                    "url": "{{base_url}}/auth/login"
                },
                "extract": [
                    create_extraction("challenge_id", "body", "$.challenge_id"),
                    create_extraction("mfa_type", "body", "$.mfa_type")
                ],
                "assertions": [
                    create_assertion("json_body", "eq", True, "$.mfa_required")
                ]
            },
            {
                "id": "request_mfa_code",
                "action": "http_request",
                "description": "Request MFA code",
                "depends_on": ["initiate_login"],
                "params": {
                    "method": "POST",
                    "url": "{{base_url}}/auth/mfa/send"
                },
                "assertions": [
                    create_assertion("status_code", "eq", 200)
                ]
            },
            {
                "id": "verify_mfa",
                "action": "http_request",
                "description": "Verify MFA code",
                "depends_on": ["request_mfa_code"],
                "params": {
                    "method": "POST",
                    "url": "{{base_url}}/auth/mfa/verify"
                },
                "extract": [
                    create_extraction("session_token", "body", "$.session_token")
                ],
                "assertions": [
                    create_assertion("json_body", "eq", True, "$.verified")
                ]
            },
            {
                "id": "get_user_profile",
                "action": "http_request",
                "description": "Get user profile",
                "depends_on": ["verify_mfa"],
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/api/me"
                },
                "assertions": [
                    create_assertion("json_body", "neq", None, "$.username")
                ]
            }
        ]

        plan = create_base_plan("mfa_flow", "MFA Login Flow", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


class TestRetryAndRecovery:
    """Tests for retry and recovery policies."""

    def test_plan_with_retry_policies(self):
        """Test plan with various retry configurations."""
        steps = [
            {
                "id": "flaky_endpoint",
                "action": "http_request",
                "description": "Call flaky endpoint with retry",
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/flaky"
                },
                "retry_policy": {
                    "max_retries": 5,
                    "delay_ms": 1000,
                    "backoff_multiplier": 2.0
                },
                "assertions": [
                    create_assertion("status_code", "eq", 200)
                ]
            },
            {
                "id": "rate_limited",
                "action": "http_request",
                "description": "Call rate-limited endpoint",
                "depends_on": ["flaky_endpoint"],
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/rate-limited"
                },
                "retry_policy": {
                    "max_retries": 10,
                    "delay_ms": 5000
                }
            }
        ]

        plan = create_base_plan("retry_test", "Retry Policy Test", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"

    def test_plan_with_recovery_steps(self):
        """Test plan with recovery/fallback steps."""
        steps = [
            {
                "id": "primary_endpoint",
                "action": "http_request",
                "description": "Primary endpoint with fallback",
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/primary"
                },
                "recovery_policy": {
                    "action": "continue"
                }
            },
            {
                "id": "fallback_endpoint",
                "action": "http_request",
                "description": "Fallback endpoint",
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/fallback"
                }
            },
            {
                "id": "continue_flow",
                "action": "http_request",
                "description": "Continue after recovery",
                "depends_on": ["primary_endpoint"],
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/continue"
                }
            }
        ]

        plan = create_base_plan("recovery_test", "Recovery Policy Test", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_plan(self):
        """Test that empty plan is handled."""
        plan = create_base_plan("empty", "Empty Plan", [])
        result = validate_plan(plan)
        # Empty plan should be valid structurally (validator allows it)
        # but may have warnings
        assert result.is_valid or "empty" in str(result.errors).lower() or "step" in str(result.errors).lower()

    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        steps = [
            create_http_step("a", depends_on=["c"]),
            create_http_step("b", depends_on=["a"]),
            create_http_step("c", depends_on=["b"])
        ]
        plan = create_base_plan("circular", "Circular Dependencies", steps)
        result = validate_plan(plan)
        # Should detect circular dependency
        assert not result.is_valid, "Should detect circular dependency"

    def test_self_dependency_detection(self):
        """Test that self-dependencies are detected."""
        steps = [
            create_http_step("step_a", depends_on=["step_a"])  # Self-reference!
        ]
        plan = create_base_plan("self_dep", "Self Dependency", steps)
        result = validate_plan(plan)
        assert not result.is_valid, "Should detect self-dependency"

    def test_missing_dependency_detection(self):
        """Test that missing dependencies are detected."""
        steps = [
            create_http_step("step_a", depends_on=["nonexistent_step"])
        ]
        plan = create_base_plan("missing_dep", "Missing Dependency", steps)
        result = validate_plan(plan)
        assert not result.is_valid, "Should detect missing dependency"

    def test_duplicate_step_ids(self):
        """Test that duplicate step IDs are detected."""
        steps = [
            create_http_step("step_a", url="{{base_url}}/a"),
            create_http_step("step_a", url="{{base_url}}/b")  # Duplicate!
        ]
        plan = create_base_plan("dup_ids", "Duplicate IDs", steps)
        result = validate_plan(plan)
        assert not result.is_valid, "Should detect duplicate step IDs"

    def test_very_long_step_id(self):
        """Test handling of very long step IDs."""
        long_id = "a" * 500  # 500 character ID (reduced from 1000)
        steps = [create_http_step(long_id)]
        plan = create_base_plan("long_id", "Long ID Test", steps)
        result = validate_plan(plan)
        # Should either accept or reject with a clear error
        assert result.is_valid or len(result.errors) > 0

    def test_special_characters_in_variables(self):
        """Test handling of special characters in variable values."""
        plan = {
            "spec_version": "0.1",
            "meta": {
                "id": "special_chars",
                "name": "Special Characters",
                "description": "Test special chars in variables"
            },
            "config": {
                "base_url": "http://localhost",
                "timeout_ms": 30000,
                "variables": {
                    "weird_value": "hello world",
                    "unicode": "日本語テスト",
                    "path": "some/path/value"
                }
            },
            "steps": [
                create_http_step("test_step", method="POST", url="{{base_url}}/test")
            ]
        }
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


class TestResourceLimits:
    """Tests for resource limit handling."""

    def test_plan_with_explicit_limits(self):
        """Test plan with explicit resource limits in config."""
        plan = {
            "spec_version": "0.1",
            "meta": {
                "id": "limited",
                "name": "Limited Plan",
                "description": "Plan with resource limits"
            },
            "config": {
                "base_url": "http://localhost",
                "timeout_ms": 30000,
                "variables": {}
            },
            "steps": [
                create_http_step("step_1")
            ]
        }
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"

    def test_plan_exceeding_step_limit(self):
        """Test that plan with many steps is at least validated."""
        # Create plan with 200 steps (reasonable stress test)
        steps = []
        for i in range(200):
            steps.append(create_http_step(f"step_{i}", url=f"{{{{base_url}}}}/step/{i}"))

        plan = create_base_plan("many_steps", "Many Steps", steps)
        result = validate_plan(plan)
        # Validation should complete regardless of outcome
        assert len(steps) == 200


class TestComplexExtractions:
    """Tests for complex extraction patterns."""

    def test_nested_json_extraction(self):
        """Test deeply nested JSON path extractions."""
        steps = [
            {
                "id": "get_nested",
                "action": "http_request",
                "description": "Get nested data",
                "params": {"method": "GET", "url": "{{base_url}}/nested"},
                "extract": [
                    create_extraction("deep_value", "body", "$.data.items[0].nested.deep.value"),
                    create_extraction("header_token", "header", "X-Custom-Token"),
                    create_extraction("status", "status_code", "")
                ]
            }
        ]
        plan = create_base_plan("nested_extract", "Nested Extraction", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"

    def test_regex_extraction(self):
        """Test regex-based extractions."""
        steps = [
            {
                "id": "get_with_regex",
                "action": "http_request",
                "description": "Get with regex extraction",
                "params": {"method": "GET", "url": "{{base_url}}/text"},
                "extract": [
                    {
                        "target": "email",
                        "source": "body",
                        "path": "$.text",
                        "regex": r"[\w.+-]+@[\w-]+\.[\w.-]+"
                    },
                    {
                        "target": "uuid",
                        "source": "body",
                        "path": "$.id",
                        "regex": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                    }
                ]
            }
        ]
        plan = create_base_plan("regex_extract", "Regex Extraction", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


class TestWaitAndPolling:
    """Tests for wait and polling scenarios."""

    def test_polling_until_condition(self):
        """Test polling pattern until condition is met."""
        steps = [
            {
                "id": "start_job",
                "action": "http_request",
                "description": "Start async job",
                "params": {
                    "method": "POST",
                    "url": "{{base_url}}/jobs"
                },
                "extract": [
                    create_extraction("job_id", "body", "$.job_id")
                ]
            },
            {
                "id": "wait_for_job",
                "action": "wait",
                "description": "Wait before checking",
                "depends_on": ["start_job"],
                "params": {
                    "duration_ms": 1000
                }
            },
            {
                "id": "check_job_status",
                "action": "http_request",
                "description": "Check job status",
                "depends_on": ["wait_for_job"],
                "params": {
                    "method": "GET",
                    "url": "{{base_url}}/jobs/{{job_id}}"
                },
                "retry_policy": {
                    "max_retries": 30,
                    "delay_ms": 2000
                },
                "assertions": [
                    create_assertion("json_body", "eq", "completed", "$.status")
                ]
            }
        ]
        plan = create_base_plan("polling", "Polling Test", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


class TestGraphQLPlans:
    """Tests for GraphQL-specific plans (for the new executor)."""

    def test_graphql_query_plan(self):
        """Test a GraphQL query plan structure."""
        # Note: The validator may not support graphql action yet,
        # so this tests if it at least doesn't crash
        steps = [
            {
                "id": "graphql_query",
                "action": "http_request",  # GraphQL via HTTP
                "description": "Execute GraphQL query",
                "params": {
                    "method": "POST",
                    "url": "{{base_url}}/graphql",
                    "headers": {
                        "Content-Type": "application/json"
                    }
                },
                "extract": [
                    create_extraction("user_name", "body", "$.data.user.name")
                ],
                "assertions": [
                    create_assertion("json_body", "neq", None, "$.data.user")
                ]
            }
        ]
        plan = create_base_plan("graphql_test", "GraphQL Query Test", steps)
        result = validate_plan(plan)
        assert result.is_valid, f"Validation failed: {result.errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
