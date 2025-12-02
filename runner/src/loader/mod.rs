// Module: Loader
// Responsible for parsing and validating UTDL files.

use crate::protocol::Plan;
use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

pub fn load_plan_from_file<P: AsRef<Path>>(path: P) -> Result<Plan> {
    let path_ref = path.as_ref();
    let content = fs::read_to_string(path_ref)
        .with_context(|| format!("Failed to read plan file {:?}", path_ref))?;
    let plan = serde_json::from_str(&content)
        .with_context(|| format!("Failed to parse plan JSON {:?}", path_ref))?;
    Ok(plan)
}
