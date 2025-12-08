//! # GraphQL Executor - Plugin de Exemplo
//!
//! Este módulo demonstra como criar um executor customizado para GraphQL.
//!
//! ## Para desenvolvedores de plugins:
//!
//! Este executor serve como template para criar seus próprios executores.
//! Ele estende as funcionalidades de HTTP para adicionar suporte a GraphQL:
//!
//! - Formatação automática de queries/mutations
//! - Validação de respostas GraphQL
//! - Tratamento de erros GraphQL vs HTTP
//!
//! ## Uso no UTDL:
//!
//! ```json
//! {
//!   "id": "get_user",
//!   "action": "graphql",
//!   "params": {
//!     "endpoint": "/graphql",
//!     "operation": "query",
//!     "query": "query GetUser($id: ID!) { user(id: $id) { name email } }",
//!     "variables": { "id": "123" }
//!   },
//!   "assertions": [
//!     { "type": "json_body", "operator": "eq", "path": "$.data.user.name", "value": "John" }
//!   ]
//! }
//! ```
//!
//! ## Arquitetura:
//!
//! ```text
//! GraphQL Step
//!       │
//!       ▼
//! ┌─────────────────────┐
//! │   GraphqlExecutor   │
//! │  - parse query      │
//! │  - build request    │
//! │  - validate errors  │
//! └──────────┬──────────┘
//!            │
//!            ▼
//! ┌─────────────────────┐
//! │   POST /graphql     │
//! │  Content-Type: JSON │
//! └─────────────────────┘
//! ```

use crate::context::Context;
use crate::executors::StepExecutor;
use crate::protocol::{Step, StepResult, StepStatus};
use anyhow::{anyhow, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde_json::{json, Value};
use std::time::Instant;

/// Executor especializado para requisições GraphQL.
///
/// ## Diferenças do HTTP puro:
///
/// 1. **Request Body**: Sempre JSON com `query`, `variables`, `operationName`
/// 2. **Método**: Sempre POST (por convenção GraphQL)
/// 3. **Erros**: GraphQL pode retornar 200 OK com erros no body
/// 4. **Assertions**: Path `$.data.*` ou `$.errors[*]`
#[derive(Default)]
pub struct GraphqlExecutor {
    client: Client,
    base_url: String,
}

impl GraphqlExecutor {
    /// Cria novo executor GraphQL.
    ///
    /// ## Parâmetros:
    /// - `base_url`: URL base do servidor (ex: "http://localhost:4000")
    #[allow(dead_code)]
    pub fn new(base_url: String) -> Self {
        Self {
            client: Client::new(),
            base_url,
        }
    }

    /// Extrai query GraphQL dos parâmetros do step.
    fn extract_query(params: &Value) -> Result<String> {
        params
            .get("query")
            .and_then(|v| v.as_str())
            .map(String::from)
            .ok_or_else(|| anyhow!("Missing 'query' in GraphQL params"))
    }

    /// Extrai variáveis (opcional).
    fn extract_variables(params: &Value) -> Value {
        params.get("variables").cloned().unwrap_or(json!({}))
    }

    /// Extrai nome da operação (opcional).
    fn extract_operation_name(params: &Value) -> Option<String> {
        params
            .get("operationName")
            .and_then(|v| v.as_str())
            .map(String::from)
    }

    /// Constrói o body da requisição GraphQL.
    fn build_request_body(query: &str, variables: Value, operation_name: Option<String>) -> Value {
        let mut body = json!({
            "query": query,
            "variables": variables
        });

        if let Some(op_name) = operation_name {
            body["operationName"] = json!(op_name);
        }

        body
    }

    /// Verifica se a resposta GraphQL contém erros.
    ///
    /// ## Nota importante:
    /// GraphQL retorna HTTP 200 mesmo com erros de negócio.
    /// Erros aparecem no campo `errors` do body.
    fn check_graphql_errors(response_body: &Value) -> Vec<String> {
        response_body
            .get("errors")
            .and_then(|e| e.as_array())
            .map(|errors| {
                errors
                    .iter()
                    .filter_map(|e| e.get("message").and_then(|m| m.as_str()))
                    .map(String::from)
                    .collect()
            })
            .unwrap_or_default()
    }
}

/// Extrai valor de JSON usando path simplificado ($.data.user.name).
fn jsonpath_select(json: &Value, path: &str) -> Option<Value> {
    let path = path.trim_start_matches("$.");
    let mut current = json;

    for part in path.split('.') {
        // Handle array index: field[0]
        if part.contains('[') {
            let (field, rest) = part.split_once('[').unwrap();
            let idx_str = rest.trim_end_matches(']');

            // First get the field
            if !field.is_empty() {
                current = current.get(field)?;
            }

            // Then get the array index
            if let Ok(idx) = idx_str.parse::<usize>() {
                current = current.get(idx)?;
            } else {
                return None;
            }
        } else {
            current = current.get(part)?;
        }
    }

    Some(current.clone())
}

#[async_trait]
impl StepExecutor for GraphqlExecutor {
    /// Aceita action "graphql" ou "graphql_request".
    fn can_handle(&self, action: &str) -> bool {
        matches!(
            action,
            "graphql" | "graphql_request" | "graphql_query" | "graphql_mutation"
        )
    }

    /// Executa requisição GraphQL.
    ///
    /// ## Fluxo:
    /// 1. Extrai query e variáveis dos params
    /// 2. Constrói request body padrão GraphQL
    /// 3. Faz POST para endpoint
    /// 4. Verifica erros GraphQL
    /// 5. Aplica assertions
    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult> {
        let start = Instant::now();

        // Extrai parâmetros
        let params = &step.params;

        let query = Self::extract_query(params)?;
        let variables = Self::extract_variables(params);
        let operation_name = Self::extract_operation_name(params);

        // Endpoint (default: /graphql)
        let endpoint = params
            .get("endpoint")
            .and_then(|v| v.as_str())
            .unwrap_or("/graphql");

        let url = format!("{}{}", self.base_url, endpoint);

        // Constrói e envia request
        let body = Self::build_request_body(&query, variables, operation_name);

        let response = self
            .client
            .post(&url)
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await?;

        let status_code = response.status().as_u16();
        let response_body: Value = response.json().await.unwrap_or(json!(null));

        // Verifica erros GraphQL
        let graphql_errors = Self::check_graphql_errors(&response_body);

        let mut all_passed = true;
        let mut error_message: Option<String> = None;

        // Adiciona verificação implícita: sem erros GraphQL (se não esperados)
        let expects_errors = step.assertions.iter().any(|x| {
            x.path
                .as_ref()
                .map(|p| p.contains("errors"))
                .unwrap_or(false)
        });

        if !graphql_errors.is_empty() && !expects_errors {
            all_passed = false;
            error_message = Some(format!("GraphQL errors: {:?}", graphql_errors));
        }

        // Processa assertions do step
        for assertion in &step.assertions {
            let passed = match assertion.assertion_type.as_str() {
                "status_code" => {
                    let expected = assertion.value.as_u64().unwrap_or(0) as u16;
                    status_code == expected
                }
                "json_body" => {
                    if let Some(path) = &assertion.path {
                        let actual = jsonpath_select(&response_body, path);
                        match assertion.operator.as_str() {
                            "eq" => actual.as_ref() == Some(&assertion.value),
                            "neq" => actual.as_ref() != Some(&assertion.value),
                            "exists" => actual.is_some(),
                            "not_exists" => actual.is_none(),
                            _ => true,
                        }
                    } else {
                        false
                    }
                }
                _ => true,
            };

            if !passed {
                all_passed = false;
                error_message = Some(format!(
                    "Assertion failed: {} {} {:?}",
                    assertion.assertion_type, assertion.operator, assertion.value
                ));
            }
        }

        // Processa extractions
        for extraction in &step.extract {
            if extraction.source == "body" {
                if let Some(value) = jsonpath_select(&response_body, &extraction.path) {
                    context.set(&extraction.target, value);
                }
            }
        }

        let duration_ms = start.elapsed().as_millis() as u64;

        Ok(StepResult {
            step_id: step.id.clone(),
            status: if all_passed {
                StepStatus::Passed
            } else {
                StepStatus::Failed
            },
            duration_ms,
            attempt: 1,
            error: error_message,
            context_before: None,
            context_after: None,
            extractions: None,
            http_details: None, // TODO: Adicionar detalhes GraphQL futuramente
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_can_handle_graphql_actions() {
        let executor = GraphqlExecutor::new("http://localhost:4000".to_string());

        assert!(executor.can_handle("graphql"));
        assert!(executor.can_handle("graphql_request"));
        assert!(executor.can_handle("graphql_query"));
        assert!(executor.can_handle("graphql_mutation"));
        assert!(!executor.can_handle("http_request"));
    }

    #[test]
    fn test_extract_query() {
        let params = json!({
            "query": "query { users { name } }"
        });

        let query = GraphqlExecutor::extract_query(&params).unwrap();
        assert_eq!(query, "query { users { name } }");
    }

    #[test]
    fn test_extract_query_missing() {
        let params = json!({});
        let result = GraphqlExecutor::extract_query(&params);
        assert!(result.is_err());
    }

    #[test]
    fn test_extract_variables() {
        let params = json!({
            "query": "query GetUser($id: ID!) { user(id: $id) { name } }",
            "variables": { "id": "123" }
        });

        let vars = GraphqlExecutor::extract_variables(&params);
        assert_eq!(vars["id"], "123");
    }

    #[test]
    fn test_extract_variables_default() {
        let params = json!({ "query": "{ users { name } }" });
        let vars = GraphqlExecutor::extract_variables(&params);
        assert_eq!(vars, json!({}));
    }

    #[test]
    fn test_build_request_body() {
        let body = GraphqlExecutor::build_request_body(
            "query { users { name } }",
            json!({"limit": 10}),
            Some("GetUsers".to_string()),
        );

        assert_eq!(body["query"], "query { users { name } }");
        assert_eq!(body["variables"]["limit"], 10);
        assert_eq!(body["operationName"], "GetUsers");
    }

    #[test]
    fn test_check_graphql_errors_none() {
        let response = json!({
            "data": { "user": { "name": "John" } }
        });

        let errors = GraphqlExecutor::check_graphql_errors(&response);
        assert!(errors.is_empty());
    }

    #[test]
    fn test_check_graphql_errors_present() {
        let response = json!({
            "data": null,
            "errors": [
                { "message": "User not found" },
                { "message": "Permission denied" }
            ]
        });

        let errors = GraphqlExecutor::check_graphql_errors(&response);
        assert_eq!(errors.len(), 2);
        assert_eq!(errors[0], "User not found");
        assert_eq!(errors[1], "Permission denied");
    }

    #[test]
    fn test_jsonpath_select_simple() {
        let json = json!({
            "data": {
                "user": {
                    "name": "John",
                    "email": "john@example.com"
                }
            }
        });

        assert_eq!(
            jsonpath_select(&json, "$.data.user.name"),
            Some(json!("John"))
        );
        assert_eq!(
            jsonpath_select(&json, "$.data.user.email"),
            Some(json!("john@example.com"))
        );
    }

    #[test]
    fn test_jsonpath_select_array() {
        let json = json!({
            "data": {
                "users": [
                    { "name": "John" },
                    { "name": "Jane" }
                ]
            }
        });

        assert_eq!(
            jsonpath_select(&json, "$.data.users[0].name"),
            Some(json!("John"))
        );
        assert_eq!(
            jsonpath_select(&json, "$.data.users[1].name"),
            Some(json!("Jane"))
        );
    }

    #[test]
    fn test_jsonpath_select_not_found() {
        let json = json!({ "data": { "user": null } });
        assert_eq!(jsonpath_select(&json, "$.data.nonexistent"), None);
    }
}
