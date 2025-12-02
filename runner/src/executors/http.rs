use async_trait::async_trait;
use crate::protocol::{Step, StepResult, StepStatus};
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
}

#[async_trait]
impl StepExecutor for HttpExecutor {
    fn can_handle(&self, action: &str) -> bool {
        action == "http_request"
    }

    async fn execute(&self, step: &Step, _context: &mut Context) -> Result<StepResult> {
        let start_time = Instant::now();

        // 1. Parse parameters
        let params = &step.params;
        let method_str = params.get("method")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("Missing 'method' in params"))?;

        let url_str = params.get("path") // Note: In a real scenario, we would join with base_url
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("Missing 'path' in params"))?;

        let method = Method::from_bytes(method_str.as_bytes())
            .map_err(|e| anyhow!("Invalid HTTP method: {}", e))?;

        // 2. Build Request
        // TODO: Add headers and body support
        let request = self.client.request(method, url_str);

        // 3. Execute Request
        let response = request.send().await;

        let duration = start_time.elapsed().as_millis() as u64;

        // 4. Handle Result
        match response {
            Ok(resp) => {
                let status = resp.status();
                println!("   -> HTTP {} {} [{}ms]", method_str, url_str, duration);
                println!("   -> Status: {}", status);

                // TODO: Implement assertions here

                Ok(StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Passed, // Assuming pass for now if request succeeds
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
