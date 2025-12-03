//! # Módulo de Retry com RecoveryPolicy
//!
//! Implementa estratégias de recuperação para steps que falham,
//! permitindo retry automático com backoff exponencial.
//!
//! ## Para todos entenderem:
//!
//! Às vezes, um teste falha por motivos temporários:
//! - Servidor estava ocupado
//! - Rede teve um soluço
//! - Recurso ainda não estava pronto
//!
//! Este módulo permite "tentar de novo" automaticamente,
//! esperando um pouco mais a cada tentativa.
//!
//! ## Estratégias de Recuperação:
//!
//! ### 1. retry (tentar novamente)
//!
//! Tenta novamente até `max_attempts` vezes.
//! Entre cada tentativa, espera cada vez mais (backoff exponencial).
//!
//! Exemplo: backoff_ms=100, backoff_factor=2
//! - 1ª falha: espera 100ms
//! - 2ª falha: espera 200ms (100 × 2)
//! - 3ª falha: espera 400ms (200 × 2)
//!
//! ### 2. fail_fast (falhar imediatamente)
//!
//! Não tenta novamente. Se falhou, falhou.
//! É o comportamento padrão.
//!
//! ### 3. ignore (ignorar falha)
//!
//! Se falhar, marca como sucesso mesmo assim.
//! Útil para steps opcionais.
//!
//! ## Exemplo de uso no UTDL:
//!
//! ```json
//! {
//!   "id": "step_com_retry",
//!   "recovery_policy": {
//!     "strategy": "retry",
//!     "max_attempts": 3,
//!     "backoff_ms": 100,
//!     "backoff_factor": 2.0
//!   }
//! }
//! ```
//!
//! ## O que é Backoff Exponencial?
//!
//! É uma técnica onde esperamos cada vez mais entre tentativas.
//! Isso evita sobrecarregar um servidor que está com problemas.
//!
//! Se todos os clientes tentassem imediatamente, o servidor
//! nunca conseguiria se recuperar. Com backoff, damos tempo.

use std::time::Duration;
use tokio::time::sleep;
use tracing::{info, warn};

use crate::protocol::RecoveryPolicy;

// ============================================================================
// ESTRATÉGIAS DE RECUPERAÇÃO
// ============================================================================

/// Enum que representa as estratégias de recuperação.
///
/// Usamos enum ao invés de strings para segurança de tipos.
/// O compilador garante que só usamos valores válidos.
#[derive(Debug, Clone, PartialEq)]
pub enum RecoveryStrategy {
    /// Tenta novamente com backoff exponencial.
    Retry,
    /// Falha imediatamente sem retry.
    FailFast,
    /// Ignora falhas e marca como sucesso.
    Ignore,
}

impl RecoveryStrategy {
    /// Converte string para RecoveryStrategy.
    ///
    /// Aceita variações comuns como:
    /// - "retry" → Retry
    /// - "fail_fast" ou "failfast" → FailFast
    /// - "ignore" → Ignore
    /// - Qualquer outro valor → FailFast (comportamento conservador)
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "retry" => Self::Retry,
            "fail_fast" | "failfast" => Self::FailFast,
            "ignore" => Self::Ignore,
            _ => Self::FailFast, // Default conservador: não tentar novamente
        }
    }
}

// ============================================================================
// RETRY EXECUTOR
// ============================================================================

/// Executor de retry com backoff exponencial.
///
/// Esta struct encapsula uma política de recuperação e fornece
/// um método genérico para executar operações com retry.
///
/// ## Para todos entenderem:
///
/// É como um assistente que:
/// 1. Tenta fazer algo
/// 2. Se falhar, olha para as regras (policy)
/// 3. Decide se tenta de novo ou desiste
/// 4. Se tentar de novo, espera um pouco primeiro
///
/// ## Nota de implementação:
///
/// Esta estrutura é usada principalmente em testes.
/// A lógica de retry em produção está inline em main.rs
/// para melhor integração com o fluxo de execução.
#[allow(dead_code)]
pub struct RetryExecutor {
    /// A política de recuperação (max_attempts, backoff_ms, etc.)
    policy: RecoveryPolicy,
    /// A estratégia parseada para enum.
    strategy: RecoveryStrategy,
}

#[allow(dead_code)]
impl RetryExecutor {
    /// Cria um novo RetryExecutor a partir de uma política.
    pub fn new(policy: RecoveryPolicy) -> Self {
        let strategy = RecoveryStrategy::from_str(&policy.strategy);
        Self { policy, strategy }
    }

    /// Executa uma operação com retry conforme a política.
    ///
    /// Este é um método genérico que aceita qualquer closure assíncrona
    /// que retorna Result<T, E>.
    ///
    /// ## Parâmetros:
    ///
    /// - `step_id`: ID do step (para logging)
    /// - `operation`: Closure que retorna Future<Output = Result<T, E>>
    ///
    /// ## Retorno:
    ///
    /// - `Ok(Some(result))`: Sucesso, retorna o resultado
    /// - `Ok(None)`: Strategy=ignore e operação falhou
    /// - `Err(error)`: Falha após todas as tentativas
    ///
    /// ## Para todos entenderem sobre closures:
    ///
    /// Uma closure é como uma função anônima.
    /// `FnMut() -> Fut` significa: "algo que pode ser chamado
    /// múltiplas vezes e retorna um Future".
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
            // ================================================================
            // FAIL_FAST: Executa uma vez, falha se der erro.
            // ================================================================
            RecoveryStrategy::FailFast => {
                match operation().await {
                    Ok(result) => Ok(Some(result)),
                    Err(e) => Err(e),
                }
            }

            // ================================================================
            // IGNORE: Executa uma vez, ignora erros.
            // ================================================================
            RecoveryStrategy::Ignore => {
                match operation().await {
                    Ok(result) => Ok(Some(result)),
                    Err(e) => {
                        // Loga warning mas não falha.
                        warn!(
                            step_id = %step_id,
                            error = %e,
                            "Step falhou mas strategy=ignore, continuando"
                        );
                        Ok(None)
                    }
                }
            }

            // ================================================================
            // RETRY: Tenta múltiplas vezes com backoff.
            // ================================================================
            RecoveryStrategy::Retry => {
                let mut attempt = 1;
                let mut current_backoff = self.policy.backoff_ms;

                // Loop de tentativas.
                loop {
                    match operation().await {
                        // Sucesso!
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
                        // Falha.
                        Err(e) => {
                            // Verifica se esgotou as tentativas.
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

                            // Ainda tem tentativas, loga e aguarda.
                            warn!(
                                step_id = %step_id,
                                attempt = attempt,
                                max_attempts = self.policy.max_attempts,
                                backoff_ms = current_backoff,
                                error = %e,
                                "Tentativa falhou, aguardando retry"
                            );

                            // Aguarda o backoff.
                            sleep(Duration::from_millis(current_backoff)).await;

                            // Calcula próximo backoff (exponencial).
                            // Exemplo: 100ms × 2.0 = 200ms.
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

/// Implementação de Default para RetryExecutor.
///
/// O padrão é fail_fast: sem retry, falha imediatamente.
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

// ============================================================================
// TESTES
// ============================================================================

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
