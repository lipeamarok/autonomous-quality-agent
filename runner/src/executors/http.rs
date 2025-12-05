//! # Executor HTTP - Requisições HTTP com Validação
//!
//! Este é o executor mais importante do Runner. Ele executa requisições HTTP
//! e valida as respostas usando assertions.
//!
//! ## O que este executor faz?
//!
//! 1. **Constrói a requisição** (método, URL, headers, body)
//! 2. **Interpola variáveis** em headers e body
//! 3. **Executa a requisição** usando o cliente HTTP (reqwest)
//! 4. **Valida a resposta** com assertions (status, body, headers, latency)
//! 5. **Extrai dados** da resposta para uso em steps seguintes
//!
//! ## Fluxo de execução:
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                        execute()                                 │
//! └───────────────────────────┬─────────────────────────────────────┘
//!                             │
//!    ┌────────────────────────┼────────────────────────────────┐
//!    ▼                        ▼                                ▼
//! ┌──────────┐          ┌──────────┐                    ┌──────────┐
//! │ 1. Parse │          │ 2. Build │                    │ 3. Send  │
//! │  params  │    →     │ request  │         →          │ request  │
//! └──────────┘          └──────────┘                    └──────────┘
//!                                                              │
//!    ┌─────────────────────────────────────────────────────────┘
//!    ▼
//! ┌──────────────────────────────────────────────────────────────┐
//! │ 4. Validate   │ 5. Extract   │ 6. Return StepResult          │
//! │  assertions   │    data      │                               │
//! └──────────────────────────────────────────────────────────────┘
//! ```

use super::StepExecutor;
use crate::context::Context;
use crate::extractors::{ExtractionResult, Extractor};
use crate::protocol::{Assertion, Extraction, Step, StepResult, StepStatus};
use anyhow::{anyhow, Result};
use async_trait::async_trait;
use regex::Regex;
use reqwest::{header::HeaderMap, Client, Method};
use serde_json::Value;
use std::collections::HashMap;
use std::time::Instant;

// ============================================================================
// FUNÇÕES AUXILIARES
// ============================================================================

/// Compara dois valores JSON numéricos usando uma função de comparação.
///
/// Esta função é usada para assertions que comparam números (gt, lt, gte, lte).
///
/// ## Parâmetros:
/// - `actual`: Valor obtido da resposta
/// - `expected`: Valor esperado na assertion
/// - `cmp`: Função de comparação (ex: |a, b| a > b)
///
/// ## Retorno:
/// - `true` se a comparação passar
/// - `false` se falhar ou os valores não forem numéricos
fn compare_values<F>(actual: &Value, expected: &Value, cmp: F) -> bool
where
    F: Fn(f64, f64) -> bool,
{
    match (actual, expected) {
        (Value::Number(a), Value::Number(b)) => {
            // Tenta converter ambos para f64 para comparação.
            if let (Some(a_f), Some(b_f)) = (a.as_f64(), b.as_f64()) {
                cmp(a_f, b_f)
            } else {
                false
            }
        }
        _ => false,
    }
}

// ============================================================================
// CONTEXTO DE RESPOSTA
// ============================================================================

/// Estrutura que agrupa informações da resposta HTTP para validação.
///
/// Usada internamente por `validate_assertions` para ter acesso
/// a todos os dados da resposta em um só lugar.
struct ResponseContext<'a> {
    /// Código de status HTTP (200, 201, 404, 500, etc.)
    status: u16,

    /// Body da resposta parseado como JSON.
    /// Será `Value::Null` se não for JSON válido.
    body: &'a Value,

    /// Headers da resposta.
    headers: &'a HeaderMap,

    /// Tempo de resposta em milissegundos.
    duration_ms: u64,
}

// ============================================================================
// HTTP EXECUTOR
// ============================================================================

/// Executor responsável por ações "http_request".
///
/// Usa a biblioteca `reqwest` para fazer requisições HTTP assíncronas.
///
/// ## Recursos:
/// - Suporte a todos os métodos HTTP (GET, POST, PUT, DELETE, PATCH, etc.)
/// - Interpolação de variáveis em headers, body e path
/// - Validação completa via assertions
/// - Extração de dados da resposta
/// - Instrumentação OpenTelemetry
pub struct HttpExecutor {
    /// Cliente HTTP reutilizável.
    ///
    /// Reusar o cliente é mais eficiente porque mantém
    /// o connection pool entre requisições.
    client: Client,
}

impl HttpExecutor {
    /// Cria um novo HttpExecutor.
    ///
    /// O cliente HTTP é criado uma vez e reutilizado para todas as requisições.
    pub fn new() -> Self {
        Self {
            client: Client::new(),
        }
    }

    /// Valida todas as assertions contra a resposta.
    ///
    /// Itera sobre cada assertion definida no step e verifica
    /// se a resposta atende aos critérios.
    ///
    /// ## Parâmetros:
    /// - `assertions`: Lista de assertions do step
    /// - `ctx`: Contexto da resposta (status, body, headers, latency)
    ///
    /// ## Retorno:
    /// - `None` se todas as assertions passaram
    /// - `Some(String)` com a mensagem de erro da primeira que falhou
    fn validate_assertions(
        &self,
        assertions: &[Assertion],
        ctx: &ResponseContext,
    ) -> Option<String> {
        for assertion in assertions {
            match assertion.assertion_type.as_str() {
                // ============================================================
                // ASSERTION: STATUS_CODE
                // ============================================================
                // Valida o código de status HTTP da resposta.
                // Exemplo: { "type": "status_code", "operator": "eq", "value": 200 }
                "status_code" => {
                    let expected = assertion.value.as_u64().unwrap_or(0) as u16;
                    let passed = match assertion.operator.as_str() {
                        "eq" => ctx.status == expected,
                        "neq" => ctx.status != expected,
                        "lt" => ctx.status < expected,
                        "gt" => ctx.status > expected,
                        "lte" | "le" => ctx.status <= expected,
                        "gte" | "ge" => ctx.status >= expected,
                        _ => false,
                    };
                    if !passed {
                        return Some(format!(
                            "Assertion failed: status_code {} {} (got {})",
                            assertion.operator, expected, ctx.status
                        ));
                    }
                }

                // ============================================================
                // ASSERTION: STATUS_RANGE
                // ============================================================
                // Valida que o status HTTP está em um range (2xx, 3xx, 4xx, 5xx).
                // Exemplo: { "type": "status_range", "operator": "eq", "value": "2xx" }
                // Também suporta ranges customizados: "4xx", "5xx", etc.
                "status_range" => {
                    let range_str = assertion.value.as_str().unwrap_or("");
                    
                    // Determina o range esperado
                    let (min_status, max_status) = match range_str.to_lowercase().as_str() {
                        "1xx" => (100, 199),
                        "2xx" | "success" => (200, 299),
                        "3xx" | "redirect" => (300, 399),
                        "4xx" | "client_error" => (400, 499),
                        "5xx" | "server_error" => (500, 599),
                        _ => {
                            // Tenta parsear como range customizado "NNN-NNN"
                            if let Some((min_str, max_str)) = range_str.split_once('-') {
                                let min = min_str.trim().parse::<u16>().unwrap_or(0);
                                let max = max_str.trim().parse::<u16>().unwrap_or(0);
                                (min, max)
                            } else {
                                (0, 0) // Range inválido
                            }
                        }
                    };

                    let in_range = ctx.status >= min_status && ctx.status <= max_status;
                    let passed = match assertion.operator.as_str() {
                        "eq" | "in" => in_range,
                        "neq" | "not_in" => !in_range,
                        _ => in_range, // Default: eq
                    };

                    if !passed {
                        return Some(format!(
                            "Assertion failed: status_range {} '{}' ({}-{}) (got {})",
                            assertion.operator, range_str, min_status, max_status, ctx.status
                        ));
                    }
                }

                // ============================================================
                // ASSERTION: JSON_BODY
                // ============================================================
                // Valida um campo específico do body JSON.
                // Exemplo: { "type": "json_body", "path": "data.id", "operator": "eq", "value": 123 }
                "json_body" => {
                    if let Some(path) = &assertion.path {
                        // Remove prefixo $. do JSONPath se presente
                        let clean_path = path.strip_prefix("$.").unwrap_or(path);

                        // Converte o path para formato JSON Pointer.
                        // "data.user.id" → "/data/user/id"
                        let pointer = if clean_path.starts_with('/') {
                            clean_path.to_string()
                        } else {
                            format!("/{}", clean_path.replace('.', "/"))
                        };

                        // Tenta encontrar o valor no body usando JSON Pointer.
                        if let Some(actual) = ctx.body.pointer(&pointer) {
                            let passed = match assertion.operator.as_str() {
                                "eq" => actual == &assertion.value,
                                "neq" => actual != &assertion.value,
                                "contains" => actual
                                    .as_str()
                                    .map(|s| {
                                        assertion
                                            .value
                                            .as_str()
                                            .map(|needle| s.contains(needle))
                                            .unwrap_or(false)
                                    })
                                    .unwrap_or(false),
                                // ========================================================
                                // OPERADOR: MATCHES_REGEX
                                // ========================================================
                                // Valida que o valor corresponde a uma expressão regular.
                                // Exemplo: { "operator": "matches_regex", "value": "^[A-Z]{2}\\d{4}$" }
                                "matches_regex" | "regex" => {
                                    if let (Some(actual_str), Some(pattern)) = 
                                        (actual.as_str(), assertion.value.as_str()) 
                                    {
                                        match Regex::new(pattern) {
                                            Ok(re) => re.is_match(actual_str),
                                            Err(_) => {
                                                tracing::warn!(
                                                    pattern = %pattern,
                                                    "Invalid regex pattern in assertion"
                                                );
                                                false
                                            }
                                        }
                                    } else {
                                        false
                                    }
                                }
                                "exists" => true,      // Se chegou aqui, existe
                                "not_exists" => false, // Se chegou aqui, existe → falha
                                "gt" => compare_values(actual, &assertion.value, |a, b| a > b),
                                "lt" => compare_values(actual, &assertion.value, |a, b| a < b),
                                "gte" | "ge" => {
                                    compare_values(actual, &assertion.value, |a, b| a >= b)
                                }
                                "lte" | "le" => {
                                    compare_values(actual, &assertion.value, |a, b| a <= b)
                                }
                                _ => false,
                            };

                            if !passed {
                                return Some(format!(
                                    "Assertion failed: json_body '{}' {} {} (got {})",
                                    path, assertion.operator, assertion.value, actual
                                ));
                            }
                        } else {
                            // O path não foi encontrado no body.
                            if assertion.operator == "not_exists" {
                                continue; // OK, não existe como esperado
                            }
                            if assertion.operator == "exists" {
                                return Some(format!(
                                    "Assertion failed: path '{}' should exist but was not found",
                                    path
                                ));
                            }
                            return Some(format!(
                                "Assertion failed: path '{}' not found in response body",
                                path
                            ));
                        }
                    }
                }

                // ============================================================
                // ASSERTION: HEADER
                // ============================================================
                // Valida um header da resposta HTTP.
                // Exemplo: { "type": "header", "path": "Content-Type", "operator": "contains", "value": "json" }
                "header" => {
                    if let Some(header_name) = &assertion.path {
                        // Tenta obter o valor do header.
                        let header_value =
                            ctx.headers.get(header_name).and_then(|v| v.to_str().ok());

                        match assertion.operator.as_str() {
                            "exists" => {
                                if header_value.is_none() {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should exist",
                                        header_name
                                    ));
                                }
                            }
                            "not_exists" => {
                                if header_value.is_some() {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should not exist",
                                        header_name
                                    ));
                                }
                            }
                            "eq" => {
                                let expected = assertion.value.as_str().unwrap_or("");
                                if header_value != Some(expected) {
                                    return Some(format!(
                                        "Assertion failed: header '{}' {} '{}' (got '{}')",
                                        header_name,
                                        assertion.operator,
                                        expected,
                                        header_value.unwrap_or("<missing>")
                                    ));
                                }
                            }
                            "neq" => {
                                let expected = assertion.value.as_str().unwrap_or("");
                                if header_value == Some(expected) {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should not equal '{}'",
                                        header_name, expected
                                    ));
                                }
                            }
                            "contains" => {
                                let needle = assertion.value.as_str().unwrap_or("");
                                let contains =
                                    header_value.map(|v| v.contains(needle)).unwrap_or(false);
                                if !contains {
                                    return Some(format!(
                                        "Assertion failed: header '{}' should contain '{}' (got '{}')",
                                        header_name, needle, header_value.unwrap_or("<missing>")
                                    ));
                                }
                            }
                            _ => {}
                        }
                    }
                }

                // ============================================================
                // ASSERTION: LATENCY
                // ============================================================
                // Valida o tempo de resposta da requisição.
                // Exemplo: { "type": "latency", "operator": "lt", "value": 500 }
                "latency" => {
                    let expected = assertion.value.as_u64().unwrap_or(0);
                    let passed = match assertion.operator.as_str() {
                        "lt" => ctx.duration_ms < expected,
                        "lte" | "le" => ctx.duration_ms <= expected,
                        "gt" => ctx.duration_ms > expected,
                        "gte" | "ge" => ctx.duration_ms >= expected,
                        "eq" => ctx.duration_ms == expected,
                        _ => false,
                    };
                    if !passed {
                        return Some(format!(
                            "Assertion failed: latency {} {}ms (got {}ms)",
                            assertion.operator, expected, ctx.duration_ms
                        ));
                    }
                }

                // Tipo de assertion desconhecido.
                _ => {
                    tracing::warn!(
                        assertion_type = %assertion.assertion_type,
                        "Unknown assertion type, skipping"
                    );
                }
            }
        }

        // Todas as assertions passaram.
        None
    }

    /// Aplica as regras de extração para salvar dados da resposta no contexto.
    ///
    /// Usa o módulo `extractors` para processar cada regra de extração
    /// e retorna resultados estruturados para o relatório.
    ///
    /// ## Parâmetros:
    /// - `extracts`: Lista de regras de extração
    /// - `body`: Body JSON da resposta
    /// - `headers`: Headers da resposta
    /// - `context`: Contexto onde salvar os valores extraídos
    ///
    /// ## Retorno:
    /// Lista de resultados de extração (para inclusão no relatório)
    fn apply_extractions(
        &self,
        extracts: &[Extraction],
        body: &Value,
        headers: &HeaderMap,
        context: &mut Context,
    ) -> Vec<ExtractionResult> {
        // Converte HeaderMap para HashMap<String, String> para o Extractor
        let headers_map: HashMap<String, String> = headers
            .iter()
            .filter_map(|(k, v)| {
                v.to_str()
                    .ok()
                    .map(|v_str| (k.as_str().to_string(), v_str.to_string()))
            })
            .collect();

        // Usa o módulo Extractor para processar
        let (results, extracted_values) = Extractor::process(extracts, Some(body), &headers_map);

        // Popula o contexto com os valores extraídos
        for (key, value) in extracted_values {
            context.set(key, value);
        }

        // Loga resultados das extrações
        for result in &results {
            if result.success {
                tracing::debug!(
                    target = %result.target,
                    source = %result.source,
                    path = %result.path,
                    "Extraction succeeded"
                );
            } else {
                tracing::warn!(
                    target = %result.target,
                    source = %result.source,
                    path = %result.path,
                    error = %result.error.as_deref().unwrap_or("unknown"),
                    "Extraction failed"
                );
            }
        }

        results
    }
}

// ============================================================================
// IMPLEMENTAÇÃO DO TRAIT STEP EXECUTOR
// ============================================================================

#[async_trait]
impl StepExecutor for HttpExecutor {
    /// Retorna true se a action for "http_request".
    fn can_handle(&self, action: &str) -> bool {
        action == "http_request"
    }

    /// Executa uma requisição HTTP.
    ///
    /// Este método é instrumentado com OpenTelemetry para gerar spans
    /// com atributos da requisição e resposta.
    #[tracing::instrument(
        name = "http_request",
        skip_all,
        fields(
            step.id = %step.id,
            http.method = tracing::field::Empty,
            http.url = tracing::field::Empty,
            http.status_code = tracing::field::Empty,
            http.duration_ms = tracing::field::Empty,
            otel.kind = "client"
        )
    )]
    async fn execute(&self, step: &Step, context: &mut Context) -> Result<StepResult> {
        let span = tracing::Span::current();
        let start_time = Instant::now();

        // ====================================================================
        // SNAPSHOT: CONTEXTO ANTES DA EXECUÇÃO
        // ====================================================================
        let context_before = context.variables.clone();

        // ====================================================================
        // PASSO 1: PARSE DOS PARÂMETROS
        // ====================================================================

        let params = &step.params;

        // Extrai o método HTTP (GET, POST, PUT, DELETE, etc.)
        let method_str = params
            .get("method")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("Missing 'method' in params"))?;

        // Extrai o path da requisição.
        let path_str = params
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("Missing 'path' in params"))?;

        // Interpola variáveis no path.
        let interpolated_path = context.interpolate_str(path_str)?;

        // ====================================================================
        // PASSO 2: CONSTRUÇÃO DA URL
        // ====================================================================

        // Se o path já é uma URL completa, usa diretamente.
        // Senão, combina com a base_url do contexto.
        let url = if interpolated_path.starts_with("http") {
            interpolated_path
        } else {
            let base = context
                .get("base_url")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            format!("{}{}", base.trim_end_matches('/'), interpolated_path)
        };

        // Converte a string do método para o enum Method.
        let method = Method::from_bytes(method_str.as_bytes())
            .map_err(|e| anyhow!("Invalid HTTP method: {}", e))?;

        // Registra atributos no span OTEL.
        span.record("http.method", method_str);
        span.record("http.url", &url);

        // ====================================================================
        // PASSO 3: CONSTRUÇÃO DA REQUISIÇÃO
        // ====================================================================

        let mut request_builder = self.client.request(method, &url);

        // Adiciona headers (com interpolação de variáveis).
        if let Some(headers) = params.get("headers").and_then(|h| h.as_object()) {
            for (k, v) in headers {
                if let Some(v_str) = v.as_str() {
                    let value = context.interpolate_str(v_str)?;
                    request_builder = request_builder.header(k, value);
                }
            }
        }

        // Adiciona body (com interpolação recursiva).
        if let Some(body) = params.get("body") {
            let resolved = context.interpolate_value(body)?;
            request_builder = request_builder.json(&resolved);
        }

        // ====================================================================
        // PASSO 4: EXECUÇÃO DA REQUISIÇÃO
        // ====================================================================

        let response = request_builder.send().await;
        let duration = start_time.elapsed().as_millis() as u64;

        // ====================================================================
        // PASSO 5: PROCESSAMENTO DA RESPOSTA
        // ====================================================================

        match response {
            Ok(resp) => {
                let status = resp.status().as_u16();
                let headers = resp.headers().clone();
                let raw_body = resp.text().await.unwrap_or_default();
                let body_json: Value = serde_json::from_str(&raw_body).unwrap_or(Value::Null);

                // Registra atributos da resposta no span OTEL.
                span.record("http.status_code", status as i64);
                span.record("http.duration_ms", duration as i64);

                tracing::info!(
                    method = %method_str,
                    %url,
                    status,
                    duration_ms = duration,
                    "HTTP step finished"
                );

                // Cria o contexto de resposta para validação.
                let response_ctx = ResponseContext {
                    status,
                    body: &body_json,
                    headers: &headers,
                    duration_ms: duration,
                };

                // Valida as assertions.
                if let Some(error_msg) = self.validate_assertions(&step.assertions, &response_ctx) {
                    tracing::warn!(error = %error_msg, "Assertion failed");
                    return Ok(StepResult {
                        step_id: step.id.clone(),
                        status: StepStatus::Failed,
                        duration_ms: duration,
                        error: Some(error_msg),
                        context_before: Some(context_before),
                        context_after: Some(context.variables.clone()),
                        extractions: None,
                    });
                }

                // Aplica as extrações.
                let extraction_results =
                    self.apply_extractions(&step.extract, &body_json, &headers, context);

                // Captura contexto após extrações
                let context_after = context.variables.clone();

                // Retorna sucesso.
                Ok(StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Passed,
                    duration_ms: duration,
                    error: None,
                    context_before: Some(context_before),
                    context_after: Some(context_after),
                    extractions: if extraction_results.is_empty() {
                        None
                    } else {
                        Some(extraction_results)
                    },
                })
            }
            Err(e) => {
                // Erro na requisição (rede, DNS, timeout, etc.)
                tracing::error!(error = %e, "HTTP request failed");
                Ok(StepResult {
                    step_id: step.id.clone(),
                    status: StepStatus::Failed,
                    duration_ms: duration,
                    error: Some(e.to_string()),
                    context_before: Some(context_before),
                    context_after: Some(context.variables.clone()),
                    extractions: None,
                })
            }
        }
    }
}

// ============================================================================
// TESTES UNITÁRIOS
// ============================================================================
#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::Assertion;
    use serde_json::json;

    /// Cria um HttpExecutor para testes
    fn create_test_executor() -> HttpExecutor {
        HttpExecutor::new()
    }

    // ========================================================================
    // Testes: status_code assertions
    // ========================================================================

    #[test]
    fn test_status_code_eq_pass() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_code".to_string(),
            operator: "eq".to_string(),
            value: json!(200),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Assertion should pass");
    }

    #[test]
    fn test_status_code_eq_fail() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 404,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_code".to_string(),
            operator: "eq".to_string(),
            value: json!(200),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_some(), "Assertion should fail");
        assert!(result.unwrap().contains("404"));
    }

    // ========================================================================
    // Testes: status_range assertions
    // ========================================================================

    #[test]
    fn test_status_range_2xx_pass() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("2xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 200 should be in 2xx range");
    }

    #[test]
    fn test_status_range_2xx_with_201() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 201,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("2xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 201 should be in 2xx range");
    }

    #[test]
    fn test_status_range_2xx_fail() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 404,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("2xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_some(), "Status 404 should NOT be in 2xx range");
    }

    #[test]
    fn test_status_range_4xx_pass() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 404,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("4xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 404 should be in 4xx range");
    }

    #[test]
    fn test_status_range_5xx_pass() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 500,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("5xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 500 should be in 5xx range");
    }

    #[test]
    fn test_status_range_success_alias() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 204,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("success"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 204 should match 'success' alias");
    }

    #[test]
    fn test_status_range_client_error_alias() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 422,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("client_error"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 422 should match 'client_error' alias");
    }

    #[test]
    fn test_status_range_not_in() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "not_in".to_string(),
            value: json!("4xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 200 should NOT be in 4xx range");
    }

    #[test]
    fn test_status_range_custom_range() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 250,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("200-299"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 250 should be in custom range 200-299");
    }

    #[test]
    fn test_status_range_boundary_lower() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 400,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("4xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 400 (lower boundary) should be in 4xx range");
    }

    #[test]
    fn test_status_range_boundary_upper() {
        let executor = create_test_executor();
        let body = json!({});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 499,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "status_range".to_string(),
            operator: "eq".to_string(),
            value: json!("4xx"),
            path: None,
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Status 499 (upper boundary) should be in 4xx range");
    }

    // ========================================================================
    // Testes: matches_regex assertions
    // ========================================================================

    #[test]
    fn test_matches_regex_simple() {
        let executor = create_test_executor();
        let body = json!({"code": "AB1234"});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "json_body".to_string(),
            operator: "matches_regex".to_string(),
            value: json!("^[A-Z]{2}\\d{4}$"),
            path: Some("code".to_string()),
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Code 'AB1234' should match pattern ^[A-Z]{{2}}\\d{{4}}$");
    }

    #[test]
    fn test_matches_regex_fail() {
        let executor = create_test_executor();
        let body = json!({"code": "abc123"});  // Lowercase, invalid
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "json_body".to_string(),
            operator: "matches_regex".to_string(),
            value: json!("^[A-Z]{2}\\d{4}$"),
            path: Some("code".to_string()),
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_some(), "Code 'abc123' should NOT match pattern");
    }

    #[test]
    fn test_matches_regex_email() {
        let executor = create_test_executor();
        let body = json!({"email": "user@example.com"});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "json_body".to_string(),
            operator: "matches_regex".to_string(),
            value: json!(r"^[\w.-]+@[\w.-]+\.\w+$"),
            path: Some("email".to_string()),
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "Email should match basic email pattern");
    }

    #[test]
    fn test_matches_regex_uuid() {
        let executor = create_test_executor();
        let body = json!({"id": "550e8400-e29b-41d4-a716-446655440000"});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "json_body".to_string(),
            operator: "regex".to_string(),  // Test alias
            value: json!("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
            path: Some("id".to_string()),
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_none(), "UUID should match UUID pattern");
    }

    #[test]
    fn test_matches_regex_invalid_pattern() {
        let executor = create_test_executor();
        let body = json!({"code": "test"});
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "json_body".to_string(),
            operator: "matches_regex".to_string(),
            value: json!("([invalid"),  // Invalid regex
            path: Some("code".to_string()),
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_some(), "Invalid regex should fail assertion");
    }

    #[test]
    fn test_matches_regex_on_non_string() {
        let executor = create_test_executor();
        let body = json!({"count": 42});  // Number, not string
        let headers = HeaderMap::new();
        let ctx = ResponseContext {
            status: 200,
            body: &body,
            headers: &headers,
            duration_ms: 100,
        };
        let assertions = vec![Assertion {
            assertion_type: "json_body".to_string(),
            operator: "matches_regex".to_string(),
            value: json!("\\d+"),
            path: Some("count".to_string()),
        }];
        
        let result = executor.validate_assertions(&assertions, &ctx);
        assert!(result.is_some(), "Regex on non-string should fail");
    }
}
