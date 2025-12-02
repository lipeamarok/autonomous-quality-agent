//! Módulo de Validação de UTDL.
//!
//! Valida planos UTDL antes da execução para evitar panics
//! e fornecer mensagens de erro claras.

use crate::protocol::{Plan, Step};
use thiserror::Error;

/// Erros de validação de UTDL.
#[derive(Debug, Error)]
pub enum ValidationError {
    #[error("Step '{step_id}': action '{action}' não é conhecida. Ações válidas: http_request, wait")]
    UnknownAction { step_id: String, action: String },

    #[error("Step '{step_id}': parâmetro obrigatório '{param}' está ausente")]
    MissingParam { step_id: String, param: String },

    #[error("Step '{step_id}': dependência '{dep}' não existe no plano")]
    UnknownDependency { step_id: String, dep: String },

    #[error("Step '{step_id}': dependência circular detectada")]
    CircularDependency { step_id: String },

    #[error("Plano vazio: nenhum step definido")]
    EmptyPlan,

    #[error("Step '{step_id}': ID vazio não é permitido")]
    EmptyStepId { step_id: String },

    #[error("Step '{step_id}': método HTTP '{method}' inválido")]
    InvalidHttpMethod { step_id: String, method: String },
}

/// Ações conhecidas pelo Runner.
const KNOWN_ACTIONS: &[&str] = &["http_request", "wait"];

/// Métodos HTTP válidos.
const VALID_HTTP_METHODS: &[&str] = &["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"];

/// Resultado de validação.
pub type ValidationResult = Result<(), Vec<ValidationError>>;

/// Valida um plano UTDL completo.
///
/// Retorna Ok(()) se válido, ou Err com lista de todos os erros encontrados.
pub fn validate_plan(plan: &Plan) -> ValidationResult {
    let mut errors = Vec::new();

    // Verifica se o plano tem steps
    if plan.steps.is_empty() {
        errors.push(ValidationError::EmptyPlan);
        return Err(errors);
    }

    // Coleta IDs de todos os steps para validar dependências
    let step_ids: Vec<&str> = plan.steps.iter().map(|s| s.id.as_str()).collect();

    // Valida cada step
    for step in &plan.steps {
        validate_step(step, &step_ids, &mut errors);
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// Valida um step individual.
fn validate_step(step: &Step, all_step_ids: &[&str], errors: &mut Vec<ValidationError>) {
    // Verifica ID vazio
    if step.id.trim().is_empty() {
        errors.push(ValidationError::EmptyStepId {
            step_id: "<vazio>".to_string(),
        });
        return; // Não faz sentido continuar sem ID
    }

    // Verifica action conhecida
    if !KNOWN_ACTIONS.contains(&step.action.as_str()) {
        errors.push(ValidationError::UnknownAction {
            step_id: step.id.clone(),
            action: step.action.clone(),
        });
    }

    // Valida parâmetros específicos por action
    match step.action.as_str() {
        "http_request" => validate_http_request_params(step, errors),
        "wait" => validate_wait_params(step, errors),
        _ => {} // Ações desconhecidas já foram reportadas
    }

    // Verifica dependências
    for dep in &step.depends_on {
        if !all_step_ids.contains(&dep.as_str()) {
            errors.push(ValidationError::UnknownDependency {
                step_id: step.id.clone(),
                dep: dep.clone(),
            });
        }
        // Verifica auto-referência (dependência circular simples)
        if dep == &step.id {
            errors.push(ValidationError::CircularDependency {
                step_id: step.id.clone(),
            });
        }
    }
}

/// Valida parâmetros de http_request.
fn validate_http_request_params(step: &Step, errors: &mut Vec<ValidationError>) {
    // Verifica method
    let method = step.params.get("method").and_then(|v| v.as_str());
    match method {
        None => {
            errors.push(ValidationError::MissingParam {
                step_id: step.id.clone(),
                param: "method".to_string(),
            });
        }
        Some(m) => {
            if !VALID_HTTP_METHODS.contains(&m.to_uppercase().as_str()) {
                errors.push(ValidationError::InvalidHttpMethod {
                    step_id: step.id.clone(),
                    method: m.to_string(),
                });
            }
        }
    }

    // Verifica path
    if step.params.get("path").and_then(|v| v.as_str()).is_none() {
        errors.push(ValidationError::MissingParam {
            step_id: step.id.clone(),
            param: "path".to_string(),
        });
    }
}

/// Valida parâmetros de wait.
fn validate_wait_params(step: &Step, errors: &mut Vec<ValidationError>) {
    if step.params.get("duration_ms").and_then(|v| v.as_u64()).is_none() {
        errors.push(ValidationError::MissingParam {
            step_id: step.id.clone(),
            param: "duration_ms".to_string(),
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{Meta, Config, Step};
    use serde_json::json;
    use std::collections::HashMap;

    fn create_test_plan(steps: Vec<Step>) -> Plan {
        Plan {
            spec_version: "1.0".to_string(),
            meta: Meta {
                id: "test".to_string(),
                name: "Test Plan".to_string(),
                description: None,
                tags: vec![],
                created_at: "2024-01-01".to_string(),
            },
            config: Config {
                base_url: "https://api.test.com".to_string(),
                timeout_ms: 5000,
                global_headers: HashMap::new(),
                variables: HashMap::new(),
            },
            steps,
        }
    }

    fn create_http_step(id: &str, method: &str, path: &str) -> Step {
        Step {
            id: id.to_string(),
            description: None,
            depends_on: vec![],
            action: "http_request".to_string(),
            params: json!({ "method": method, "path": path }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }
    }

    #[test]
    fn test_valid_plan() {
        let plan = create_test_plan(vec![
            create_http_step("step1", "GET", "/api/test"),
        ]);
        assert!(validate_plan(&plan).is_ok());
    }

    #[test]
    fn test_empty_plan() {
        let plan = create_test_plan(vec![]);
        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(matches!(errors[0], ValidationError::EmptyPlan));
    }

    #[test]
    fn test_unknown_action() {
        let plan = create_test_plan(vec![Step {
            id: "step1".to_string(),
            description: None,
            depends_on: vec![],
            action: "browser_click".to_string(), // Não suportado ainda
            params: json!({}),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }]);
        
        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(matches!(&errors[0], ValidationError::UnknownAction { action, .. } if action == "browser_click"));
    }

    #[test]
    fn test_missing_http_params() {
        let plan = create_test_plan(vec![Step {
            id: "step1".to_string(),
            description: None,
            depends_on: vec![],
            action: "http_request".to_string(),
            params: json!({}), // Sem method e path
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }]);
        
        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert_eq!(errors.len(), 2); // method e path
    }

    #[test]
    fn test_unknown_dependency() {
        let plan = create_test_plan(vec![Step {
            id: "step1".to_string(),
            description: None,
            depends_on: vec!["nonexistent".to_string()],
            action: "http_request".to_string(),
            params: json!({ "method": "GET", "path": "/test" }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }]);
        
        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(matches!(&errors[0], ValidationError::UnknownDependency { dep, .. } if dep == "nonexistent"));
    }

    #[test]
    fn test_circular_self_dependency() {
        let plan = create_test_plan(vec![Step {
            id: "step1".to_string(),
            description: None,
            depends_on: vec!["step1".to_string()], // Auto-referência
            action: "http_request".to_string(),
            params: json!({ "method": "GET", "path": "/test" }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }]);
        
        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(matches!(&errors[0], ValidationError::CircularDependency { .. }));
    }

    #[test]
    fn test_invalid_http_method() {
        let plan = create_test_plan(vec![
            create_http_step("step1", "INVALID", "/api/test"),
        ]);
        
        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(matches!(&errors[0], ValidationError::InvalidHttpMethod { method, .. } if method == "INVALID"));
    }

    #[test]
    fn test_wait_missing_duration() {
        let plan = create_test_plan(vec![Step {
            id: "wait1".to_string(),
            description: None,
            depends_on: vec![],
            action: "wait".to_string(),
            params: json!({}), // Sem duration_ms
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }]);
        
        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(matches!(&errors[0], ValidationError::MissingParam { param, .. } if param == "duration_ms"));
    }
}
