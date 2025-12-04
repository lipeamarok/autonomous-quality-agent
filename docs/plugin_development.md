# Plugin Development Guide

This guide explains how to extend the AQA runner with custom executors (plugins).

## Architecture Overview

The runner uses a **trait-based plugin system** where each executor implements the `StepExecutor` trait:

```rust
#[async_trait]
pub trait StepExecutor: Send + Sync {
    /// Returns true if this executor can handle the given action type.
    fn can_handle(&self, action: &str) -> bool;

    /// Executes a step and returns the result.
    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult>;
}
```

## Creating a Custom Executor

### Step 1: Create the Executor Module

Create a new file in `runner/src/executors/`:

```rust
// runner/src/executors/my_executor.rs

use async_trait::async_trait;
use anyhow::Result;
use crate::context::Context;
use crate::protocol::{Step, StepResult, StepStatus};
use super::StepExecutor;

#[derive(Default)]
pub struct MyExecutor {
    // Add any configuration fields here
}

impl MyExecutor {
    pub fn new() -> Self {
        Self::default()
    }
}

#[async_trait]
impl StepExecutor for MyExecutor {
    fn can_handle(&self, action: &str) -> bool {
        // Define which action types this executor handles
        matches!(action, "my_action" | "my_other_action")
    }

    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult> {
        let start = std::time::Instant::now();

        // 1. Extract parameters from step.params
        let params = step.params.as_ref()
            .ok_or_else(|| anyhow::anyhow!("Missing params"))?;

        // 2. Interpolate variables from context
        let some_value = context.interpolate(
            params.get("key").and_then(|v| v.as_str()).unwrap_or("")
        );

        // 3. Execute your custom logic
        let result = do_something(&some_value)?;

        // 4. Store results in context for later steps
        context.set("my_result", result.clone());

        // 5. Return the step result
        Ok(StepResult {
            step_id: step.id.clone(),
            status: StepStatus::Passed,
            duration_ms: start.elapsed().as_millis() as u64,
            error: None,
            extractions: None,
        })
    }
}
```

### Step 2: Register the Module

Add your module to `runner/src/executors/mod.rs`:

```rust
pub mod http;
pub mod wait;
pub mod graphql;
pub mod my_executor;  // Add this line

pub use http::HttpExecutor;
pub use wait::WaitExecutor;
pub use graphql::GraphqlExecutor;
pub use my_executor::MyExecutor;  // Add this line
```

### Step 3: Register the Executor

Add your executor to the executor list in `runner/src/main.rs`:

```rust
let http_executor = HttpExecutor::new();
let wait_executor = WaitExecutor::new();
let graphql_executor = GraphqlExecutor::default();
let my_executor = MyExecutor::new();  // Add this line

let executors: Vec<Box<dyn StepExecutor + Send + Sync>> = vec![
    Box::new(http_executor),
    Box::new(wait_executor),
    Box::new(graphql_executor),
    Box::new(my_executor),  // Add this line
];
```

## Key Concepts

### The Context

The `Context` struct manages shared state between steps:

```rust
// Set a value
context.set("token", "abc123");

// Get a value
let token = context.get("token");

// Interpolate variables in a string
let url = context.interpolate("https://api.example.com/users/{{user_id}}");

// Extend with multiple values
context.extend(&serde_json::json!({
    "key1": "value1",
    "key2": "value2"
}));
```

### Built-in Interpolation Functions

The context supports these built-in functions:

| Function | Example | Description |
|----------|---------|-------------|
| `{{var}}` | `{{token}}` | Variable lookup |
| `$now()` | `$now()` | Current ISO timestamp |
| `$timestamp()` | `$timestamp()` | Unix timestamp (seconds) |
| `$timestamp_ms()` | `$timestamp_ms()` | Unix timestamp (milliseconds) |
| `$random_uuid()` | `$random_uuid()` | Random UUID v4 |
| `$random_int(min,max)` | `$random_int(1,100)` | Random integer |
| `$base64(text)` | `$base64(user:pass)` | Base64 encode |
| `$sha256(text)` | `$sha256(data)` | SHA-256 hash |
| `$env(VAR)` | `$env(API_KEY)` | Environment variable |

### The Step Structure

```rust
pub struct Step {
    pub id: String,           // Unique step identifier
    pub action: String,       // Action type (e.g., "http", "graphql")
    pub params: Option<Value>,// Step-specific parameters
    pub assert: Vec<Assertion>,    // Assertions to validate
    pub extract: Vec<Extraction>,  // Values to extract
    pub depends_on: Vec<String>,   // Step dependencies
    pub recovery: Option<RecoveryPolicy>,
    pub retry: Option<RetryPolicy>,
    pub timeout_ms: Option<u64>,
    pub description: Option<String>,
    pub tags: Vec<String>,
}
```

### StepResult Structure

```rust
pub struct StepResult {
    pub step_id: String,
    pub status: StepStatus,  // Passed, Failed, Skipped, Error
    pub duration_ms: u64,
    pub error: Option<String>,
    pub extractions: Option<HashMap<String, Value>>,
}
```

## Example: GraphQL Executor

See `runner/src/executors/graphql.rs` for a complete example of a custom executor that:

1. Handles `graphql` and `graphql.query` actions
2. Builds GraphQL request bodies
3. Executes HTTP requests
4. Validates GraphQL-specific errors
5. Extracts values using JSONPath

### Usage in UTDL

```json
{
  "id": "get_user",
  "action": "graphql",
  "params": {
    "url": "{{base_url}}/graphql",
    "query": "query GetUser($id: ID!) { user(id: $id) { name email } }",
    "variables": { "id": "{{user_id}}" }
  },
  "extract": [
    { "name": "user_name", "source": "body", "path": "$.data.user.name" }
  ],
  "assert": [
    { "path": "$.data.user", "operator": "exists" }
  ]
}
```

## Best Practices

### 1. Error Handling

Return meaningful errors with context:

```rust
use anyhow::Context;

let response = client.post(&url)
    .json(&body)
    .send()
    .await
    .context("Failed to send request")?;
```

### 2. Timeout Handling

Respect the step's timeout configuration:

```rust
let timeout = step.timeout_ms.unwrap_or(30_000);
let response = tokio::time::timeout(
    Duration::from_millis(timeout),
    client.post(&url).send()
).await
.context("Request timed out")??;
```

### 3. Logging

Use `tracing` for structured logging:

```rust
use tracing::{info, debug, warn, error};

info!(step_id = %step.id, action = %step.action, "Executing step");
debug!(url = %url, "Sending request");
warn!(error = ?e, "Retrying after error");
```

### 4. Testing

Add unit tests for your executor:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_can_handle() {
        let executor = MyExecutor::default();
        assert!(executor.can_handle("my_action"));
        assert!(!executor.can_handle("unknown"));
    }

    #[tokio::test]
    async fn test_execute_success() {
        let executor = MyExecutor::default();
        let step = Step { /* ... */ };
        let mut context = Context::new();
        
        let result = executor.execute(&step, &mut context).await.unwrap();
        assert_eq!(result.status, StepStatus::Passed);
    }
}
```

## Available Executors

| Executor | Actions | Description |
|----------|---------|-------------|
| `HttpExecutor` | `http`, `http.get`, `http.post`, etc. | HTTP/REST API calls |
| `WaitExecutor` | `wait`, `sleep` | Delays and polling |
| `GraphqlExecutor` | `graphql`, `graphql.query`, `graphql.mutation` | GraphQL API calls |

## Future Plugin API

We're working on a dynamic plugin system that will allow:

- Loading plugins from shared libraries (.so/.dll)
- Plugin discovery and hot-reloading
- Plugin configuration via environment variables
- Plugin marketplace integration

Stay tuned for updates!
