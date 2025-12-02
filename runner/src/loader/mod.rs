// Module: Loader
// Responsible for parsing and validating UTDL files.

use crate::protocol::Plan;
use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

pub fn load_plan_from_file<P: AsRef<Path>>(path: P) -> Result<Plan> {
    let content = fs::read_to_string(path).context("Failed to read plan file")?;
    let plan = serde_json::from_str(&content).context("Failed to parse plan JSON")?;
    Ok(plan)
}
