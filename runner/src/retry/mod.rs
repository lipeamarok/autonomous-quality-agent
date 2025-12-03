//! Módulo de Retry com RecoveryPolicy.
//!
//! Implementa algoritmo de retry exponencial com suporte a estratégias:
//! - `retry`: tenta novamente até max_attempts com backoff exponencial
//! - `fail_fast`: falha imediatamente sem retry
//! - `ignore`: marca como passed mesmo se falhar

use std::time::Duration;
use tokio::time::sleep;
use tracing::{info, warn};

use crate::protocol::RecoveryPolicy;

/// Estratégias de recuperação suportadas.
#[derive(Debug, Clone, PartialEq)]
pub enum RecoveryStrategy {
    /// Retry com backoff exponencial
    Retry,
    /// Falha imediatamente
    FailFast,
    /// Ignora falhas (marca como passed)
    Ignore,
}

impl RecoveryStrategy {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "retry" => Self::Retry,
            "fail_fast" | "failfast" => Self::FailFast,
            "ignore" => Self::Ignore,
            _ => Self::FailFast, // Default conservador
        }
    }
}

/// Executor de retry com backoff exponencial.
///
/// Nota: Esta estrutura é mantida para testes e uso futuro.
/// A lógica de retry inline em main.rs é usada na execução real.
#[allow(dead_code)]
pub struct RetryExecutor {
    policy: RecoveryPolicy,
    strategy: RecoveryStrategy,
}

#[allow(dead_code)]
impl RetryExecutor {
    pub fn new(policy: RecoveryPolicy) -> Self {
        let strategy = RecoveryStrategy::from_str(&policy.strategy);
        Self { policy, strategy }
    }

    /// Executa uma operação com retry conforme a política.
    ///
    /// # Argumentos
    /// * `step_id` - ID do step para logging
    /// * `operation` - Closure assíncrona que retorna Result<T, E>
    ///
    /// # Retorno
    /// * `Ok(Some(result))` - Sucesso
    /// * `Ok(None)` - Ignorado (strategy = ignore)
    /// * `Err(error)` - Falha após todas tentativas
    pub async fn execute<T, E, F, Fut>(
        &self,
        step_id: &str,
        mut operation: F,
    ) -> Result<Option<T>, E>
    where
        F: FnMut() -> Fut,
        Fut: std::future::Future<Output = Result<T, E>>,
        E: std::fmt::Display,
    {
        match self.strategy {
            RecoveryStrategy::FailFast => {
                // Executa uma vez, falha se der erro
                match operation().await {
                    Ok(result) => Ok(Some(result)),
                    Err(e) => Err(e),
                }
            }

            RecoveryStrategy::Ignore => {
                // Executa uma vez, ignora erros
                match operation().await {
                    Ok(result) => Ok(Some(result)),
                    Err(e) => {
                        warn!(
                            step_id = %step_id,
                            error = %e,
                            "Step falhou mas strategy=ignore, continuando"
                        );
                        Ok(None)
                    }
                }
            }

            RecoveryStrategy::Retry => {
                let mut attempt = 1;
                let mut current_backoff = self.policy.backoff_ms;

                loop {
                    match operation().await {
                        Ok(result) => {
                            if attempt > 1 {
                                info!(
                                    step_id = %step_id,
                                    attempt = attempt,
                                    "Retry bem sucedido"
                                );
                            }
                            return Ok(Some(result));
                        }
                        Err(e) => {
                            if attempt >= self.policy.max_attempts {
                                warn!(
                                    step_id = %step_id,
                                    attempt = attempt,
                                    max_attempts = self.policy.max_attempts,
                                    error = %e,
                                    "Todas as tentativas esgotadas"
                                );
                                return Err(e);
                            }

                            warn!(
                                step_id = %step_id,
                                attempt = attempt,
                                max_attempts = self.policy.max_attempts,
                                backoff_ms = current_backoff,
                                error = %e,
                                "Tentativa falhou, aguardando retry"
                            );

                            // Aguarda backoff
                            sleep(Duration::from_millis(current_backoff)).await;

                            // Calcula próximo backoff (exponencial)
                            current_backoff =
                                (current_backoff as f64 * self.policy.backoff_factor) as u64;
                            attempt += 1;
                        }
                    }
                }
            }
        }
    }
}

/// Cria um executor de retry com política padrão (fail_fast).
impl Default for RetryExecutor {
    fn default() -> Self {
        Self::new(RecoveryPolicy {
            strategy: "fail_fast".to_string(),
            max_attempts: 1,
            backoff_ms: 0,
            backoff_factor: 2.0,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::Arc;

    #[tokio::test]
    async fn test_fail_fast_succeeds() {
        let policy = RecoveryPolicy {
            strategy: "fail_fast".to_string(),
            max_attempts: 1,
            backoff_ms: 100,
            backoff_factor: 2.0,
        };
        let executor = RetryExecutor::new(policy);

        let result: Result<Option<i32>, &str> = executor
            .execute("test", || async { Ok::<i32, &str>(42) })
            .await;

        assert_eq!(result.unwrap(), Some(42));
    }

    #[tokio::test]
    async fn test_fail_fast_fails_immediately() {
        let policy = RecoveryPolicy {
            strategy: "fail_fast".to_string(),
            max_attempts: 3,
            backoff_ms: 100,
            backoff_factor: 2.0,
        };
        let executor = RetryExecutor::new(policy);
        let attempts = Arc::new(AtomicU32::new(0));
        let attempts_clone = attempts.clone();

        let result: Result<Option<i32>, &str> = executor
            .execute("test", || {
                let attempts = attempts_clone.clone();
                async move {
                    attempts.fetch_add(1, Ordering::SeqCst);
                    Err::<i32, &str>("error")
                }
            })
            .await;

        assert!(result.is_err());
        assert_eq!(attempts.load(Ordering::SeqCst), 1); // Apenas uma tentativa
    }

    #[tokio::test]
    async fn test_ignore_returns_none_on_failure() {
        let policy = RecoveryPolicy {
            strategy: "ignore".to_string(),
            max_attempts: 1,
            backoff_ms: 100,
            backoff_factor: 2.0,
        };
        let executor = RetryExecutor::new(policy);

        let result: Result<Option<i32>, &str> = executor
            .execute("test", || async { Err::<i32, &str>("error") })
            .await;

        assert_eq!(result.unwrap(), None); // None indica ignorado
    }

    #[tokio::test]
    async fn test_retry_succeeds_after_failures() {
        let policy = RecoveryPolicy {
            strategy: "retry".to_string(),
            max_attempts: 3,
            backoff_ms: 10, // Curto para testes
            backoff_factor: 2.0,
        };
        let executor = RetryExecutor::new(policy);
        let attempts = Arc::new(AtomicU32::new(0));
        let attempts_clone = attempts.clone();

        let result: Result<Option<i32>, &str> = executor
            .execute("test", || {
                let attempts = attempts_clone.clone();
                async move {
                    let current = attempts.fetch_add(1, Ordering::SeqCst);
                    if current < 2 {
                        Err("temporary error")
                    } else {
                        Ok(42)
                    }
                }
            })
            .await;

        assert_eq!(result.unwrap(), Some(42));
        assert_eq!(attempts.load(Ordering::SeqCst), 3); // 2 falhas + 1 sucesso
    }

    #[tokio::test]
    async fn test_retry_exhausts_all_attempts() {
        let policy = RecoveryPolicy {
            strategy: "retry".to_string(),
            max_attempts: 3,
            backoff_ms: 10,
            backoff_factor: 2.0,
        };
        let executor = RetryExecutor::new(policy);
        let attempts = Arc::new(AtomicU32::new(0));
        let attempts_clone = attempts.clone();

        let result: Result<Option<i32>, &str> = executor
            .execute("test", || {
                let attempts = attempts_clone.clone();
                async move {
                    attempts.fetch_add(1, Ordering::SeqCst);
                    Err::<i32, &str>("persistent error")
                }
            })
            .await;

        assert!(result.is_err());
        assert_eq!(attempts.load(Ordering::SeqCst), 3); // Todas tentativas
    }
}
