// Module: Executors
// Contains implementations for different step actions (HTTP, Wait, etc).

pub mod http;
pub mod wait;

use async_trait::async_trait;
use crate::protocol::{Step, StepResult};
use crate::context::Context;
use anyhow::Result;

/// Trait that defines the contract for any step executor.
/// This allows us to easily extend the runner with new capabilities (e.g., Browser, gRPC).
///
/// O trait requer Send + Sync para suportar execução paralela com tokio::spawn.
#[async_trait]
pub trait StepExecutor: Send + Sync {
    /// Checks if this executor is responsible for the given action.
    fn can_handle(&self, action: &str) -> bool;

    /// Executes the step logic and returns the result.
    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult>;
}
