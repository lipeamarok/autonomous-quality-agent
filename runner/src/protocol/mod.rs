use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use serde_json::Value;

#[derive(Debug, Deserialize, Serialize)]
pub struct Plan {
    pub spec_version: String,
    pub meta: Meta,
    pub config: Config,
    pub steps: Vec<Step>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Meta {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    pub created_at: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Config {
    pub base_url: String,
    pub timeout_ms: u64,
    #[serde(default)]
    pub global_headers: HashMap<String, String>,
    #[serde(default)]
    pub variables: HashMap<String, Value>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Step {
    pub id: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub depends_on: Vec<String>,
    pub action: String,
    pub params: Value,
    #[serde(default)]
    pub assertions: Vec<Assertion>,
    #[serde(default)]
    pub extract: Vec<Extraction>,
    #[serde(default)]
    pub recovery_policy: Option<RecoveryPolicy>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Assertion {
    #[serde(rename = "type")]
    pub assertion_type: String,
    pub operator: String,
    pub value: Value,
    #[serde(default)]
    pub path: Option<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Extraction {
    pub source: String,
    pub path: String,
    pub target: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct RecoveryPolicy {
    /// Estratégia: "retry", "fail_fast", "ignore"
    pub strategy: String,
    /// Número máximo de tentativas (incluindo a primeira)
    pub max_attempts: u32,
    /// Delay base em milissegundos entre tentativas
    pub backoff_ms: u64,
    /// Fator multiplicador para backoff exponencial (padrão: 2.0)
    #[serde(default = "default_backoff_factor")]
    pub backoff_factor: f64,
}

fn default_backoff_factor() -> f64 {
    2.0
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct StepResult {
    pub step_id: String,
    pub status: StepStatus,
    pub duration_ms: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
#[serde(rename_all = "lowercase")]
pub enum StepStatus {
    Passed,
    Failed,
    Skipped,
}

#[derive(Debug, Serialize)]
pub struct ExecutionReport {
    pub plan_id: String,
    pub status: String, // "passed" | "failed"
    pub start_time: String,
    pub end_time: String,
    pub steps: Vec<StepResult>,
}
