//! # Módulo de Limites de Execução (Rate Limiting)
//!
//! Define políticas de limite para proteger o sistema contra
//! planos UTDL malformados ou maliciosos gerados pela IA.
//!
//! ## Para todos entenderem:
//!
//! Imagine que você tem um restaurante e precisa de regras:
//! - Máximo 50 pedidos por mesa (evita sobrecarga)
//! - Máximo 10 pratos sendo preparados ao mesmo tempo (evita caos)
//! - Máximo 3 tentativas de refazer um prato (evita desperdício)
//! - Máximo 2 horas de atendimento por mesa (evita monopolização)
//!
//! Este módulo faz exatamente isso para a execução de testes.
//!
//! ## Por que isso é importante?
//!
//! 1. **Proteção contra DoS**: IA pode gerar planos infinitos
//! 2. **Recursos controlados**: Evita consumir toda CPU/memória
//! 3. **Previsibilidade**: Sabe-se quanto tempo/recursos serão usados
//! 4. **Debug facilitado**: Planos problemáticos falham cedo
//!
//! ## Limites configuráveis:
//!
//! | Limite             | Padrão | Descrição                           |
//! |--------------------|--------|-------------------------------------|
//! | max_steps          | 100    | Máximo de steps por plano           |
//! | max_parallel       | 10     | Máximo de steps paralelos           |
//! | max_retries_total  | 50     | Máximo de retries no plano todo     |
//! | max_execution_secs | 300    | Timeout total de execução (5 min)   |
//! | max_step_timeout   | 30     | Timeout por step (segundos)         |

use std::time::Duration;
use serde::{Deserialize, Serialize};

// ============================================================================
// LIMITES PADRÃO (CONSTANTES)
// ============================================================================

/// Número máximo de steps permitidos em um plano.
/// Protege contra planos gigantes que consumiriam muitos recursos.
pub const DEFAULT_MAX_STEPS: usize = 100;

/// Número máximo de steps executando em paralelo.
/// Evita sobrecarga de conexões/threads.
pub const DEFAULT_MAX_PARALLEL: usize = 10;

/// Número máximo de retries no plano inteiro.
/// Evita loops infinitos de retry.
pub const DEFAULT_MAX_RETRIES_TOTAL: u32 = 50;

/// Tempo máximo de execução do plano todo (em segundos).
/// Evita que um plano trave indefinidamente.
pub const DEFAULT_MAX_EXECUTION_SECS: u64 = 300; // 5 minutos

/// Timeout máximo por step individual (em segundos).
/// Evita que um step lento trave todo o plano.
pub const DEFAULT_MAX_STEP_TIMEOUT_SECS: u64 = 30;

// ============================================================================
// ESTRUTURA DE LIMITES
// ============================================================================

/// Configuração de limites de execução.
///
/// Pode ser carregada de arquivo, variáveis de ambiente, ou CLI.
/// Todos os campos têm valores padrão seguros.
///
/// ## Exemplo de uso:
///
/// ```rust
/// let limits = ExecutionLimits::default();
/// // Ou personalizado:
/// let limits = ExecutionLimits {
///     max_steps: 50,
///     max_parallel: 5,
///     ..Default::default()
/// };
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionLimits {
    /// Número máximo de steps no plano.
    /// Se excedido, plano é rejeitado na validação.
    pub max_steps: usize,

    /// Número máximo de steps executando simultaneamente.
    /// Limita o paralelismo do DAG executor.
    pub max_parallel: usize,

    /// Número máximo de retries em todo o plano.
    /// Soma de todos os retries de todos os steps.
    pub max_retries_total: u32,

    /// Timeout total para execução do plano.
    /// Depois desse tempo, execução é abortada.
    pub max_execution_time: Duration,

    /// Timeout máximo para cada step individual.
    /// Sobrescreve o timeout do step se for maior.
    pub max_step_timeout: Duration,
}

impl Default for ExecutionLimits {
    fn default() -> Self {
        Self {
            max_steps: DEFAULT_MAX_STEPS,
            max_parallel: DEFAULT_MAX_PARALLEL,
            max_retries_total: DEFAULT_MAX_RETRIES_TOTAL,
            max_execution_time: Duration::from_secs(DEFAULT_MAX_EXECUTION_SECS),
            max_step_timeout: Duration::from_secs(DEFAULT_MAX_STEP_TIMEOUT_SECS),
        }
    }
}

impl ExecutionLimits {
    /// Cria limites a partir de variáveis de ambiente.
    ///
    /// Variáveis suportadas:
    /// - `RUNNER_MAX_STEPS`: Máximo de steps
    /// - `RUNNER_MAX_PARALLEL`: Máximo paralelismo
    /// - `RUNNER_MAX_RETRIES`: Máximo retries
    /// - `RUNNER_MAX_EXECUTION_SECS`: Timeout total
    /// - `RUNNER_MAX_STEP_TIMEOUT`: Timeout por step
    pub fn from_env() -> Self {
        let mut limits = Self::default();

        if let Ok(val) = std::env::var("RUNNER_MAX_STEPS") {
            if let Ok(n) = val.parse() {
                limits.max_steps = n;
            }
        }

        if let Ok(val) = std::env::var("RUNNER_MAX_PARALLEL") {
            if let Ok(n) = val.parse() {
                limits.max_parallel = n;
            }
        }

        if let Ok(val) = std::env::var("RUNNER_MAX_RETRIES") {
            if let Ok(n) = val.parse() {
                limits.max_retries_total = n;
            }
        }

        if let Ok(val) = std::env::var("RUNNER_MAX_EXECUTION_SECS") {
            if let Ok(n) = val.parse() {
                limits.max_execution_time = Duration::from_secs(n);
            }
        }

        if let Ok(val) = std::env::var("RUNNER_MAX_STEP_TIMEOUT") {
            if let Ok(n) = val.parse() {
                limits.max_step_timeout = Duration::from_secs(n);
            }
        }

        limits
    }

    /// Limites restritivos para testes.
    pub fn strict() -> Self {
        Self {
            max_steps: 10,
            max_parallel: 2,
            max_retries_total: 5,
            max_execution_time: Duration::from_secs(30),
            max_step_timeout: Duration::from_secs(5),
        }
    }

    /// Limites permissivos para desenvolvimento.
    pub fn relaxed() -> Self {
        Self {
            max_steps: 500,
            max_parallel: 50,
            max_retries_total: 200,
            max_execution_time: Duration::from_secs(3600), // 1 hora
            max_step_timeout: Duration::from_secs(120),
        }
    }
}

// ============================================================================
// VALIDAÇÃO DE LIMITES
// ============================================================================

/// Resultado da validação de limites.
#[derive(Debug)]
pub struct LimitValidationResult {
    pub passed: bool,
    pub violations: Vec<LimitViolation>,
}

/// Violação de limite detectada.
#[derive(Debug, Clone)]
pub struct LimitViolation {
    /// Nome do limite violado.
    pub limit_name: String,
    /// Valor máximo permitido.
    pub limit_value: String,
    /// Valor encontrado no plano.
    pub actual_value: String,
    /// Mensagem descritiva.
    pub message: String,
}

/// Valida se um plano está dentro dos limites.
///
/// ## Parâmetros:
/// - `step_count`: Número de steps no plano
/// - `total_retries`: Soma de max_attempts de todos os steps
/// - `limits`: Configuração de limites
///
/// ## Retorno:
/// `LimitValidationResult` com lista de violações (se houver)
pub fn validate_limits(
    step_count: usize,
    total_retries: u32,
    limits: &ExecutionLimits,
) -> LimitValidationResult {
    let mut violations = Vec::new();

    // Verifica limite de steps
    if step_count > limits.max_steps {
        violations.push(LimitViolation {
            limit_name: "max_steps".to_string(),
            limit_value: limits.max_steps.to_string(),
            actual_value: step_count.to_string(),
            message: format!(
                "Plano tem {} steps, máximo permitido é {}",
                step_count, limits.max_steps
            ),
        });
    }

    // Verifica limite de retries
    if total_retries > limits.max_retries_total {
        violations.push(LimitViolation {
            limit_name: "max_retries_total".to_string(),
            limit_value: limits.max_retries_total.to_string(),
            actual_value: total_retries.to_string(),
            message: format!(
                "Plano pode ter até {} retries, máximo permitido é {}",
                total_retries, limits.max_retries_total
            ),
        });
    }

    LimitValidationResult {
        passed: violations.is_empty(),
        violations,
    }
}

// ============================================================================
// CONTADOR DE RETRIES (RUNTIME)
// ============================================================================

/// Contador de retries em tempo de execução.
///
/// Usado durante a execução para rastrear quantos retries
/// já foram feitos e abortar se exceder o limite.
#[derive(Debug, Default)]
pub struct RetryCounter {
    count: std::sync::atomic::AtomicU32,
    limit: u32,
}

impl RetryCounter {
    /// Cria um novo contador com o limite especificado.
    pub fn new(limit: u32) -> Self {
        Self {
            count: std::sync::atomic::AtomicU32::new(0),
            limit,
        }
    }

    /// Tenta incrementar o contador.
    /// Retorna `true` se ainda está dentro do limite.
    /// Retorna `false` se excedeu (retry não deve ser feito).
    pub fn try_increment(&self) -> bool {
        let current = self.count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        current < self.limit
    }

    /// Retorna o número atual de retries.
    pub fn current(&self) -> u32 {
        self.count.load(std::sync::atomic::Ordering::SeqCst)
    }

    /// Retorna o limite configurado.
    pub fn limit(&self) -> u32 {
        self.limit
    }
}

// ============================================================================
// TESTES
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_limits() {
        let limits = ExecutionLimits::default();
        assert_eq!(limits.max_steps, 100);
        assert_eq!(limits.max_parallel, 10);
        assert_eq!(limits.max_retries_total, 50);
    }

    #[test]
    fn test_strict_limits() {
        let limits = ExecutionLimits::strict();
        assert_eq!(limits.max_steps, 10);
        assert_eq!(limits.max_parallel, 2);
    }

    #[test]
    fn test_validate_limits_ok() {
        let limits = ExecutionLimits::default();
        let result = validate_limits(50, 20, &limits);
        assert!(result.passed);
        assert!(result.violations.is_empty());
    }

    #[test]
    fn test_validate_limits_steps_exceeded() {
        let limits = ExecutionLimits::default();
        let result = validate_limits(150, 20, &limits);
        assert!(!result.passed);
        assert_eq!(result.violations.len(), 1);
        assert_eq!(result.violations[0].limit_name, "max_steps");
    }

    #[test]
    fn test_validate_limits_retries_exceeded() {
        let limits = ExecutionLimits::default();
        let result = validate_limits(10, 100, &limits);
        assert!(!result.passed);
        assert_eq!(result.violations.len(), 1);
        assert_eq!(result.violations[0].limit_name, "max_retries_total");
    }

    #[test]
    fn test_retry_counter() {
        let counter = RetryCounter::new(3);

        assert!(counter.try_increment()); // 1
        assert!(counter.try_increment()); // 2
        assert!(counter.try_increment()); // 3
        assert!(!counter.try_increment()); // 4 - excedeu!

        assert_eq!(counter.current(), 4);
    }
}
