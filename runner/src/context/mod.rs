// Module: Context
// Manages variable state, interpolation, and secrets.

use std::collections::HashMap;
use serde_json::Value;

/// Holds the execution state, including variables and secrets.
#[derive(Debug, Default)]
pub struct Context {
    pub variables: HashMap<String, Value>,
}

impl Context {
    /// Creates a new empty context.
    pub fn new() -> Self {
        Self {
            variables: HashMap::new(),
        }
    }

    /// Updates a variable in the context.
    pub fn set(&mut self, key: String, value: Value) {
        self.variables.insert(key, value);
    }

    /// Retrieves a variable from the context.
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.variables.get(key)
    }
}
