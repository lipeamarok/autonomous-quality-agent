use async_trait::async_trait;
use crate::protocol::{Step, StepResult, StepStatus, Assertion, Extraction};
use crate::context::Context;
use super::StepExecutor;
use anyhow::{Result, anyhow};
use std::time::Instant;
use reqwest::{Client, Method, header::HeaderMap};
use serde_json::Value;

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

    fn validate_assertions(&self, assertions: &[Assertion], status: u16, body: &Value) -> Option<String> {
        for assertion in assertions {
            match assertion.assertion_type.as_str() {
                "status_code" => {
                    let expected = assertion.value.as_u64().unwrap_or(0) as u16;
                    let passed = match assertion.operator.as_str() {
                        "eq" => status == expected,
                        "neq" => status != expected,
                        "lt" => status < expected,
                        "gt" => status > expected,
                        _ => false,
                    };
                    if !passed {
                        return Some(format!(
                            "Assertion failed: status_code {} {} {} (got {})",
                            assertion.operator, expected, "", status
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

                        if let Some(actual) = body.pointer(&pointer) {
                            let passed = match assertion.operator.as_str() {
                                "eq" => actual == &assertion.value,
                                "neq" => actual != &assertion.value,
                                "contains" => actual.as_str().map(|s| {
                                    assertion.value.as_str().map(|needle| s.contains(needle)).unwrap_or(false)
                                }).unwrap_or(false),
                                _ => false,
                            };

                            if !passed {
                                return Some(format!(
                                    "Assertion failed: json_body '{}' {} {} (got {})",
                                    path, assertion.operator, assertion.value, actual
                                ));
                            }
                        } else {
                            return Some(format!("Assertion failed: path '{}' not found in response body", path));
                        }
                    }
                }
                _ => {}
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

    #[tracing::instrument(name = "http_step", skip_all, fields(step_id = %step.id))]
    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult> {
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
                tracing::info!(method = %method_str, %url, status, duration_ms = duration, "HTTP step finished");

                if let Some(error_msg) = self.validate_assertions(&step.assertions, status, &body_json) {
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
