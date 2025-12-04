//! # Runner - Motor de Execução do Autonomous Quality Agent
//!
//! Este é o **ponto de entrada principal** do Runner, o componente de alta performance
//! escrito em Rust que executa os planos de teste gerados pelo Brain.
//!
//! ## O que este arquivo faz?
//!
//! 1. **Processa argumentos da linha de comando** (CLI) usando a biblioteca `clap`
//! 2. **Carrega e valida** o arquivo UTDL (plano de testes em JSON)
//! 3. **Inicializa o sistema de telemetria** (OpenTelemetry) para observabilidade
//! 4. **Executa os steps** do plano (sequencial ou paralelo)
//! 5. **Gera um relatório** com os resultados da execução
//!
//! ## Exemplo de uso:
//!
//! ```bash
//! # Executar um plano de testes
//! runner execute --file plano.utdl.json --output resultado.json
//!
//! # Executar em paralelo com telemetria OTEL
//! runner execute --file plano.utdl.json --parallel --otel
//! ```
//!
//! ## Arquitetura do Runner
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                           main.rs                                │
//! │  (CLI, orquestração, relatórios)                                │
//! └─────────────────────────────────────────────────────────────────┘
//!                                 │
//!          ┌──────────────────────┼──────────────────────┐
//!          ▼                      ▼                      ▼
//!    ┌──────────┐          ┌──────────┐           ┌──────────┐
//!    │ loader/  │          │ planner/ │           │executors/│
//!    │ (JSON)   │          │ (DAG)    │           │ (HTTP,   │
//!    │          │          │          │           │  Wait)   │
//!    └──────────┘          └──────────┘           └──────────┘
//! ```

// ============================================================================
// DECLARAÇÃO DE MÓDULOS
// ============================================================================
// Em Rust, `mod` importa um módulo (pasta ou arquivo) para uso neste arquivo.
// Cada módulo é um "pacote" de código relacionado.

/// Módulo de contexto: gerencia variáveis, interpolação e estado da execução.
mod context;

/// Módulo de erros: códigos de erro estruturados (E1xxx, E2xxx, etc.).
mod errors;

/// Módulo de executores: implementações de ações (HTTP, Wait, etc.).
mod executors;

/// Módulo de extração: captura dados de respostas HTTP para o contexto.
mod extractors;

/// Módulo de limites: políticas de rate-limiting e proteção.
mod limits;

/// Módulo de carregamento: lê e parseia arquivos UTDL (JSON).
mod loader;

/// Módulo de planejamento: DAG para execução paralela.
mod planner;

/// Módulo de protocolo: estruturas de dados UTDL (Plan, Step, etc.).
mod protocol;

/// Módulo de retry: políticas de recuperação (retry, fail_fast, ignore).
mod retry;

/// Módulo de telemetria: integração OpenTelemetry.
mod telemetry;

/// Módulo de validação: verifica se o plano UTDL é válido.
mod validation;

// ============================================================================
// IMPORTS (DEPENDÊNCIAS)
// ============================================================================
// `use` traz itens de outros módulos para uso direto neste arquivo.

// Imports internos (nossos módulos)
use context::Context;
use executors::{http::HttpExecutor, wait::WaitExecutor, StepExecutor};
use limits::ExecutionLimits;
use planner::DagPlanner;
use protocol::{ExecutionReport, Step, StepStatus};
use telemetry::{init_telemetry, shutdown_telemetry, TelemetryConfig};

// Imports externos (bibliotecas de terceiros)
use chrono::Utc; // Data/hora em UTC
use clap::{Parser, Subcommand}; // Parser de argumentos CLI
use std::fs; // Operações de sistema de arquivos
use std::path::PathBuf; // Tipo para caminhos de arquivo
use std::sync::Arc; // Ponteiro atômico para compartilhar dados entre threads
use tokio::sync::RwLock; // Lock de leitura/escrita assíncrono
use tracing::{error, info, Level}; // Macros de logging estruturado
use uuid::Uuid; // Geração de UUIDs

// ============================================================================
// DEFINIÇÃO DA CLI (INTERFACE DE LINHA DE COMANDO)
// ============================================================================

/// Estrutura principal da CLI.
///
/// Esta estrutura define os argumentos que o usuário pode passar na linha de comando.
/// O atributo `#[derive(Parser)]` usa a biblioteca `clap` para gerar automaticamente
/// o parser de argumentos.
///
/// ## Exemplo:
/// ```bash
/// runner --help          # Mostra ajuda
/// runner execute --file plano.json  # Executa um plano
/// ```
#[derive(Parser)]
#[command(name = "runner")]
#[command(about = "Autonomous Quality Agent Runner - Motor de execução de testes", long_about = None)]
struct Cli {
    /// Subcomando a ser executado (atualmente só temos `execute`).
    #[command(subcommand)]
    command: Commands,
}

/// Enum que define os subcomandos disponíveis.
///
/// Cada variante do enum representa um subcomando diferente.
/// Atualmente só temos `Execute`, mas podemos adicionar outros no futuro
/// como `validate`, `lint`, `export`, etc.
#[derive(Subcommand)]
enum Commands {
    /// Executa um plano de testes UTDL.
    ///
    /// Este é o comando principal do Runner. Ele carrega o plano,
    /// valida a estrutura, executa os steps e gera um relatório.
    Execute {
        /// Caminho para o arquivo UTDL (JSON com o plano de testes).
        ///
        /// Exemplo: `--file ./plans/login_test.utdl.json`
        #[arg(short, long)]
        file: PathBuf,

        /// Caminho para salvar o relatório de execução (opcional).
        ///
        /// Se não especificado, o relatório é impresso no console.
        /// Exemplo: `--output ./reports/resultado.json`
        #[arg(short, long)]
        output: Option<PathBuf>,

        /// Habilita execução paralela usando o scheduler DAG.
        ///
        /// Quando ativado, steps sem dependências entre si são
        /// executados em paralelo para melhor performance.
        #[arg(long, default_value = "false")]
        parallel: bool,

        /// Habilita exportação de traces para OpenTelemetry.
        ///
        /// Envia spans/traces para um collector OTEL para
        /// visualização em ferramentas como Jaeger, Grafana, etc.
        #[arg(long, default_value = "false")]
        otel: bool,

        /// Endpoint do collector OTEL (opcional).
        ///
        /// Se não especificado, usa a variável de ambiente
        /// `OTEL_EXPORTER_OTLP_ENDPOINT` ou `http://localhost:4317`.
        #[arg(long)]
        otel_endpoint: Option<String>,

        /// Modo silencioso: apenas erros críticos no stderr.
        ///
        /// Ideal para CI/CD onde você só quer saber se passou ou falhou.
        /// Desativa logs informativos e de progresso.
        #[arg(long, short = 's', default_value = "false")]
        silent: bool,

        /// Modo verbose: logs detalhados de debug.
        ///
        /// Mostra detalhes de cada step, interpolação de variáveis,
        /// headers HTTP, bodies de resposta, etc.
        /// Ideal para desenvolvimento e debugging.
        #[arg(long, short = 'v', default_value = "false")]
        verbose: bool,

        /// ID de execução customizado (UUID).
        ///
        /// Se não especificado, gera um UUID v4 automaticamente.
        /// Útil para rastreabilidade em sistemas externos.
        #[arg(long)]
        execution_id: Option<String>,
    },
}

// ============================================================================
// FUNÇÃO PRINCIPAL (PONTO DE ENTRADA)
// ============================================================================

/// Função principal - ponto de entrada do programa.
///
/// O atributo `#[tokio::main]` transforma esta função em uma função assíncrona
/// que roda dentro do runtime Tokio. Isso é necessário porque usamos `async/await`
/// para operações de I/O não-bloqueantes (HTTP, arquivos, etc.).
///
/// ## Fluxo de execução:
/// 1. Parseia os argumentos da CLI
/// 2. Configura a telemetria (logging e OTEL)
/// 3. Chama a função apropriada baseado no subcomando
/// 4. Encerra a telemetria antes de sair
#[tokio::main]
async fn main() {
    // Parseia os argumentos da linha de comando.
    // Se os argumentos forem inválidos, `clap` exibe uma mensagem de erro e sai.
    let cli = Cli::parse();

    // Processa o subcomando escolhido pelo usuário.
    // Em Rust, `match` é como um `switch` em outras linguagens, mas mais poderoso.
    match &cli.command {
        Commands::Execute {
            file,
            output,
            parallel,
            otel,
            otel_endpoint,
            silent,
            verbose,
            execution_id,
        } => {
            // Gera ou usa o execution_id fornecido.
            let exec_id = execution_id
                .clone()
                .unwrap_or_else(|| Uuid::new_v4().to_string());

            // Carrega configuração de telemetria das variáveis de ambiente.
            let mut telemetry_config = TelemetryConfig::from_env();

            // Configura nível de log baseado nos flags silent/verbose.
            telemetry_config.log_level = if *silent {
                Level::ERROR
            } else if *verbose {
                Level::DEBUG
            } else {
                Level::INFO
            };

            // Se o usuário passou --otel, configura o endpoint.
            if *otel {
                // Se o endpoint foi especificado na CLI, usa ele.
                if let Some(endpoint) = otel_endpoint {
                    telemetry_config.otlp_endpoint = Some(endpoint.clone());
                }
                // Senão, se não há endpoint configurado, usa o padrão.
                else if telemetry_config.otlp_endpoint.is_none() {
                    telemetry_config.otlp_endpoint = Some("http://localhost:4317".to_string());
                }
            }

            // Inicializa o sistema de telemetria (logging + OTEL).
            // Se falhar, cai para logging simples no console.
            if let Err(e) = init_telemetry(telemetry_config) {
                if !*silent {
                    eprintln!("Warning: Failed to initialize telemetry: {}", e);
                }
                // Fallback: configura logging básico sem OTEL.
                let _ = tracing_subscriber::fmt()
                    .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
                    .try_init();
            }

            // Executa o plano de testes.
            // `*parallel` dereferencia o valor booleano.
            execute_plan(file, output, *parallel, &exec_id, *silent).await;

            // Encerra a telemetria, garantindo que todos os traces sejam enviados.
            shutdown_telemetry();
        }
    }
}

// ============================================================================
// FUNÇÃO DE EXECUÇÃO DO PLANO
// ============================================================================

/// Executa um plano de testes UTDL.
///
/// Esta é a função principal que orquestra toda a execução:
///
/// ## Etapas:
/// 1. **Load**: Carrega o arquivo JSON do disco
/// 2. **Validate**: Verifica se a estrutura é válida
/// 3. **Limits**: Verifica limites de steps e retries
/// 4. **Initialize**: Configura contexto e executores
/// 5. **Execute**: Roda os steps (sequencial ou paralelo)
/// 6. **Report**: Gera e salva o relatório
///
/// ## Parâmetros:
/// - `file_path`: Caminho para o arquivo UTDL
/// - `output_path`: Onde salvar o relatório (ou None para stdout)
/// - `parallel`: Se deve usar execução paralela (DAG)
/// - `execution_id`: UUID único desta execução
/// - `silent`: Se true, suprime logs informativos
async fn execute_plan(
    file_path: &PathBuf,
    output_path: &Option<PathBuf>,
    parallel: bool,
    execution_id: &str,
    silent: bool,
) {
    if !silent {
        info!(execution_id = %execution_id, "Runner initializing");
    }
    let start_time = Utc::now();

    // 1. Carrega o plano do arquivo JSON.
    let plan = match loader::load_plan_from_file(file_path) {
        Ok(p) => p,
        Err(e) => {
            error!(error = %e, "Failed to load plan");
            std::process::exit(1);
        }
    };
    if !silent {
        info!(plan_id = %plan.meta.id, plan_name = %plan.meta.name, "Plan loaded");
    }

    // 2. Valida a estrutura do plano antes de executar.
    if let Err(errors) = validation::validate_plan(&plan) {
        error!("Plan validation failed with {} error(s):", errors.len());
        for err in &errors {
            error!("  - {}", err);
        }
        std::process::exit(1);
    }
    if !silent {
        info!("Plan validation passed");
    }

    // 2.5. Valida limites de execução.
    let limits = ExecutionLimits::from_env();
    let total_retries: u32 = plan
        .steps
        .iter()
        .map(|s| {
            s.recovery_policy
                .as_ref()
                .map(|p| p.max_attempts)
                .unwrap_or(1)
        })
        .sum();
    let limit_result = limits::validate_limits(plan.steps.len(), total_retries, &limits);
    if !limit_result.passed {
        error!("Plan exceeds execution limits:");
        for v in &limit_result.violations {
            error!("  - {}", v.message);
        }
        std::process::exit(1);
    }

    // 3. Inicializa o contexto e os executores.
    let mut context = Context::new();
    context.set(
        "base_url",
        serde_json::Value::String(plan.config.base_url.clone()),
    );
    context.set(
        "execution_id",
        serde_json::Value::String(execution_id.to_string()),
    );
    context.extend(&plan.config.variables);

    // Cria os executores para cada tipo de action.
    let http_executor = HttpExecutor::new();
    let wait_executor = WaitExecutor::new();
    let executors: Vec<Box<dyn StepExecutor + Send + Sync>> =
        vec![Box::new(http_executor), Box::new(wait_executor)];

    // 4. Executa os steps (paralelo ou sequencial).
    if !silent {
        info!(parallel = parallel, "Starting execution");
    }

    let step_results = if parallel {
        // Execução paralela usando DAG.
        let planner = DagPlanner::new(plan.steps);
        let executors_arc = Arc::new(executors);
        let context_arc = Arc::new(RwLock::new(context));

        planner.execute(executors_arc, context_arc, limits).await
    } else {
        // Execução sequencial (comportamento padrão).
        execute_sequential(plan.steps, executors, context).await
    };

    let all_passed = step_results.iter().all(|r| r.status == StepStatus::Passed);

    let end_time = Utc::now();
    if !silent {
        info!("Execution finished");
    }

    // 5. Gera o relatório de execução.
    let report = ExecutionReport {
        execution_id: execution_id.to_string(),
        plan_id: plan.meta.id.clone(),
        status: if all_passed {
            "passed".to_string()
        } else {
            "failed".to_string()
        },
        start_time: start_time.to_rfc3339(),
        end_time: end_time.to_rfc3339(),
        steps: step_results,
    };

    // 5. Salva ou imprime o relatório.
    if let Some(path) = output_path {
        let json = serde_json::to_string_pretty(&report).expect("Failed to serialize report");
        if let Err(e) = fs::write(path, json) {
            eprintln!("❌ Failed to write report: {}", e);
        } else if !silent {
            println!("📄 Report saved to: {:?}", path);
        }
    } else if !silent {
        // Imprime no stdout se nenhum arquivo foi especificado.
        let json = serde_json::to_string_pretty(&report).expect("Failed to serialize report");
        println!("\n--- Execution Report ---\n{}", json);
    }

    // Exit code baseado no resultado
    if !all_passed {
        std::process::exit(1);
    }
}

// ============================================================================
// EXECUÇÃO SEQUENCIAL
// ============================================================================

/// Executa steps sequencialmente (modo padrão).
///
/// Este é o modo mais simples: cada step é executado após o anterior terminar.
/// Útil para debugging e quando a ordem de execução é crítica.
///
/// ## Parâmetros:
/// - `steps`: Lista de steps a executar
/// - `executors`: Lista de executores disponíveis
/// - `context`: Contexto de execução (variáveis)
///
/// ## Retorno:
/// Vetor com os resultados de cada step.
async fn execute_sequential(
    steps: Vec<Step>,
    executors: Vec<Box<dyn StepExecutor + Send + Sync>>,
    mut context: Context,
) -> Vec<protocol::StepResult> {
    let mut step_results = Vec::new();

    for step in steps {
        info!(step_id = %step.id, action = %step.action, "Running step");

        // Encontra um executor que saiba lidar com esta action.
        let executor = executors.iter().find(|e| e.can_handle(&step.action));

        let result = match executor {
            Some(exec) => execute_step_with_retry(&step, exec.as_ref(), &mut context).await,
            None => {
                error!(step_id = %step.id, action = %step.action, "No executor found for action");
                // Captura contexto para debug
                let context_snapshot = context.variables.clone();
                protocol::StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Failed,
                    duration_ms: 0,
                    error: Some(format!("Unknown action: {}", step.action)),
                    context_before: Some(context_snapshot.clone()),
                    context_after: Some(context_snapshot),
                    extractions: None,
                }
            }
        };

        info!(step_id = %step.id, status = ?result.status, duration_ms = result.duration_ms, "Step finished");
        step_results.push(result);
    }

    step_results
}

// ============================================================================
// EXECUÇÃO COM RETRY
// ============================================================================

/// Executa um step com suporte a retry conforme RecoveryPolicy.
///
/// ## Estratégias de Recuperação:
///
/// - **retry**: Tenta novamente até `max_attempts` com backoff exponencial
/// - **fail_fast**: Falha imediatamente sem retry (padrão)
/// - **ignore**: Marca como passed mesmo se falhar
///
/// ## Backoff Exponencial:
///
/// O tempo entre tentativas aumenta exponencialmente:
/// - Tentativa 1: falha → espera backoff_ms
/// - Tentativa 2: falha → espera backoff_ms × backoff_factor
/// - Tentativa 3: falha → espera backoff_ms × backoff_factor²
///
/// Exemplo: backoff_ms=500, backoff_factor=2.0 → 500ms, 1000ms, 2000ms...
async fn execute_step_with_retry(
    step: &Step,
    executor: &dyn StepExecutor,
    context: &mut Context,
) -> protocol::StepResult {
    // Extrai configurações de retry da RecoveryPolicy.
    let max_attempts = step
        .recovery_policy
        .as_ref()
        .map(|p| p.max_attempts)
        .unwrap_or(1);
    let strategy = step
        .recovery_policy
        .as_ref()
        .map(|p| p.strategy.as_str())
        .unwrap_or("fail_fast");
    let backoff_ms = step
        .recovery_policy
        .as_ref()
        .map(|p| p.backoff_ms)
        .unwrap_or(0);
    let backoff_factor = step
        .recovery_policy
        .as_ref()
        .map(|p| p.backoff_factor)
        .unwrap_or(2.0);

    let mut attempt = 0u32;

    loop {
        attempt += 1;

        // Snapshot do contexto antes da execução
        let context_before = context.variables.clone();

        match executor.execute(step, context).await {
            Ok(result) => {
                if result.status == StepStatus::Passed {
                    return result;
                }
                // Assertion falhou.

                if strategy == "ignore" {
                    return protocol::StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Passed, // Ignora falha
                        duration_ms: result.duration_ms,
                        error: None,
                        context_before: result.context_before,
                        context_after: result.context_after,
                        extractions: result.extractions,
                    };
                }

                if strategy != "retry" || attempt >= max_attempts {
                    return result;
                }
            }
            Err(e) => {
                error!(step_id = %step.id, error = %e, attempt = attempt, "Step execution failed");

                // Captura contexto após erro para debug
                let context_after = context.variables.clone();

                if strategy == "ignore" {
                    return protocol::StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Passed,
                        duration_ms: 0,
                        error: None,
                        context_before: Some(context_before),
                        context_after: Some(context_after),
                        extractions: None,
                    };
                }

                if strategy != "retry" || attempt >= max_attempts {
                    return protocol::StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Failed,
                        duration_ms: 0,
                        error: Some(e.to_string()),
                        context_before: Some(context_before),
                        context_after: Some(context_after),
                        extractions: None,
                    };
                }
            }
        }

        // Calcula backoff exponencial e aguarda.
        let backoff = (backoff_ms as f64 * backoff_factor.powi(attempt as i32 - 1)) as u64;
        info!(step_id = %step.id, attempt = attempt, max_attempts = max_attempts, backoff_ms = backoff, "Retrying after backoff");
        tokio::time::sleep(std::time::Duration::from_millis(backoff)).await;
    }
}
