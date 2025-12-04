//! # Módulo de Extração - Captura de Dados das Respostas HTTP
//!
//! Este módulo implementa a lógica de extração de dados das respostas HTTP
//! para popular o contexto de execução.
//!
//! ## Para todos entenderem:
//!
//! Imagine que você faz login numa API e recebe um token na resposta.
//! Você precisa usar esse token nos próximos requests. A extração faz isso:
//!
//! 1. **Recebe** a resposta HTTP (body JSON, headers, status)
//! 2. **Busca** o dado usando JSONPath, regex ou nome do header
//! 3. **Salva** no contexto com o nome especificado em `target`
//! 4. **Disponibiliza** para interpolação em steps seguintes
//!
//! ## Exemplo de Fluxo:
//!
//! ```text
//! Step 1: POST /login
//! Resposta: { "data": { "token": "abc123" } }
//! Extração: source=body, path=$.data.token, target=auth_token
//! Resultado: ctx.set("auth_token", "abc123")
//!
//! Step 2: GET /profile
//! Header: Authorization: Bearer ${auth_token}
//! Interpolado: Authorization: Bearer abc123
//! ```
//!
//! ## Tipos de Extração Suportados:
//!
//! | Source | Path | Descrição |
//! |--------|------|-----------|
//! | `body` | JSONPath | Extrai de JSON: `$.data.token` |
//! | `header` | Nome | Extrai header: `X-Request-Id` |
//! | `body` | Regex | Extrai com regex: `token=(\w+)` |

use anyhow::{anyhow, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

use crate::errors::ErrorCode;
use crate::protocol::Extraction;

// ============================================================================
// TIPOS DE VALOR
// ============================================================================

/// Tipo do valor extraído, para validação e debug.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ValueType {
    /// Valor string
    String,
    /// Valor numérico (inteiro ou float)
    Number,
    /// Valor booleano
    Boolean,
    /// Array de valores
    Array,
    /// Objeto JSON
    Object,
    /// Valor null
    Null,
}

impl ValueType {
    /// Detecta o tipo de um serde_json::Value.
    pub fn from_value(value: &Value) -> Self {
        match value {
            Value::String(_) => ValueType::String,
            Value::Number(_) => ValueType::Number,
            Value::Bool(_) => ValueType::Boolean,
            Value::Array(_) => ValueType::Array,
            Value::Object(_) => ValueType::Object,
            Value::Null => ValueType::Null,
        }
    }
}

// ============================================================================
// ESTRUTURAS DE RESULTADO
// ============================================================================

/// Resultado de uma operação de extração.
///
/// Contém informações sobre o sucesso ou falha da extração,
/// útil para debugging e relatórios detalhados.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractionResult {
    /// Nome da variável de destino (target).
    pub target: String,

    /// Fonte da extração: "body", "header" ou "status_code".
    pub source: String,

    /// Caminho usado para extração (JSONPath, regex ou nome do header).
    pub path: String,

    /// Valor extraído, se sucesso.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<Value>,

    /// Tipo do valor extraído (string, number, boolean, array, object).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value_type: Option<ValueType>,

    /// Mensagem de erro, se falhou.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,

    /// Código de erro estruturado (E3010, E3011, etc).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_code: Option<String>,

    /// Se a extração foi bem-sucedida.
    pub success: bool,

    /// Se esta extração era crítica (deve abortar em caso de falha).
    #[serde(default)]
    pub is_critical: bool,
}

impl ExtractionResult {
    /// Cria um resultado de sucesso.
    pub fn success(target: String, source: String, path: String, value: Value) -> Self {
        let value_type = Some(ValueType::from_value(&value));
        Self {
            target,
            source,
            path,
            value: Some(value),
            value_type,
            error: None,
            error_code: None,
            success: true,
            is_critical: false,
        }
    }

    /// Cria um resultado de sucesso com flag de crítico.
    #[allow(dead_code)]
    pub fn success_critical(
        target: String,
        source: String,
        path: String,
        value: Value,
        critical: bool,
    ) -> Self {
        let value_type = Some(ValueType::from_value(&value));
        Self {
            target,
            source,
            path,
            value: Some(value),
            value_type,
            error: None,
            error_code: None,
            success: true,
            is_critical: critical,
        }
    }

    /// Cria um resultado de falha.
    pub fn failure(target: String, source: String, path: String, error: String) -> Self {
        Self {
            target,
            source,
            path,
            value: None,
            value_type: None,
            error: Some(error),
            error_code: None,
            success: false,
            is_critical: false,
        }
    }

    /// Cria um resultado de falha com flag de crítico.
    #[allow(dead_code)]
    pub fn failure_critical(
        target: String,
        source: String,
        path: String,
        error: String,
        critical: bool,
    ) -> Self {
        Self {
            target,
            source,
            path,
            value: None,
            value_type: None,
            error: Some(error),
            error_code: None,
            success: false,
            is_critical: critical,
        }
    }

    /// Cria um resultado de falha com código de erro estruturado.
    #[allow(dead_code)]
    pub fn failure_with_code(
        target: String,
        source: String,
        path: String,
        error: String,
        code: ErrorCode,
    ) -> Self {
        Self {
            target,
            source,
            path,
            value: None,
            value_type: None,
            error: Some(error),
            error_code: Some(code.formatted()),
            success: false,
            is_critical: false,
        }
    }

    /// Cria um resultado de falha com código de erro e flag de crítico.
    #[allow(dead_code)]
    pub fn failure_with_code_critical(
        target: String,
        source: String,
        path: String,
        error: String,
        code: ErrorCode,
        critical: bool,
    ) -> Self {
        Self {
            target,
            source,
            path,
            value: None,
            value_type: None,
            error: Some(error),
            error_code: Some(code.formatted()),
            success: false,
            is_critical: critical,
        }
    }

    /// Verifica se a falha deve abortar a execução.
    #[allow(dead_code)]
    pub fn should_abort(&self) -> bool {
        !self.success && self.is_critical
    }
}

// ============================================================================
// EXTRATOR PRINCIPAL
// ============================================================================

/// Motor de extração de dados.
///
/// Processa regras de extração e retorna resultados estruturados.
/// Suporta múltiplas fontes e métodos de extração.
pub struct Extractor;

impl Extractor {
    /// Processa todas as extrações de um step.
    ///
    /// ## Parâmetros:
    /// - `extractions`: Lista de regras de extração do step
    /// - `response_body`: Body da resposta HTTP (JSON)
    /// - `response_headers`: Headers da resposta HTTP
    /// - `status_code`: Código de status HTTP (para extração de status)
    ///
    /// ## Retorno:
    /// - Lista de resultados (sucesso ou falha para cada extração)
    /// - HashMap com os valores extraídos com sucesso (para popular o Context)
    /// - bool indicando se alguma extração crítica falhou
    pub fn process(
        extractions: &[Extraction],
        response_body: Option<&Value>,
        response_headers: &HashMap<String, String>,
    ) -> (Vec<ExtractionResult>, HashMap<String, Value>) {
        Self::process_with_status(extractions, response_body, response_headers, None)
    }

    /// Processa extrações com suporte a status_code.
    pub fn process_with_status(
        extractions: &[Extraction],
        response_body: Option<&Value>,
        response_headers: &HashMap<String, String>,
        status_code: Option<u16>,
    ) -> (Vec<ExtractionResult>, HashMap<String, Value>) {
        let mut results = Vec::with_capacity(extractions.len());
        let mut extracted_values = HashMap::new();

        for extraction in extractions {
            let result =
                Self::extract_single(extraction, response_body, response_headers, status_code);

            // Se sucesso, adiciona ao HashMap de valores
            if result.success {
                if let Some(ref value) = result.value {
                    extracted_values.insert(result.target.clone(), value.clone());
                }
            }

            results.push(result);
        }

        (results, extracted_values)
    }

    /// Verifica se alguma extração crítica falhou.
    #[allow(dead_code)]
    pub fn has_critical_failure(results: &[ExtractionResult]) -> bool {
        results.iter().any(|r| r.should_abort())
    }

    /// Processa uma única extração.
    fn extract_single(
        extraction: &Extraction,
        response_body: Option<&Value>,
        response_headers: &HashMap<String, String>,
        status_code: Option<u16>,
    ) -> ExtractionResult {
        let source = extraction.source.to_lowercase();
        let target = extraction.target.clone();
        let path = extraction.path.clone();
        let critical = extraction.critical;
        let all_values = extraction.all_values;

        let mut result = match source.as_str() {
            "body" => Self::extract_from_body(&target, &path, response_body, all_values),
            "header" => Self::extract_from_header(&target, &path, response_headers),
            "status_code" | "statuscode" | "status" => {
                Self::extract_status_code(&target, status_code)
            }
            _ => ExtractionResult::failure_with_code(
                target,
                source.clone(),
                path,
                format!(
                    "Fonte de extração desconhecida '{}'. Use 'body', 'header' ou 'status_code'.",
                    source
                ),
                ErrorCode::EXTRACTION_INVALID_SOURCE,
            ),
        };

        // Define flag de crítico no resultado
        result.is_critical = critical;
        result
    }

    /// Extrai o código de status HTTP.
    fn extract_status_code(target: &str, status_code: Option<u16>) -> ExtractionResult {
        match status_code {
            Some(code) => ExtractionResult::success(
                target.to_string(),
                "status_code".to_string(),
                "".to_string(),
                Value::Number(code.into()),
            ),
            None => ExtractionResult::failure(
                target.to_string(),
                "status_code".to_string(),
                "".to_string(),
                "Status code não disponível.".to_string(),
            ),
        }
    }

    /// Extrai valor do body JSON usando JSONPath.
    ///
    /// ## Formatos de path suportados:
    /// - JSONPath padrão: `$.data.token`, `$.users[0].id`
    /// - Notação de ponto simples: `data.token` (convertido para JSONPath)
    /// - Regex (se path começa com `regex:`): `regex:token=(\w+)`
    fn extract_from_body(
        target: &str,
        path: &str,
        response_body: Option<&Value>,
        all_values: bool,
    ) -> ExtractionResult {
        let body = match response_body {
            Some(b) => b,
            None => {
                return ExtractionResult::failure(
                    target.to_string(),
                    "body".to_string(),
                    path.to_string(),
                    "Body da resposta está vazio ou não é JSON válido.".to_string(),
                );
            }
        };

        // Verifica se é extração por regex
        if let Some(regex_pattern) = path.strip_prefix("regex:") {
            return Self::extract_with_regex(target, regex_pattern, body, all_values);
        }

        // Extração por JSONPath
        Self::extract_with_jsonpath(target, path, body, all_values)
    }

    /// Extrai valor usando JSONPath.
    ///
    /// Suporta:
    /// - `$.data.token` → JSONPath padrão
    /// - `data.token` → Convertido para JSONPath
    /// - `$.users[0].id` → Acesso a arrays
    /// - `$.items[*].name` → Todos os items (retorna array)
    ///
    /// Se `all_values` for true, retorna todos os matches como array.
    fn extract_with_jsonpath(
        target: &str,
        path: &str,
        body: &Value,
        all_values: bool,
    ) -> ExtractionResult {
        // Normaliza o path para JSONPath
        let jsonpath = if path.starts_with('$') {
            path.to_string()
        } else {
            format!("$.{}", path)
        };

        // Usa navegação manual por enquanto (serde_json_path será adicionado depois)
        // Isso permite funcionar sem dependência externa inicialmente
        match navigate_json_multi(body, &jsonpath, all_values) {
            Ok(value) => {
                if value.is_null() {
                    ExtractionResult::failure_with_code(
                        target.to_string(),
                        "body".to_string(),
                        path.to_string(),
                        format!("Campo '{}' não encontrado ou é null.", path),
                        ErrorCode::EXTRACTION_PATH_NOT_FOUND,
                    )
                } else {
                    ExtractionResult::success(
                        target.to_string(),
                        "body".to_string(),
                        path.to_string(),
                        value,
                    )
                }
            }
            Err(e) => ExtractionResult::failure_with_code(
                target.to_string(),
                "body".to_string(),
                path.to_string(),
                e.to_string(),
                ErrorCode::EXTRACTION_PATH_NOT_FOUND,
            ),
        }
    }

    /// Extrai valor usando regex com grupo de captura.
    ///
    /// O primeiro grupo de captura `()` é usado como valor.
    /// Se não houver grupo, o match completo é usado.
    /// Se `all_values` for true, retorna todos os matches como array.
    fn extract_with_regex(
        target: &str,
        pattern: &str,
        body: &Value,
        all_values: bool,
    ) -> ExtractionResult {
        // Converte body para string para aplicar regex
        let body_str = match body {
            Value::String(s) => s.clone(),
            _ => body.to_string(),
        };

        match Regex::new(pattern) {
            Ok(re) => {
                if all_values {
                    // Retorna todos os matches como array
                    let matches: Vec<Value> = re
                        .captures_iter(&body_str)
                        .filter_map(|caps| {
                            caps.get(1)
                                .or_else(|| caps.get(0))
                                .map(|m| Value::String(m.as_str().to_string()))
                        })
                        .collect();

                    if matches.is_empty() {
                        ExtractionResult::failure_with_code(
                            target.to_string(),
                            "body".to_string(),
                            format!("regex:{}", pattern),
                            format!("Padrão regex '{}' não encontrou match no body.", pattern),
                            ErrorCode::EXTRACTION_REGEX_NO_MATCH,
                        )
                    } else {
                        ExtractionResult::success(
                            target.to_string(),
                            "body".to_string(),
                            format!("regex:{}", pattern),
                            Value::Array(matches),
                        )
                    }
                } else {
                    // Retorna apenas o primeiro match
                    match re.captures(&body_str) {
                        Some(caps) => {
                            // Usa o primeiro grupo de captura, ou o match completo
                            let value = caps
                                .get(1)
                                .or_else(|| caps.get(0))
                                .map(|m| m.as_str())
                                .unwrap_or("");

                            ExtractionResult::success(
                                target.to_string(),
                                "body".to_string(),
                                format!("regex:{}", pattern),
                                Value::String(value.to_string()),
                            )
                        }
                        None => ExtractionResult::failure_with_code(
                            target.to_string(),
                            "body".to_string(),
                            format!("regex:{}", pattern),
                            format!("Padrão regex '{}' não encontrou match no body.", pattern),
                            ErrorCode::EXTRACTION_REGEX_NO_MATCH,
                        ),
                    }
                }
            }
            Err(e) => ExtractionResult::failure_with_code(
                target.to_string(),
                "body".to_string(),
                format!("regex:{}", pattern),
                format!("Regex inválida '{}': {}", pattern, e),
                ErrorCode::EXTRACTION_INVALID_REGEX,
            ),
        }
    }

    /// Extrai valor de um header HTTP.
    fn extract_from_header(
        target: &str,
        header_name: &str,
        headers: &HashMap<String, String>,
    ) -> ExtractionResult {
        // Busca case-insensitive (headers HTTP são case-insensitive)
        let header_lower = header_name.to_lowercase();

        for (key, value) in headers {
            if key.to_lowercase() == header_lower {
                return ExtractionResult::success(
                    target.to_string(),
                    "header".to_string(),
                    header_name.to_string(),
                    Value::String(value.clone()),
                );
            }
        }

        ExtractionResult::failure_with_code(
            target.to_string(),
            "header".to_string(),
            header_name.to_string(),
            format!("Header '{}' não encontrado na resposta.", header_name),
            ErrorCode::EXTRACTION_HEADER_NOT_FOUND,
        )
    }
}

// ============================================================================
// NAVEGAÇÃO JSON SIMPLIFICADA
// ============================================================================

/// Navega em um Value JSON usando um path simplificado.
///
/// Suporta:
/// - `$.field` → Acesso direto a campo
/// - `$.parent.child` → Acesso aninhado
/// - `$.array[0]` → Acesso a índice de array
/// - `$.array[*]` → Todos os elementos (retorna array)
#[allow(dead_code)]
fn navigate_json(value: &Value, path: &str) -> Result<Value> {
    navigate_json_multi(value, path, false)
}

/// Navega em um Value JSON com suporte a múltiplos valores.
///
/// Se `all_values` for true e houver múltiplos resultados (ex: wildcard),
/// retorna todos como array. Caso contrário, retorna o primeiro.
fn navigate_json_multi(value: &Value, path: &str, all_values: bool) -> Result<Value> {
    // Remove o prefixo "$." se presente
    let clean_path = path.strip_prefix("$.").unwrap_or(path);

    if clean_path.is_empty() {
        return Ok(value.clone());
    }

    let mut current = value.clone();

    for segment in split_path(clean_path) {
        current = navigate_segment(&current, &segment, all_values)?;
    }

    Ok(current)
}

/// Divide um path em segmentos, respeitando índices de array.
///
/// Exemplo: "users[0].name" → ["users", "[0]", "name"]
fn split_path(path: &str) -> Vec<String> {
    let mut segments = Vec::new();
    let mut current = String::new();

    let mut chars = path.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '.' => {
                if !current.is_empty() {
                    segments.push(current.clone());
                    current.clear();
                }
            }
            '[' => {
                if !current.is_empty() {
                    segments.push(current.clone());
                    current.clear();
                }
                current.push('[');
                // Lê até o ]
                while let Some(&next) = chars.peek() {
                    current.push(chars.next().unwrap());
                    if next == ']' {
                        break;
                    }
                }
                segments.push(current.clone());
                current.clear();
            }
            _ => current.push(c),
        }
    }

    if !current.is_empty() {
        segments.push(current);
    }

    segments
}

/// Navega um único segmento do path.
fn navigate_segment(value: &Value, segment: &str, _all_values: bool) -> Result<Value> {
    // Índice de array: [0], [1], [*]
    if segment.starts_with('[') && segment.ends_with(']') {
        let index_str = &segment[1..segment.len() - 1];

        // Wildcard: retorna todos os elementos
        if index_str == "*" {
            return match value {
                Value::Array(arr) => Ok(Value::Array(arr.clone())),
                _ => Err(anyhow!("Esperado array para [*], encontrado: {}", value)),
            };
        }

        // Índice numérico
        let index: usize = index_str
            .parse()
            .map_err(|_| anyhow!("Índice de array inválido: '{}'", index_str))?;

        return match value {
            Value::Array(arr) => arr.get(index).cloned().ok_or_else(|| {
                anyhow!(
                    "Índice {} fora dos limites (array tem {} elementos)",
                    index,
                    arr.len()
                )
            }),
            _ => Err(anyhow!(
                "Esperado array para [{}], encontrado: {}",
                index,
                value
            )),
        };
    }

    // Campo de objeto
    match value {
        Value::Object(map) => map
            .get(segment)
            .cloned()
            .ok_or_else(|| anyhow!("Campo '{}' não encontrado no objeto", segment)),
        _ => Err(anyhow!(
            "Esperado objeto para acessar '{}', encontrado: {}",
            segment,
            value
        )),
    }
}

// ============================================================================
// TESTES
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // ------------------------------------------------------------------------
    // Testes de navegação JSON
    // ------------------------------------------------------------------------

    #[test]
    fn test_navigate_simple_field() {
        let json = json!({"name": "João"});
        let result = navigate_json(&json, "$.name").unwrap();
        assert_eq!(result, json!("João"));
    }

    #[test]
    fn test_navigate_nested_field() {
        let json = json!({"data": {"token": "abc123"}});
        let result = navigate_json(&json, "$.data.token").unwrap();
        assert_eq!(result, json!("abc123"));
    }

    #[test]
    fn test_navigate_array_index() {
        let json = json!({"users": [{"id": 1}, {"id": 2}]});
        let result = navigate_json(&json, "$.users[0].id").unwrap();
        assert_eq!(result, json!(1));
    }

    #[test]
    fn test_navigate_array_wildcard() {
        let json = json!({"items": [1, 2, 3]});
        let result = navigate_json(&json, "$.items[*]").unwrap();
        assert_eq!(result, json!([1, 2, 3]));
    }

    #[test]
    fn test_navigate_without_dollar() {
        let json = json!({"data": {"value": 42}});
        let result = navigate_json(&json, "data.value").unwrap();
        assert_eq!(result, json!(42));
    }

    #[test]
    fn test_navigate_missing_field() {
        let json = json!({"name": "test"});
        let result = navigate_json(&json, "$.missing");
        assert!(result.is_err());
    }

    // ------------------------------------------------------------------------
    // Testes de extração de body
    // ------------------------------------------------------------------------

    #[test]
    fn test_extract_from_body_simple() {
        let body = json!({"token": "secret123"});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.token".to_string(),
            target: "auth_token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, values) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert_eq!(results.len(), 1);
        assert!(results[0].success);
        assert_eq!(values.get("auth_token"), Some(&json!("secret123")));
    }

    #[test]
    fn test_extract_from_body_nested() {
        let body = json!({
            "data": {
                "user": {
                    "id": 42,
                    "name": "Test User"
                }
            }
        });

        let extractions = vec![
            Extraction {
                source: "body".to_string(),
                path: "$.data.user.id".to_string(),
                target: "user_id".to_string(),
                all_values: false,
                critical: false,
            },
            Extraction {
                source: "body".to_string(),
                path: "$.data.user.name".to_string(),
                target: "user_name".to_string(),
                all_values: false,
                critical: false,
            },
        ];

        let (results, values) = Extractor::process(&extractions, Some(&body), &HashMap::new());

        assert_eq!(results.len(), 2);
        assert!(results.iter().all(|r| r.success));
        assert_eq!(values.get("user_id"), Some(&json!(42)));
        assert_eq!(values.get("user_name"), Some(&json!("Test User")));
    }

    #[test]
    fn test_extract_from_body_missing_field() {
        let body = json!({"name": "test"});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.missing_field".to_string(),
            target: "result".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, values) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert_eq!(results.len(), 1);
        assert!(!results[0].success);
        assert!(results[0].error.is_some());
        assert!(values.is_empty());
    }

    // ------------------------------------------------------------------------
    // Testes de extração de header
    // ------------------------------------------------------------------------

    #[test]
    fn test_extract_from_header() {
        let mut headers = HashMap::new();
        headers.insert("X-Request-Id".to_string(), "req-12345".to_string());
        headers.insert("Content-Type".to_string(), "application/json".to_string());

        let extraction = Extraction {
            source: "header".to_string(),
            path: "X-Request-Id".to_string(),
            target: "request_id".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, values) = Extractor::process(&[extraction], None, &headers);

        assert_eq!(results.len(), 1);
        assert!(results[0].success);
        assert_eq!(values.get("request_id"), Some(&json!("req-12345")));
    }

    #[test]
    fn test_extract_from_header_case_insensitive() {
        let mut headers = HashMap::new();
        headers.insert("content-type".to_string(), "application/json".to_string());

        let extraction = Extraction {
            source: "header".to_string(),
            path: "Content-Type".to_string(), // Diferente case
            target: "content_type".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, values) = Extractor::process(&[extraction], None, &headers);

        assert!(results[0].success);
        assert_eq!(values.get("content_type"), Some(&json!("application/json")));
    }

    #[test]
    fn test_extract_from_header_missing() {
        let headers = HashMap::new();
        let extraction = Extraction {
            source: "header".to_string(),
            path: "X-Missing".to_string(),
            target: "missing".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], None, &headers);

        assert!(!results[0].success);
        assert!(results[0]
            .error
            .as_ref()
            .unwrap()
            .contains("não encontrado"));
    }

    // ------------------------------------------------------------------------
    // Testes de extração por regex
    // ------------------------------------------------------------------------

    #[test]
    fn test_extract_with_regex() {
        let body = json!("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9");
        let extraction = Extraction {
            source: "body".to_string(),
            path: "regex:Bearer\\s+(\\S+)".to_string(),
            target: "jwt_token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, values) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(results[0].success);
        assert_eq!(
            values.get("jwt_token"),
            Some(&json!("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"))
        );
    }

    #[test]
    fn test_extract_with_regex_no_match() {
        let body = json!("no token here");
        let extraction = Extraction {
            source: "body".to_string(),
            path: "regex:Bearer\\s+(\\S+)".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert!(results[0]
            .error
            .as_ref()
            .unwrap()
            .contains("não encontrou match"));
    }

    #[test]
    fn test_extract_with_invalid_regex() {
        let body = json!("test");
        let extraction = Extraction {
            source: "body".to_string(),
            path: "regex:[invalid".to_string(),
            target: "result".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert!(results[0]
            .error
            .as_ref()
            .unwrap()
            .contains("Regex inválida"));
    }

    // ------------------------------------------------------------------------
    // Testes de múltiplas extrações
    // ------------------------------------------------------------------------

    #[test]
    fn test_multiple_extractions() {
        let body = json!({
            "access_token": "token123",
            "refresh_token": "refresh456",
            "expires_in": 3600
        });

        let mut headers = HashMap::new();
        headers.insert("X-RateLimit-Remaining".to_string(), "99".to_string());

        let extractions = vec![
            Extraction {
                source: "body".to_string(),
                path: "$.access_token".to_string(),
                target: "access_token".to_string(),
                all_values: false,
                critical: false,
            },
            Extraction {
                source: "body".to_string(),
                path: "$.refresh_token".to_string(),
                target: "refresh_token".to_string(),
                all_values: false,
                critical: false,
            },
            Extraction {
                source: "body".to_string(),
                path: "$.expires_in".to_string(),
                target: "expires_in".to_string(),
                all_values: false,
                critical: false,
            },
            Extraction {
                source: "header".to_string(),
                path: "X-RateLimit-Remaining".to_string(),
                target: "rate_limit".to_string(),
                all_values: false,
                critical: false,
            },
        ];

        let (results, values) = Extractor::process(&extractions, Some(&body), &headers);

        assert_eq!(results.len(), 4);
        assert!(results.iter().all(|r| r.success));
        assert_eq!(values.len(), 4);
        assert_eq!(values.get("access_token"), Some(&json!("token123")));
        assert_eq!(values.get("refresh_token"), Some(&json!("refresh456")));
        assert_eq!(values.get("expires_in"), Some(&json!(3600)));
        assert_eq!(values.get("rate_limit"), Some(&json!("99")));
    }

    // ------------------------------------------------------------------------
    // Testes de edge cases
    // ------------------------------------------------------------------------

    #[test]
    fn test_extract_from_empty_body() {
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.token".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], None, &HashMap::new());

        assert!(!results[0].success);
        assert!(results[0].error.as_ref().unwrap().contains("vazio"));
    }

    #[test]
    fn test_extract_unknown_source() {
        let extraction = Extraction {
            source: "unknown".to_string(),
            path: "test".to_string(),
            target: "result".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], None, &HashMap::new());

        assert!(!results[0].success);
        assert!(results[0].error.as_ref().unwrap().contains("desconhecida"));
    }

    #[test]
    fn test_extract_null_value() {
        let body = json!({"token": null});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.token".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert!(results[0].error.as_ref().unwrap().contains("null"));
    }

    // ------------------------------------------------------------------------
    // Testes de códigos de erro estruturados
    // ------------------------------------------------------------------------

    #[test]
    fn test_error_code_path_not_found() {
        let body = json!({"data": {}});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.data.missing_field".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert_eq!(results[0].error_code.as_ref().unwrap(), "E3010");
    }

    #[test]
    fn test_error_code_header_not_found() {
        let extraction = Extraction {
            source: "header".to_string(),
            path: "X-Missing-Header".to_string(),
            target: "header".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], None, &HashMap::new());

        assert!(!results[0].success);
        assert_eq!(results[0].error_code.as_ref().unwrap(), "E3011");
    }

    #[test]
    fn test_error_code_regex_no_match() {
        let body = json!("some text without match");
        let extraction = Extraction {
            source: "body".to_string(),
            path: "regex:token=(\\w+)".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert_eq!(results[0].error_code.as_ref().unwrap(), "E3012");
    }

    #[test]
    fn test_error_code_invalid_source() {
        // Note: Now "statuscode" is valid, so we use a truly invalid source
        let extraction = Extraction {
            source: "invalid_source".to_string(),
            path: "test".to_string(),
            target: "result".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], None, &HashMap::new());

        assert!(!results[0].success);
        assert_eq!(results[0].error_code.as_ref().unwrap(), "E3013");
    }

    #[test]
    fn test_error_code_invalid_regex() {
        let body = json!("some text");
        let extraction = Extraction {
            source: "body".to_string(),
            path: "regex:[invalid(".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert_eq!(results[0].error_code.as_ref().unwrap(), "E3014");
    }

    // ------------------------------------------------------------------------
    // Teste de integração: fluxo completo login → token → uso
    // ------------------------------------------------------------------------

    #[test]
    fn test_integration_login_extract_token_flow() {
        use crate::context::Context;

        // Simula Step 1: Login
        let login_response = json!({
            "success": true,
            "data": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
                "refresh_token": "refresh_abc123",
                "user": {
                    "id": 42,
                    "name": "Test User"
                }
            }
        });

        let mut login_headers = HashMap::new();
        login_headers.insert("X-Request-Id".to_string(), "req-001".to_string());

        let step1_extractions = vec![
            Extraction {
                source: "body".to_string(),
                path: "$.data.access_token".to_string(),
                target: "auth_token".to_string(),
                all_values: false,
                critical: false,
            },
            Extraction {
                source: "body".to_string(),
                path: "$.data.user.id".to_string(),
                target: "user_id".to_string(),
                all_values: false,
                critical: false,
            },
            Extraction {
                source: "header".to_string(),
                path: "X-Request-Id".to_string(),
                target: "request_id".to_string(),
                all_values: false,
                critical: false,
            },
        ];

        // Processa extrações do Step 1
        let (results, values) =
            Extractor::process(&step1_extractions, Some(&login_response), &login_headers);

        // Verifica que todas extrações foram bem sucedidas
        assert!(
            results.iter().all(|r| r.success),
            "Todas extrações devem passar"
        );
        assert_eq!(values.len(), 3);

        // Simula inserção no Context
        let mut ctx = Context::default();
        for (key, value) in &values {
            ctx.set(key.clone(), value.clone());
        }

        // Verifica que os valores estão no contexto
        assert!(ctx.variables.contains_key("auth_token"));
        assert!(ctx.variables.contains_key("user_id"));
        assert!(ctx.variables.contains_key("request_id"));

        // Simula Step 2: Usa o token extraído
        // Em uso real, a interpolação ${auth_token} seria aplicada no header
        let token = ctx.variables.get("auth_token").unwrap();
        assert!(token.as_str().unwrap().starts_with("eyJ"));

        let user_id = ctx.variables.get("user_id").unwrap();
        assert_eq!(user_id, &json!(42));
    }

    // ------------------------------------------------------------------------
    // Testes de extração de status_code
    // ------------------------------------------------------------------------

    #[test]
    fn test_extract_status_code() {
        let extraction = Extraction {
            source: "status_code".to_string(),
            path: "".to_string(),
            target: "http_status".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, values) =
            Extractor::process_with_status(&[extraction], None, &HashMap::new(), Some(200));

        assert_eq!(results.len(), 1);
        assert!(results[0].success);
        assert_eq!(values.get("http_status"), Some(&json!(200)));
        assert_eq!(results[0].value_type, Some(ValueType::Number));
    }

    #[test]
    fn test_extract_status_code_not_available() {
        let extraction = Extraction {
            source: "status_code".to_string(),
            path: "".to_string(),
            target: "http_status".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) =
            Extractor::process_with_status(&[extraction], None, &HashMap::new(), None);

        assert!(!results[0].success);
        assert!(results[0]
            .error
            .as_ref()
            .unwrap()
            .contains("não disponível"));
    }

    // ------------------------------------------------------------------------
    // Testes de value_type
    // ------------------------------------------------------------------------

    #[test]
    fn test_value_type_string() {
        let body = json!({"name": "test"});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.name".to_string(),
            target: "name".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(results[0].success);
        assert_eq!(results[0].value_type, Some(ValueType::String));
    }

    #[test]
    fn test_value_type_number() {
        let body = json!({"count": 42});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.count".to_string(),
            target: "count".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(results[0].success);
        assert_eq!(results[0].value_type, Some(ValueType::Number));
    }

    #[test]
    fn test_value_type_boolean() {
        let body = json!({"active": true});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.active".to_string(),
            target: "active".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(results[0].success);
        assert_eq!(results[0].value_type, Some(ValueType::Boolean));
    }

    #[test]
    fn test_value_type_array() {
        let body = json!({"items": [1, 2, 3]});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.items".to_string(),
            target: "items".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(results[0].success);
        assert_eq!(results[0].value_type, Some(ValueType::Array));
    }

    // ------------------------------------------------------------------------
    // Testes de all_values (múltiplos resultados)
    // ------------------------------------------------------------------------

    #[test]
    fn test_all_values_regex() {
        let body = json!("token1=abc token2=def token3=ghi");
        let extraction = Extraction {
            source: "body".to_string(),
            path: "regex:token\\d=(\\w+)".to_string(),
            target: "tokens".to_string(),
            all_values: true,
            critical: false,
        };

        let (results, values) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(results[0].success);
        let tokens = values.get("tokens").unwrap();
        assert!(tokens.is_array());
        let arr = tokens.as_array().unwrap();
        assert_eq!(arr.len(), 3);
        assert_eq!(arr[0], json!("abc"));
        assert_eq!(arr[1], json!("def"));
        assert_eq!(arr[2], json!("ghi"));
    }

    #[test]
    fn test_all_values_false_returns_first() {
        let body = json!("token1=abc token2=def");
        let extraction = Extraction {
            source: "body".to_string(),
            path: "regex:token\\d=(\\w+)".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: false,
        };

        let (results, values) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(results[0].success);
        // Com all_values=false, retorna apenas o primeiro
        assert_eq!(values.get("token"), Some(&json!("abc")));
    }

    // ------------------------------------------------------------------------
    // Testes de critical (falhas críticas)
    // ------------------------------------------------------------------------

    #[test]
    fn test_critical_extraction_failure() {
        let body = json!({"data": {}});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.data.missing_token".to_string(),
            target: "token".to_string(),
            all_values: false,
            critical: true, // Esta é crítica!
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert!(results[0].is_critical);
        assert!(results[0].should_abort());
        assert!(Extractor::has_critical_failure(&results));
    }

    #[test]
    fn test_non_critical_extraction_failure() {
        let body = json!({"data": {}});
        let extraction = Extraction {
            source: "body".to_string(),
            path: "$.data.optional_field".to_string(),
            target: "optional".to_string(),
            all_values: false,
            critical: false, // Não é crítica
        };

        let (results, _) = Extractor::process(&[extraction], Some(&body), &HashMap::new());

        assert!(!results[0].success);
        assert!(!results[0].is_critical);
        assert!(!results[0].should_abort());
        assert!(!Extractor::has_critical_failure(&results));
    }

    #[test]
    fn test_mixed_critical_extractions() {
        let body = json!({"token": "abc123"});
        let extractions = vec![
            Extraction {
                source: "body".to_string(),
                path: "$.token".to_string(),
                target: "token".to_string(),
                all_values: false,
                critical: true, // Crítica, mas vai passar
            },
            Extraction {
                source: "body".to_string(),
                path: "$.missing".to_string(),
                target: "missing".to_string(),
                all_values: false,
                critical: false, // Não crítica, vai falhar
            },
        ];

        let (results, _) = Extractor::process(&extractions, Some(&body), &HashMap::new());

        // Token passou
        assert!(results[0].success);
        // Missing falhou, mas não é crítica
        assert!(!results[1].success);
        assert!(!results[1].is_critical);
        // Não deve abortar
        assert!(!Extractor::has_critical_failure(&results));
    }
}
