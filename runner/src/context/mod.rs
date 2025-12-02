// Module: Context
// Manages variable state, interpolation, and secrets.

use std::collections::HashMap;
use anyhow::{anyhow, Result};
use once_cell::sync::Lazy;
use regex::Regex;
use serde_json::{Map, Value};

static INTERPOLATION_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\$\{([A-Za-z0-9_.:-]+)\}").expect("valid interpolation regex")
});

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
    pub fn set(&mut self, key: impl Into<String>, value: Value) {
        self.variables.insert(key.into(), value);
    }

    /// Bulk insert of variables.
    pub fn extend(&mut self, entries: &HashMap<String, Value>) {
        for (k, v) in entries {
            self.variables.insert(k.clone(), v.clone());
        }
    }

    /// Retrieves a variable from the context.
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.variables.get(key)
    }

    /// Interpolates placeholders like ${token} inside a string.
    pub fn interpolate_str(&self, input: &str) -> Result<String> {
        let mut result = String::new();
        let mut last_index = 0;

        for capture in INTERPOLATION_RE.captures_iter(input) {
            let matched = capture.get(0).unwrap();
            result.push_str(&input[last_index..matched.start()]);
            let token = capture.get(1).unwrap().as_str();
            let resolved = self.resolve_token(token)?;
            result.push_str(&resolved);
            last_index = matched.end();
        }

        result.push_str(&input[last_index..]);
        Ok(result)
    }

    /// Recursively interpolates strings inside JSON values.
    pub fn interpolate_value(&self, value: &Value) -> Result<Value> {
        match value {
            Value::String(s) => Ok(Value::String(self.interpolate_str(s)?)),
            Value::Array(items) => {
                let mut result = Vec::with_capacity(items.len());
                for item in items {
                    result.push(self.interpolate_value(item)?);
                }
                Ok(Value::Array(result))
            }
            Value::Object(map) => {
                let mut new_map = Map::with_capacity(map.len());
                for (k, v) in map {
                    new_map.insert(k.clone(), self.interpolate_value(v)?);
                }
                Ok(Value::Object(new_map))
            }
            _ => Ok(value.clone()),
        }
    }

    fn resolve_token(&self, token: &str) -> Result<String> {
        if let Some(rest) = token.strip_prefix("ENV_") {
            std::env::var(rest)
                .map_err(|_| anyhow!("Missing environment variable '{}'.", rest))
        } else if let Some(value) = self.variables.get(token) {
            match value {
                Value::String(s) => Ok(s.clone()),
                primitive => Ok(primitive.to_string()),
            }
        } else {
            Err(anyhow!("Missing context variable '{}'.", token))
        }
    }
}
