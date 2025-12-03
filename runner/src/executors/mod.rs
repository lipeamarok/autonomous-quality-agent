//! # Módulo de Executores - Implementações de Ações
//!
//! Este módulo define o **trait StepExecutor** e contém as implementações
//! concretas para cada tipo de ação suportada pelo Runner.
//!
//! ## O que é um Executor?
//!
//! Um Executor é um componente que sabe como executar um tipo específico
//! de ação. Por exemplo:
//! - `HttpExecutor` sabe fazer requisições HTTP
//! - `WaitExecutor` sabe pausar a execução
//!
//! ## Arquitetura (Strategy Pattern):
//!
//! ```text
//!                    ┌─────────────────┐
//!                    │  StepExecutor   │ (trait/interface)
//!                    │  - can_handle() │
//!                    │  - execute()    │
//!                    └────────┬────────┘
//!                             │
//!            ┌────────────────┼────────────────┐
//!            ▼                ▼                ▼
//!   ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
//!   │  HttpExecutor  │ │  WaitExecutor  │ │ FuturoExecutor │
//!   │ "http_request" │ │ "wait"/"sleep" │ │  "browser"...  │
//!   └────────────────┘ └────────────────┘ └────────────────┘
//! ```
//!
//! ## Como adicionar um novo Executor:
//!
//! 1. Crie um novo arquivo (ex: `browser.rs`)
//! 2. Implemente a struct com `StepExecutor` trait
//! 3. Adicione `pub mod browser;` aqui
//! 4. Registre no `main.rs` na lista de executores
//!
//! ## Submódulos:
//! - `http`: Requisições HTTP com suporte a assertions e extractions
//! - `wait`: Delays/pausas na execução

/// Submódulo para execução de requisições HTTP.
pub mod http;

/// Submódulo para delays/pausas (wait e sleep).
pub mod wait;

// Imports necessários para o trait.
use async_trait::async_trait;
use crate::protocol::{Step, StepResult};
use crate::context::Context;
use anyhow::Result;

// ============================================================================
// TRAIT STEP EXECUTOR
// ============================================================================

/// Trait que define o contrato para qualquer executor de steps.
///
/// Este trait é a "interface" que todos os executores devem implementar.
/// Isso permite que o Runner trate todos os executores de forma uniforme,
/// sem precisar saber os detalhes de implementação de cada um.
///
/// ## Por que usar um trait?
///
/// - **Polimorfismo**: O Runner pode ter uma lista de executores diferentes
/// - **Extensibilidade**: Novos executores podem ser adicionados sem mudar o core
/// - **Testabilidade**: Podemos criar mocks para testes
///
/// ## Requisitos de Thread Safety:
///
/// O trait requer `Send + Sync` porque os executores podem ser usados
/// em múltiplas threads simultaneamente (execução paralela com DAG).
///
/// - `Send`: Pode ser transferido entre threads
/// - `Sync`: Pode ser acessado de múltiplas threads simultaneamente
///
/// ## Exemplo de implementação:
///
/// ```rust
/// struct MyExecutor;
///
/// #[async_trait]
/// impl StepExecutor for MyExecutor {
///     fn can_handle(&self, action: &str) -> bool {
///         action == "my_action"
///     }
///
///     async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult> {
///         // Implementação...
///         Ok(StepResult { ... })
///     }
/// }
/// ```
#[async_trait]
pub trait StepExecutor: Send + Sync {
    /// Verifica se este executor é responsável por uma determinada action.
    ///
    /// O Runner itera sobre todos os executores registrados e chama
    /// `can_handle()` para encontrar o executor correto para cada step.
    ///
    /// ## Parâmetros:
    /// - `action`: Tipo de ação do step (ex: "http_request", "wait")
    ///
    /// ## Retorno:
    /// - `true` se este executor sabe lidar com a action
    /// - `false` caso contrário
    ///
    /// ## Exemplo:
    /// ```rust
    /// // HttpExecutor retorna true para "http_request"
    /// assert!(http_executor.can_handle("http_request"));
    /// assert!(!http_executor.can_handle("wait"));
    /// ```
    fn can_handle(&self, action: &str) -> bool;

    /// Executa a lógica do step e retorna o resultado.
    ///
    /// Esta é a função principal onde a "mágica" acontece.
    /// Cada executor implementa sua lógica específica aqui.
    ///
    /// ## Parâmetros:
    /// - `step`: O step a executar (contém params, assertions, etc.)
    /// - `context`: Contexto mutável para leitura/escrita de variáveis
    ///
    /// ## Retorno:
    /// - `Ok(StepResult)`: Resultado com status (Passed/Failed) e duração
    /// - `Err`: Erro se algo inesperado acontecer
    ///
    /// ## Nota sobre erros:
    ///
    /// - Assertions que falham devem retornar `Ok(StepResult { status: Failed, ... })`
    /// - `Err` é reservado para erros inesperados (panic, IO error, etc.)
    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult>;
}
