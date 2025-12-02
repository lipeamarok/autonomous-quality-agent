use async_trait::async_trait;
use crate::protocol::{Step, StepResult, StepStatus, Assertion, Extraction};
use crate::context::Context;
use super::StepExecutor;
use anyhow::{Result, anyhow};
use std::time::Instant;
use reqwest::{Client, Method, header::HeaderMap};
use serde_json::Value;

/// Compara dois valores JSON numéricos usando uma função de comparação.
fn compare_values<F>(actual: &Value, expected: &Value, cmp: F) -> bool
where
    F: Fn(f64, f64) -> bool,
{
    match (actual, expected) {
        (Value::Number(a), Value::Number(b)) => {
            if let (Some(a_f), Some(b_f)) = (a.as_f64(), b.as_f64()) {
                cmp(a_f, b_f)
            } else {
                false
            }
        }
        _ => false,
    }
}

/// Contexto de uma resposta HTTP para validação de assertions.
struct ResponseContext<'a> {
    status: u16,
    body: &'a Value,
    headers: &'a HeaderMap,
    duration_ms: u64,
}

/// Executor responsible for handling "http_request" actions.
pub struct HttpExecutor {
    client: Client,
}

impl HttpExecutor {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
        }
    }

    fn validate_assertions(&self, assertions: &[Assertion], ctx: &ResponseContext) -> Option<String> {
        for assertion in assertions {
            match assertion.assertion_type.as_str() {
                "status_code" => {
                    let expected = assertion.value.as_u64().unwrap_or(0) as u16;
                    let passed = match assertion.operator.as_str() {
                        "eq" => ctx.status == expected,
                        "neq" => ctx.status != expected,
                        "lt" => ctx.status < expected,
                        "gt" => ctx.status > expected,
                        "lte" | "le" => ctx.status <= expected,
                        "gte" | "ge" => ctx.status >= expected,
                        _ => false,
                    };
                    if !passed {
                        return Some(format!(
                            "Assertion failed: status_code {} {} (got {})",
                            assertion.operator, expected, ctx.status
                        ));
                    }
                }
                "json_body" => {
                    if let Some(path) = &assertion.path {
                        let pointer = if path.starts_with('/') {
                            path.clone()
                        } else {
                            format!("/{}", path.replace('.', "/"))
                        };

                        if let Some(actual) = ctx.body.pointer(&pointer) {
                            let passed = match assertion.operator.as_str() {
                                "eq" => actual == &assertion.value,
                                "neq" => actual != &assertion.value,
                                "contains" => actual.as_str().map(|s| {
                                    assertion.value.as_str().map(|needle| s.contains(needle)).unwrap_or(false)
                                }).unwrap_or(false),
                                "exists" => true, // Se chegou aqui, existe
                                "not_exists" => false, // Se chegou aqui, existe, então falha
                                "gt" => compare_values(actual, &assertion.value, |a, b| a > b),
                                "lt" => compare_values(actual, &assertion.value, |a, b| a < b),
                                "gte" | "ge" => compare_values(actual, &assertion.value, |a, b| a >= b),
                                "lte" | "le" => compare_values(actual, &assertion.value, |a, b| a <= b),
                                _ => false,
                            };

                            if !passed {
                                return Some(format!(
                                    "Assertion failed: json_body '{}' {} {} (got {})",
                                    path, assertion.operator, assertion.value, actual
                                ));
                            }
                        } else {
                            // Path não existe
                            if assertion.operator == "not_exists" {
                                continue; // OK, não existe como esperado
                            }
                            if assertion.operator == "exists" {
                                return Some(format!("Assertion failed: path '{}' should exist but was not found", path));
                            }
                            return Some(format!("Assertion failed: path '{}' not found in response body", path));
                        }
                    }
                }
                "header" => {
                    if let Some(header_name) = &assertion.path {
                        let header_value = ctx.headers.get(header_name)
                            .and_then(|v| v.to_str().ok());

                        match assertion.operator.as_str() {
                            "exists" => {
                                if header_value.is_none() {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should exist",
                                        header_name
                                    ));
                                }
                            }
                            "not_exists" => {
                                if header_value.is_some() {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should not exist",
                                        header_name
                                    ));
                                }
                            }
                            "eq" => {
                                let expected = assertion.value.as_str().unwrap_or("");
                                if header_value != Some(expected) {
                                    return Some(format!(
                                        "Assertion failed: header '{}' {} '{}' (got '{}')",
                                        header_name, assertion.operator, expected,
                                        header_value.unwrap_or("<missing>")
                                    ));
                                }
                            }
                            "neq" => {
                                let expected = assertion.value.as_str().unwrap_or("");
                                if header_value == Some(expected) {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should not equal '{}'",
                                        header_name, expected
                                    ));
                                }
                            }
                            "contains" => {
                                let needle = assertion.value.as_str().unwrap_or("");
                                let contains = header_value.map(|v| v.contains(needle)).unwrap_or(false);
                                if !contains {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should contain '{}' (got '{}')",
                                        header_name, needle, header_value.unwrap_or("<missing>")
                                    ));
                                }
                            }
                            _ => {}
                        }
                    }
                }
                "latency" => {
                    let expected = assertion.value.as_u64().unwrap_or(0);
                    let passed = match assertion.operator.as_str() {
                        "lt" => ctx.duration_ms < expected,
                        "lte" | "le" => ctx.duration_ms <= expected,
                        "gt" => ctx.duration_ms > expected,
                        "gte" | "ge" => ctx.duration_ms >= expected,
                        "eq" => ctx.duration_ms == expected,
                        _ => false,
                    };
                    if !passed {
                        return Some(format!(
                            "Assertion failed: latency {} {}ms (got {}ms)",
                            assertion.operator, expected, ctx.duration_ms
                        ));
                    }
                }
                _ => {
                    tracing::warn!(assertion_type = %assertion.assertion_type, "Unknown assertion type, skipping");
                }
            }
        }
        None
    }

    fn apply_extractions(
        &self,
        extracts: &[Extraction],
        body: &Value,
        headers: &HeaderMap,
        context: &mut Context,
    ) {
        for rule in extracts {
            match rule.source.as_str() {
                "body" => {
                    let pointer = if rule.path.starts_with('/') {
                        rule.path.clone()
                    } else {
                        format!("/{}", rule.path.replace('.', "/"))
                    };

                    if let Some(val) = body.pointer(&pointer) {
                        context.set(rule.target.clone(), val.clone());
                    }
                }
                "header" => {
                    if let Some(val) = headers.get(&rule.path) {
                        if let Ok(str_val) = val.to_str() {
                            context.set(rule.target.clone(), Value::String(str_val.to_string()));
                        }
                    }
                }
                _ => {}
            }
        }
    }
}

#[async_trait]
impl StepExecutor for HttpExecutor {
    fn can_handle(&self, action: &str) -> bool {
        action == "http_request"
    }

    #[tracing::instrument(
        name = "http_request",
        skip_all,
        fields(
            step.id = %step.id,
            http.method = tracing::field::Empty,
            http.url = tracing::field::Empty,
            http.status_code = tracing::field::Empty,
            http.duration_ms = tracing::field::Empty,
            otel.kind = "client"
        )
    )]
    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult> {
        let span = tracing::Span::current();
        let start_time = Instant::now();

        // 1. Parse parameters
        let params = &step.params;
        let method_str = params.get("method")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("Missing 'method' in params"))?;

        let path_str = params.get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("Missing 'path' in params"))?;

        // Resolve URL (Base URL + Path)
        // Note: We need to access config from context or pass it down.
        // For now, we'll assume context has a special variable or we need to refactor execute signature.
        // Refactoring execute to take Plan Config is a larger change.
        // Quick fix: Check if path is absolute, if not, try to find base_url in context variables (set by main).

        let interpolated_path = context.interpolate_str(path_str)?;

        let url = if interpolated_path.starts_with("http") {
            interpolated_path
        } else {
            // Try to get base_url from context, default to empty if not found (will likely fail)
            let base = context.get("base_url")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            format!("{}{}", base.trim_end_matches('/'), interpolated_path)
        };

        let method = Method::from_bytes(method_str.as_bytes())
            .map_err(|e| anyhow!("Invalid HTTP method: {}", e))?;

        // Record OTEL attributes
        span.record("http.method", method_str);
        span.record("http.url", &url);

        // 2. Build Request
        let mut request_builder = self.client.request(method, &url);

        // Add Headers
        if let Some(headers) = params.get("headers").and_then(|h| h.as_object()) {
            for (k, v) in headers {
                if let Some(v_str) = v.as_str() {
                    let value = context.interpolate_str(v_str)?;
                    request_builder = request_builder.header(k, value);
                }
            }
        }

        // Add Body
        if let Some(body) = params.get("body") {
            let resolved = context.interpolate_value(body)?;
            request_builder = request_builder.json(&resolved);
        }

        // 3. Execute Request
        let response = request_builder.send().await;

        let duration = start_time.elapsed().as_millis() as u64;

        // 4. Handle Result
        match response {
            Ok(resp) => {
                let status = resp.status().as_u16();
                let headers = resp.headers().clone();
                let raw_body = resp.text().await.unwrap_or_default();
                let body_json: Value = serde_json::from_str(&raw_body).unwrap_or(Value::Null);
                
                // Record OTEL attributes for response
                span.record("http.status_code", status as i64);
                span.record("http.duration_ms", duration as i64);
                
                tracing::info!(method = %method_str, %url, status, duration_ms = duration, "HTTP step finished");

                let response_ctx = ResponseContext {
                    status,
                    body: &body_json,
                    headers: &headers,
                    duration_ms: duration,
                };

                if let Some(error_msg) = self.validate_assertions(&step.assertions, &response_ctx) {
                    tracing::warn!(error = %error_msg, "Assertion failed");
                    return Ok(StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Failed,
                        duration_ms: duration,
                        error: Some(error_msg),
                    });
                }

                self.apply_extractions(&step.extract, &body_json, &headers, context);

                Ok(StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Passed,
                    duration_ms: duration,
                    error: None,
                })
            },
            Err(e) => {
                tracing::error!(error = %e, "HTTP request failed");
                Ok(StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Failed,
                    duration_ms: duration,
                    error: Some(e.to_string()),
                })
            }
        }
    }
}
