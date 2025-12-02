use async_trait::async_trait;
use crate::protocol::{Step, StepResult, StepStatus, Assertion};
use crate::context::Context;
use super::StepExecutor;
use anyhow::{Result, anyhow};
use std::time::Instant;
use reqwest::{Client, Method};
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

    fn validate_assertions(&self, assertions: &[Assertion], status: u16) -> Option<String> {
        for assertion in assertions {
            if assertion.assertion_type == "status_code" {
                let expected = assertion.value.as_u64().unwrap_or(0) as u16;
                let passed = match assertion.operator.as_str() {
                    "eq" => status == expected,
                    "neq" => status != expected,
                    "lt" => status < expected,
                    "gt" => status > expected,
                    _ => false, // Unsupported operator
                };

                if !passed {
                    return Some(format!(
                        "Assertion failed: status_code {} {} {} (got {})",
                        assertion.operator, expected, "", status
                    ));
                }
            }
            // TODO: Implement other assertion types (json_body, header, latency)
        }
        None
    }
}

#[async_trait]
impl StepExecutor for HttpExecutor {
    fn can_handle(&self, action: &str) -> bool {
        action == "http_request"
    }

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

        let url = if path_str.starts_with("http") {
            path_str.to_string()
        } else {
            // Try to get base_url from context, default to empty if not found (will likely fail)
            let base = context.get("base_url")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            format!("{}{}", base.trim_end_matches('/'), path_str)
        };

        let method = Method::from_bytes(method_str.as_bytes())
            .map_err(|e| anyhow!("Invalid HTTP method: {}", e))?;

        // 2. Build Request
        let request = self.client.request(method, &url);

        // 3. Execute Request
        let response = request.send().await;

        let duration = start_time.elapsed().as_millis() as u64;

        // 4. Handle Result
        match response {
            Ok(resp) => {
                let status = resp.status().as_u16();
                println!("   -> HTTP {} {} [{}ms]", method_str, url, duration);
                println!("   -> Status: {}", status);

                // Validate Assertions
                if let Some(error_msg) = self.validate_assertions(&step.assertions, status) {
                    return Ok(StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Failed,
                        duration_ms: duration,
                        error: Some(error_msg),
                    });
                }

                Ok(StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Passed,
                    duration_ms: duration,
                    error: None,
                })
            },
            Err(e) => {
                println!("   -> Error: {}", e);
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
