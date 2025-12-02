mod protocol;
mod loader;
mod executors;
mod context;
mod telemetry;

use protocol::{Plan, ExecutionReport, StepStatus};
use executors::{StepExecutor, http::HttpExecutor};
use context::Context;
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::fs;
use chrono::Utc;

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
    },
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    match &cli.command {
        Commands::Execute { file, output } => {
            execute_plan(file, output).await;
        }
    }
}

async fn execute_plan(file_path: &PathBuf, output_path: &Option<PathBuf>) {
    println!("🚀 Runner Initializing...");
    let start_time = Utc::now();

    // 1. Load Plan
    let plan = match loader::load_plan_from_file(file_path) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("❌ Failed to load plan: {}", e);
            std::process::exit(1);
        }
    };
    println!("📋 Plan Loaded: {}", plan.meta.name);

    // 2. Initialize Context & Executors
    let mut context = Context::new();
    let http_executor = HttpExecutor::new();
    let executors: Vec<Box<dyn StepExecutor>> = vec![
        Box::new(http_executor),
    ];

    // 3. Execute Steps
    println!("▶️  Starting Execution...");
    let mut step_results = Vec::new();
    let mut all_passed = true;

    for step in plan.steps {
        println!("Running step: {}", step.id);

        let executor = executors.iter()
            .find(|e| e.can_handle(&step.action))
            .expect("No executor found for action");

        let result = match executor.execute(&step, &mut context).await {
            Ok(res) => {
                println!("   ✅ Result: {:?} ({}ms)", res.status, res.duration_ms);
                if res.status != StepStatus::Passed {
                    all_passed = false;
                }
                res
            },
            Err(e) => {
                println!("   ❌ Execution Error: {}", e);
                all_passed = false;
                protocol::StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Failed,
                    duration_ms: 0,
                    error: Some(e.to_string()),
                }
            }
        };
        step_results.push(result);
    }

    let end_time = Utc::now();
    println!("🏁 Execution Finished.");

    // 4. Generate Report
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
