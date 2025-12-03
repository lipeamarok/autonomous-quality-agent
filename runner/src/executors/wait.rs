//! # Executor Wait/Sleep - Delays e Pausas
//!
//! Este executor implementa pausas na execução dos testes.
//! É útil para simular delays entre requisições ou aguardar processamento.
//!
//! ## Actions suportadas:
//! - `wait` - Pausa a execução pelo tempo especificado
//! - `sleep` - Alias de `wait` (mesma funcionalidade)
//!
//! ## Casos de uso:
//! - **Rate limiting**: Evitar exceder limites de API
//! - **Processamento assíncrono**: Aguardar um job processar
//! - **Simulação de usuário**: Delays realistas entre ações
//! - **Debugging**: Pausar para inspecionar estado
//!
//! ## Exemplo de uso no UTDL:
//!
//! ```json
//! {
//!   "id": "wait_processing",
//!   "action": "wait",
//!   "params": {
//!     "duration_ms": 2000
//!   }
//! }
//! ```

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use serde::Deserialize;
use std::time::{Duration, Instant};
use tokio::time::sleep;
use tracing::{info, instrument};

use crate::context::Context;
use crate::protocol::{Step, StepResult, StepStatus};

use super::StepExecutor;

// ============================================================================
// PARÂMETROS DO WAIT
// ============================================================================

/// Parâmetros esperados para a ação `wait`/`sleep`.
///
/// Esta struct é usada para deserializar os parâmetros do step.
/// O atributo `#[derive(Deserialize)]` permite converter JSON para esta struct.
///
/// ## Formatos aceitos:
/// - `{ "duration_ms": 1000 }` - Formato canônico
/// - `{ "ms": 1000 }` - Alias mais curto
///
/// Se ambos forem fornecidos, `duration_ms` tem precedência.
#[derive(Debug, Deserialize)]
struct WaitParams {
    /// Duração do delay em milissegundos (formato canônico).
    ///
    /// Deve ser um número inteiro positivo.
    /// Exemplo: 1000 = 1 segundo, 500 = meio segundo
    #[serde(default)]
    duration_ms: Option<u64>,

    /// Duração do delay em milissegundos (alias curto).
    ///
    /// Alternativa mais concisa para `duration_ms`.
    /// Se `duration_ms` estiver presente, este campo é ignorado.
    #[serde(default)]
    ms: Option<u64>,
}

impl WaitParams {
    /// Retorna a duração em milissegundos, priorizando `duration_ms` sobre `ms`.
    ///
    /// ## Retorno:
    /// - `Some(u64)` se pelo menos um dos campos estiver definido
    /// - `None` se nenhum campo estiver definido
    fn get_duration(&self) -> Option<u64> {
        self.duration_ms.or(self.ms)
    }
}

// ============================================================================
// WAIT EXECUTOR
// ============================================================================

/// Executor para as ações `wait` e `sleep`.
///
/// Este executor é muito simples: ele apenas pausa a execução
/// pelo tempo especificado e retorna sucesso.
///
/// ## Por que ter um executor separado para isso?
///
/// Manter a mesma arquitetura para todas as ações permite:
/// - Consistência no código
/// - Mesma interface de instrumentação (spans OTEL)
/// - Fácil adição de funcionalidades (ex: wait condicional no futuro)
///
/// ## Thread Safety:
///
/// O `WaitExecutor` não tem estado interno, então é completamente
/// thread-safe e pode ser usado em execução paralela sem problemas.
pub struct WaitExecutor;

impl WaitExecutor {
    /// Cria um novo WaitExecutor.
    ///
    /// Como não há estado, isso apenas retorna uma instância vazia.
    pub fn new() -> Self {
        Self
    }
}

/// Implementação de Default para WaitExecutor.
///
/// Permite criar com `WaitExecutor::default()`.
impl Default for WaitExecutor {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// IMPLEMENTAÇÃO DO TRAIT
// ============================================================================

#[async_trait]
impl StepExecutor for WaitExecutor {
    /// Verifica se este executor lida com a action especificada.
    ///
    /// Retorna `true` para:
    /// - "wait" - Ação principal
    /// - "sleep" - Alias para compatibilidade
    fn can_handle(&self, action: &str) -> bool {
        action == "wait" || action == "sleep"
    }

    /// Executa o delay.
    ///
    /// ## Fluxo:
    /// 1. Parseia os parâmetros para obter `duration_ms`
    /// 2. Registra no span OTEL
    /// 3. Aguarda o tempo especificado
    /// 4. Retorna sucesso com a duração real
    ///
    /// ## Parâmetros esperados:
    /// ```json
    /// { "duration_ms": 1000 }
    /// ```
    ///
    /// ## Nota sobre precisão:
    ///
    /// A duração real pode ser ligeiramente maior que a especificada
    /// devido ao overhead do sistema operacional e do runtime Tokio.
    #[instrument(skip(self, _context), fields(step_id = %step.id, duration_ms))]
    async fn execute(&self, step: &Step, _context: &mut Context) -> Result<StepResult> {
        // Marca o início para calcular a duração real.
        let start = Instant::now();

        // Parseia os parâmetros do step.
        // `serde_json::from_value` converte o Value para WaitParams.
        let params: WaitParams = serde_json::from_value(step.params.clone()).map_err(|e| {
            anyhow!(
                "Parâmetros inválidos para {}: {}. Esperado: {{ \"duration_ms\": <número> }} ou {{ \"ms\": <número> }}",
                step.action,
                e
            )
        })?;

        // Obtém a duração, priorizando duration_ms sobre ms.
        let duration_ms = params.get_duration().ok_or_else(|| {
            anyhow!(
                "Parâmetros incompletos para {}: forneça 'duration_ms' ou 'ms'",
                step.action
            )
        })?;

        // Registra a duração no span OTEL.
        tracing::Span::current().record("duration_ms", duration_ms);

        // Log informativo.
        info!(
            step_id = %step.id,
            action = %step.action,
            duration_ms = duration_ms,
            "⏳ Aguardando..."
        );

        // Executa o delay.
        // `sleep` é uma função assíncrona do Tokio que não bloqueia a thread.
        sleep(Duration::from_millis(duration_ms)).await;

        // Calcula a duração real.
        let elapsed = start.elapsed().as_millis() as u64;

        // Log de conclusão.
        info!(
            step_id = %step.id,
            actual_duration_ms = elapsed,
            "✅ Wait concluído"
        );

        // Retorna sucesso.
        // Wait sempre passa (a menos que haja erro nos parâmetros).
        Ok(StepResult {
            step_id: step.id.clone(),
            status: StepStatus::Passed,
            duration_ms: elapsed,
            error: None,
            context_before: None,
            context_after: None,
            extractions: None,
        })
    }
}

// ============================================================================
// TESTES
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    /// Cria um step de wait para testes.
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

    #[tokio::test]
    async fn test_wait_executor_handles_sleep_action() {
        let executor = WaitExecutor::new();
        // Verifica que 'sleep' é reconhecido como alias.
        assert!(executor.can_handle("sleep"));
    }

    #[tokio::test]
    async fn test_sleep_action_executes() {
        let executor = WaitExecutor::new();
        let step = Step {
            id: "sleep_step".to_string(),
            description: None,
            depends_on: vec![],
            action: "sleep".to_string(), // Usando sleep ao invés de wait
            params: json!({ "duration_ms": 50 }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        };
        let mut context = Context::new();

        let result = executor.execute(&step, &mut context).await.unwrap();

        assert_eq!(result.status, StepStatus::Passed);
        assert!(result.duration_ms >= 50);
    }

    #[tokio::test]
    async fn test_wait_with_ms_alias() {
        let executor = WaitExecutor::new();
        let step = Step {
            id: "wait_ms".to_string(),
            description: Some("Test wait with ms alias".to_string()),
            depends_on: vec![],
            action: "wait".to_string(),
            params: json!({ "ms": 75 }), // Usando alias 'ms'
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        };
        let mut context = Context::new();

        let result = executor.execute(&step, &mut context).await.unwrap();

        assert_eq!(result.status, StepStatus::Passed);
        assert!(result.duration_ms >= 75);
        assert!(result.duration_ms < 150);
    }

    #[tokio::test]
    async fn test_duration_ms_takes_precedence_over_ms() {
        let executor = WaitExecutor::new();
        let step = Step {
            id: "wait_both".to_string(),
            description: Some("Both duration_ms and ms provided".to_string()),
            depends_on: vec![],
            action: "wait".to_string(),
            params: json!({ "duration_ms": 50, "ms": 200 }), // duration_ms deve ter precedência
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        };
        let mut context = Context::new();

        let result = executor.execute(&step, &mut context).await.unwrap();

        assert_eq!(result.status, StepStatus::Passed);
        // Deve usar duration_ms (50), não ms (200)
        assert!(result.duration_ms >= 50);
        assert!(result.duration_ms < 150); // Confirma que não esperou 200ms
    }

    #[tokio::test]
    async fn test_wait_missing_duration() {
        let executor = WaitExecutor::new();
        let step = Step {
            id: "wait_no_duration".to_string(),
            description: None,
            depends_on: vec![],
            action: "wait".to_string(),
            params: json!({}), // Sem duration_ms nem ms
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        };
        let mut context = Context::new();

        let result = executor.execute(&step, &mut context).await;

        assert!(result.is_err());
        let err_msg = result.unwrap_err().to_string();
        assert!(err_msg.contains("duration_ms") || err_msg.contains("ms"));
    }
}
