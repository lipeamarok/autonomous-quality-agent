mod protocol;
mod loader;
mod executors;
mod context;
mod telemetry;
mod retry;
mod validation;
mod planner;

use protocol::{ExecutionReport, StepStatus, Step};
use executors::{StepExecutor, http::HttpExecutor, wait::WaitExecutor};
use context::Context;
use planner::DagPlanner;
use telemetry::{TelemetryConfig, init_telemetry, shutdown_telemetry};
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::sync::Arc;
use std::fs;
use chrono::Utc;
use tokio::sync::RwLock;
use tracing::{error, info};

#[derive(Parser)]
#[command(name = "runner")]
#[command(about = "Autonomous Quality Agent Runner", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Executes a test plan
    Execute {
        /// Path to the UTDL file
        #[arg(short, long)]
        file: PathBuf,

        /// Path to the output report file
        #[arg(short, long)]
        output: Option<PathBuf>,

        /// Enable parallel execution using DAG scheduler
        #[arg(long, default_value = "false")]
        parallel: bool,

        /// Enable OpenTelemetry tracing export
        #[arg(long, default_value = "false")]
        otel: bool,

        /// OTEL endpoint (default: from OTEL_EXPORTER_OTLP_ENDPOINT env var)
        #[arg(long)]
        otel_endpoint: Option<String>,
    },
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    match &cli.command {
        Commands::Execute { file, output, parallel, otel, otel_endpoint } => {
            // Configura telemetria
            let mut telemetry_config = TelemetryConfig::from_env();
            
            if *otel {
                // Se --otel foi passado, usa endpoint do argumento ou default
                if let Some(endpoint) = otel_endpoint {
                    telemetry_config.otlp_endpoint = Some(endpoint.clone());
                } else if telemetry_config.otlp_endpoint.is_none() {
                    // Default endpoint se nenhum foi especificado
                    telemetry_config.otlp_endpoint = Some("http://localhost:4317".to_string());
                }
            }

            // Inicializa telemetria
            if let Err(e) = init_telemetry(telemetry_config) {
                eprintln!("Warning: Failed to initialize telemetry: {}", e);
                // Fallback para logging simples
                let _ = tracing_subscriber::fmt()
                    .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
                    .try_init();
            }

            execute_plan(file, output, *parallel).await;
            
            // Shutdown telemetria para garantir flush de traces
            shutdown_telemetry();
        }
    }
}

async fn execute_plan(file_path: &PathBuf, output_path: &Option<PathBuf>, parallel: bool) {
    info!("Runner initializing");
    let start_time = Utc::now();

    // 1. Load Plan
    let plan = match loader::load_plan_from_file(file_path) {
        Ok(p) => p,
        Err(e) => {
            error!(error = %e, "Failed to load plan");
            std::process::exit(1);
        }
    };
    info!(plan_id = %plan.meta.id, plan_name = %plan.meta.name, "Plan loaded");

    // 2. Validate Plan
    if let Err(errors) = validation::validate_plan(&plan) {
        error!("Plan validation failed with {} error(s):", errors.len());
        for err in &errors {
            error!("  - {}", err);
        }
        std::process::exit(1);
    }
    info!("Plan validation passed");

    // 3. Initialize Context & Executors
    let mut context = Context::new();
    context.set("base_url", serde_json::Value::String(plan.config.base_url.clone()));
    context.extend(&plan.config.variables);

    let http_executor = HttpExecutor::new();
    let wait_executor = WaitExecutor::new();
    let executors: Vec<Box<dyn StepExecutor + Send + Sync>> = vec![
        Box::new(http_executor),
        Box::new(wait_executor),
    ];

    // 4. Execute Steps
    info!(parallel = parallel, "Starting execution");
    
    let step_results = if parallel {
        // Execução paralela usando DAG
        let planner = DagPlanner::new(plan.steps);
        let executors_arc = Arc::new(executors);
        let context_arc = Arc::new(RwLock::new(context));
        
        planner.execute(executors_arc, context_arc).await
    } else {
        // Execução sequencial (comportamento original)
        execute_sequential(plan.steps, executors, context).await
    };

    let all_passed = step_results.iter().all(|r| r.status == StepStatus::Passed);

    let end_time = Utc::now();
    info!("Execution finished");

    // 5. Generate Report
    let report = ExecutionReport {
        plan_id: plan.meta.id.clone(),
        status: if all_passed { "passed".to_string() } else { "failed".to_string() },
        start_time: start_time.to_rfc3339(),
        end_time: end_time.to_rfc3339(),
        steps: step_results,
    };

    // 5. Save Report
    if let Some(path) = output_path {
        let json = serde_json::to_string_pretty(&report).expect("Failed to serialize report");
        if let Err(e) = fs::write(path, json) {
            eprintln!("❌ Failed to write report: {}", e);
        } else {
            println!("📄 Report saved to: {:?}", path);
        }
    } else {
        // Print to stdout if no file specified
        let json = serde_json::to_string_pretty(&report).expect("Failed to serialize report");
        println!("\n--- Execution Report ---\n{}", json);
    }
}

/// Executa steps sequencialmente (modo padrão).
async fn execute_sequential(
    steps: Vec<Step>,
    executors: Vec<Box<dyn StepExecutor + Send + Sync>>,
    mut context: Context,
) -> Vec<protocol::StepResult> {
    let mut step_results = Vec::new();

    for step in steps {
        info!(step_id = %step.id, action = %step.action, "Running step");

        let executor = executors.iter().find(|e| e.can_handle(&step.action));

        let result = match executor {
            Some(exec) => execute_step_with_retry(&step, exec.as_ref(), &mut context).await,
            None => {
                error!(step_id = %step.id, action = %step.action, "No executor found for action");
                protocol::StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Failed,
                    duration_ms: 0,
                    error: Some(format!("Unknown action: {}", step.action)),
                }
            }
        };

        info!(step_id = %step.id, status = ?result.status, duration_ms = result.duration_ms, "Step finished");
        step_results.push(result);
    }

    step_results
}

/// Executa um step com suporte a retry conforme RecoveryPolicy.
async fn execute_step_with_retry(
    step: &Step,
    executor: &dyn StepExecutor,
    context: &mut Context,
) -> protocol::StepResult {
    // Extrai configurações de retry
    let max_attempts = step.recovery_policy.as_ref().map(|p| p.max_attempts).unwrap_or(1);
    let strategy = step.recovery_policy.as_ref()
        .map(|p| p.strategy.as_str())
        .unwrap_or("fail_fast");
    let backoff_ms = step.recovery_policy.as_ref().map(|p| p.backoff_ms).unwrap_or(0);
    let backoff_factor = step.recovery_policy.as_ref().map(|p| p.backoff_factor).unwrap_or(2.0);

    let mut attempt = 0u32;

    loop {
        attempt += 1;
        
        match executor.execute(step, context).await {
            Ok(result) => {
                if result.status == StepStatus::Passed {
                    return result;
                }
                // Assertion falhou
                
                if strategy == "ignore" {
                    return protocol::StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Passed, // Ignora falha
                        duration_ms: result.duration_ms,
                        error: None,
                    };
                }
                
                if strategy != "retry" || attempt >= max_attempts {
                    return result;
                }
            }
            Err(e) => {
                error!(step_id = %step.id, error = %e, attempt = attempt, "Step execution failed");
                
                if strategy == "ignore" {
                    return protocol::StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Passed,
                        duration_ms: 0,
                        error: None,
                    };
                }
                
                if strategy != "retry" || attempt >= max_attempts {
                    return protocol::StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Failed,
                        duration_ms: 0,
                        error: Some(e.to_string()),
                    };
                }
            }
        }

        // Calcula backoff exponencial
        let backoff = (backoff_ms as f64 * backoff_factor.powi(attempt as i32 - 1)) as u64;
        info!(step_id = %step.id, attempt = attempt, max_attempts = max_attempts, backoff_ms = backoff, "Retrying after backoff");
        tokio::time::sleep(std::time::Duration::from_millis(backoff)).await;
    }
}
