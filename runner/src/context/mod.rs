// Module: Context
// Manages variable state, interpolation, secrets, and dynamic functions.

use std::collections::HashMap;
use anyhow::{anyhow, Result};
use chrono::{Utc, Local};
use once_cell::sync::Lazy;
use regex::Regex;
use serde_json::{Map, Value};
use uuid::Uuid;

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
        // Funções dinâmicas (magic variables)
        match token {
            "random_uuid" => return Ok(Uuid::new_v4().to_string()),
            "timestamp" => return Ok(Utc::now().timestamp().to_string()),
            "timestamp_ms" => return Ok(Utc::now().timestamp_millis().to_string()),
            "now" => return Ok(Utc::now().to_rfc3339()),
            "now_local" => return Ok(Local::now().to_rfc3339()),
            "random_int" => return Ok(rand::random::<u32>().to_string()),
            _ => {}
        }

        // Variáveis de ambiente
        if let Some(rest) = token.strip_prefix("ENV_") {
            return std::env::var(rest)
                .map_err(|_| anyhow!("Missing environment variable '{}'.", rest));
        }

        // Variáveis do contexto
        if let Some(value) = self.variables.get(token) {
            return match value {
                Value::String(s) => Ok(s.clone()),
                primitive => Ok(primitive.to_string()),
            };
        }

        Err(anyhow!("Missing context variable '{}'. Available: {:?}", token, self.variables.keys().collect::<Vec<_>>()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_random_uuid_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("id: ${random_uuid}").unwrap();
        
        // UUID v4 tem formato xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        assert!(result.starts_with("id: "));
        let uuid_part = &result[4..];
        assert_eq!(uuid_part.len(), 36);
        assert!(uuid_part.contains('-'));
    }

    #[test]
    fn test_timestamp_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("ts: ${timestamp}").unwrap();
        
        let ts_part = &result[4..];
        let ts: i64 = ts_part.parse().expect("deve ser número");
        assert!(ts > 1700000000); // Após 2023
    }

    #[test]
    fn test_timestamp_ms_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("ts: ${timestamp_ms}").unwrap();
        
        let ts_part = &result[4..];
        let ts: i64 = ts_part.parse().expect("deve ser número");
        assert!(ts > 1700000000000); // Após 2023 em ms
    }

    #[test]
    fn test_now_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("${now}").unwrap();
        
        // Formato RFC3339: 2024-01-15T12:34:56+00:00
        assert!(result.contains("T"));
        assert!(result.len() > 20);
    }

    #[test]
    fn test_random_int_interpolation() {
        let ctx = Context::new();
        let result1 = ctx.interpolate_str("${random_int}").unwrap();
        let result2 = ctx.interpolate_str("${random_int}").unwrap();
        
        // Ambos devem ser números
        let _: u32 = result1.parse().expect("deve ser número");
        let _: u32 = result2.parse().expect("deve ser número");
        
        // Alta probabilidade de serem diferentes
        // (não garantido, mas extremamente improvável serem iguais)
    }

    #[test]
    fn test_multiple_dynamic_vars() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("uuid=${random_uuid}&ts=${timestamp}").unwrap();
        
        assert!(result.contains("uuid="));
        assert!(result.contains("&ts="));
        assert!(!result.contains("${"));
    }

    #[test]
    fn test_mixed_static_and_dynamic() {
        let mut ctx = Context::new();
        ctx.set("user", Value::String("john".to_string()));
        
        let result = ctx.interpolate_str("user=${user}&session=${random_uuid}").unwrap();
        
        assert!(result.starts_with("user=john&session="));
        assert!(!result.contains("${"));
    }
}
