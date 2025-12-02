//! Executor para a ação `wait`.
//!
//! Este executor implementa delays/pausas entre steps,
//! útil para simular tempo de espera ou rate limiting.

use anyhow::{Result, anyhow};
use async_trait::async_trait;
use serde::Deserialize;
use std::time::{Duration, Instant};
use tokio::time::sleep;
use tracing::{info, instrument};

use crate::context::Context;
use crate::protocol::{Step, StepResult, StepStatus};

use super::StepExecutor;

/// Parâmetros para a ação `wait`.
#[derive(Debug, Deserialize)]
struct WaitParams {
    /// Duração do delay em milissegundos.
    duration_ms: u64,
}

/// Executor para a ação `wait`.
///
/// Permite pausar a execução por um tempo especificado,
/// útil para:
/// - Simular delays entre requests
/// - Aguardar processamento assíncrono
/// - Rate limiting manual
pub struct WaitExecutor;

impl WaitExecutor {
    pub fn new() -> Self {
        Self
    }
}

impl Default for WaitExecutor {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl StepExecutor for WaitExecutor {
    fn can_handle(&self, action: &str) -> bool {
        action == "wait"
    }

    #[instrument(skip(self, _context), fields(step_id = %step.id, duration_ms))]
    async fn execute(&self, step: &Step, _context: &mut Context) -> Result<StepResult> {
        let start = Instant::now();

        // Parse dos parâmetros
        let params: WaitParams = serde_json::from_value(step.params.clone())
            .map_err(|e| anyhow!("Parâmetros inválidos para wait: {}. Esperado: {{ \"duration_ms\": <número> }}", e))?;

        tracing::Span::current().record("duration_ms", params.duration_ms);

        info!(
            step_id = %step.id,
            duration_ms = params.duration_ms,
            "⏳ Aguardando..."
        );

        // Executa o delay
        sleep(Duration::from_millis(params.duration_ms)).await;

        let elapsed = start.elapsed().as_millis() as u64;

        info!(
            step_id = %step.id,
            actual_duration_ms = elapsed,
            "✅ Wait concluído"
        );

        Ok(StepResult {
            step_id: step.id.clone(),
            status: StepStatus::Passed,
            duration_ms: elapsed,
            error: None,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn create_wait_step(duration_ms: u64) -> Step {
        Step {
            id: "wait_step".to_string(),
            description: Some("Test wait".to_string()),
            depends_on: vec![],
            action: "wait".to_string(),
            params: json!({ "duration_ms": duration_ms }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }
    }

    #[tokio::test]
    async fn test_wait_executor_handles_wait_action() {
        let executor = WaitExecutor::new();
        assert!(executor.can_handle("wait"));
        assert!(!executor.can_handle("http_request"));
    }

    #[tokio::test]
    async fn test_wait_executor_delays_correctly() {
        let executor = WaitExecutor::new();
        let step = create_wait_step(100); // 100ms
        let mut context = Context::new();

        let result = executor.execute(&step, &mut context).await.unwrap();

        assert_eq!(result.status, StepStatus::Passed);
        assert!(result.duration_ms >= 100); // Deve ter esperado pelo menos 100ms
        assert!(result.duration_ms < 200); // Mas não muito mais
    }

    #[tokio::test]
    async fn test_wait_executor_invalid_params() {
        let executor = WaitExecutor::new();
        let step = Step {
            id: "bad_wait".to_string(),
            description: None,
            depends_on: vec![],
            action: "wait".to_string(),
            params: json!({ "invalid": "params" }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        };
        let mut context = Context::new();

        let result = executor.execute(&step, &mut context).await;
        assert!(result.is_err());
    }
}
