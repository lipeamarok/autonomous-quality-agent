//! # Módulo de Validação de UTDL
//!
//! Este módulo valida planos UTDL antes da execução para garantir
//! que o arquivo de teste está correto e evitar erros durante a execução.
//!
//! ## Para leigos:
//!
//! Imagine que você está preenchendo um formulário importante.
//! Antes de enviar, o sistema verifica se todos os campos obrigatórios
//! estão preenchidos e se os valores fazem sentido.
//! Este módulo faz exatamente isso para os arquivos de teste.
//!
//! ## Por que validar?
//!
//! - **Prevenir erros tardios**: Melhor descobrir problemas antes de executar
//! - **Mensagens claras**: Erros específicos ajudam a corrigir rapidamente
//! - **Fail-fast**: Se algo está errado, paramos imediatamente
//!
//! ## Validações realizadas:
//!
//! 1. **spec_version**: Verifica se a versão do formato é suportada
//! 2. **Plano não vazio**: Deve ter pelo menos um step
//! 3. **Actions válidas**: Apenas ações conhecidas são aceitas
//! 4. **Parâmetros completos**: Campos obrigatórios presentes
//! 5. **Dependências existem**: Não referencia steps inexistentes
//! 6. **Sem ciclos**: Evita dependências circulares
//!
//! ## Exemplo de uso:
//!
//! ```ignore
//! let plan = loader::load_plan("test.json")?;
//!
//! match validate_plan(&plan) {
//!     Ok(()) => println!("Plano válido!"),
//!     Err(errors) => {
//!         for err in errors {
//!             eprintln!("Erro: {}", err);
//!         }
//!     }
//! }
//! ```

use std::collections::HashMap;
use crate::protocol::{Plan, Step};
use thiserror::Error;

// ============================================================================
// TIPOS DE ERRO
// ============================================================================

/// Erros de validação de UTDL.
///
/// Cada variante representa um tipo específico de problema encontrado.
/// O atributo `#[error(...)]` define a mensagem que será exibida.
///
/// ## Para leigos:
///
/// `enum` em Rust é como uma lista de opções possíveis.
/// Aqui listamos todos os tipos de erro que podem acontecer.
#[derive(Debug, Error)]
pub enum ValidationError {
    /// Versão do formato UTDL não é suportada.
    /// Exemplo: spec_version "2.0" quando só suportamos "0.1"
    #[error("Plano com spec_version '{version}' não suportada. Versão esperada: {expected}")]
    UnsupportedSpecVersion { version: String, expected: String },

    /// Ação (action) do step não é reconhecida.
    /// Exemplo: "browser_click" quando só temos "http_request", "wait", "sleep"
    #[error("Step '{step_id}': action '{action}' não é conhecida. Ações válidas: http_request, wait, sleep")]
    UnknownAction { step_id: String, action: String },

    /// Parâmetro obrigatório não foi informado.
    /// Exemplo: http_request sem "method" ou "path"
    #[error("Step '{step_id}': parâmetro obrigatório '{param}' está ausente")]
    MissingParam { step_id: String, param: String },

    /// Dependência referencia um step que não existe.
    /// Exemplo: depends_on: ["step_xyz"] mas não existe step com id "step_xyz"
    #[error("Step '{step_id}': dependência '{dep}' não existe no plano")]
    UnknownDependency { step_id: String, dep: String },

    /// Dependência circular detectada (A depende de B que depende de A).
    /// Isso causaria loop infinito na execução.
    #[error("Step '{step_id}': dependência circular detectada")]
    CircularDependency { step_id: String },

    /// Plano não tem nenhum step para executar.
    #[error("Plano vazio: nenhum step definido")]
    EmptyPlan,

    /// Step tem ID vazio ou apenas espaços.
    #[error("Step '{step_id}': ID vazio não é permitido")]
    EmptyStepId { step_id: String },

    /// Método HTTP inválido (não é GET, POST, PUT, etc).
    #[error("Step '{step_id}': método HTTP '{method}' inválido")]
    InvalidHttpMethod { step_id: String, method: String },
}

// ============================================================================
// CONSTANTES
// ============================================================================

/// Versão UTDL suportada pelo Runner.
///
/// Esta constante DEVE estar alinhada com o que o Brain gera
/// e o que está documentado no TDD.
///
/// Versão atual: "0.1" (formato simples, sem prefixo "utdl/")
pub const SUPPORTED_SPEC_VERSION: &str = "0.1";

/// Lista de ações (actions) que o Runner sabe executar.
///
/// Se uma action não está aqui, o plano será rejeitado na validação.
/// Isso é melhor que falhar durante a execução.
///
/// Ações atuais:
/// - `http_request`: Faz requisição HTTP
/// - `wait`: Pausa a execução
/// - `sleep`: Alias de wait (mesmo comportamento)
const KNOWN_ACTIONS: &[&str] = &["http_request", "wait", "sleep"];

/// Métodos HTTP válidos conforme RFC 7231 e RFC 5789.
///
/// Requisições com outros métodos serão rejeitadas.
const VALID_HTTP_METHODS: &[&str] = &["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"];

// ============================================================================
// TIPOS AUXILIARES
// ============================================================================

/// Tipo de resultado para validação.
///
/// ## Para leigos:
///
/// `Result<(), Vec<ValidationError>>` significa:
/// - `Ok(())` = Sucesso, sem valor de retorno (o `()` é "nada")
/// - `Err(Vec<ValidationError>)` = Falha, com lista de erros
///
/// Usamos Vec (vetor/lista) porque pode haver múltiplos erros
/// e queremos reportar todos de uma vez.
pub type ValidationResult = Result<(), Vec<ValidationError>>;

// ============================================================================
// FUNÇÃO PRINCIPAL DE VALIDAÇÃO
// ============================================================================

/// Valida um plano UTDL completo.
///
/// Esta é a função principal de validação. Ela analisa todo o plano
/// e coleta TODOS os erros encontrados (não para no primeiro).
///
/// ## Parâmetros:
///
/// - `plan`: Referência ao plano carregado
///
/// ## Retorno:
///
/// - `Ok(())`: Plano é válido, pode executar
/// - `Err(Vec<ValidationError>)`: Lista de todos os problemas encontrados
///
/// ## Validações realizadas:
///
/// 1. spec_version deve ser "0.1"
/// 2. Plano deve ter ao menos um step
/// 3. Cada step passa pela validação individual
///
/// ## Exemplo:
///
/// ```ignore
/// match validate_plan(&plan) {
///     Ok(()) => execute_plan(plan),
///     Err(errors) => show_errors(errors),
/// }
/// ```
pub fn validate_plan(plan: &Plan) -> ValidationResult {
    // Cria vetor vazio para acumular erros.
    // Vec é como uma lista dinâmica que pode crescer.
    let mut errors = Vec::new();

    // Verifica spec_version.
    // Se não bate com a versão suportada, adiciona erro.
    if plan.spec_version != SUPPORTED_SPEC_VERSION {
        errors.push(ValidationError::UnsupportedSpecVersion {
            version: plan.spec_version.clone(),
            expected: SUPPORTED_SPEC_VERSION.to_string(),
        });
    }

    // Verifica se o plano tem steps.
    // Um plano sem steps não faz sentido executar.
    if plan.steps.is_empty() {
        errors.push(ValidationError::EmptyPlan);
        // Retorna early porque sem steps não há o que validar mais.
        return Err(errors);
    }

    // Valida o DAG (detecta ciclos complexos como A→B→C→A).
    // Isso é crucial para evitar loops infinitos na execução paralela.
    if let Err(cycle_errors) = validate_dag(&plan.steps) {
        errors.extend(cycle_errors);
    }

    // Coleta IDs de todos os steps.
    // Isso é usado para verificar se as dependências existem.
    //
    // Para leigos:
    // `.iter()` percorre cada step
    // `.map(|s| s.id.as_str())` pega só o ID de cada um
    // `.collect()` junta tudo em um vetor
    let step_ids: Vec<&str> = plan.steps.iter().map(|s| s.id.as_str()).collect();

    // Valida cada step individualmente.
    for step in &plan.steps {
        validate_step(step, &step_ids, &mut errors);
    }

    // Retorna resultado.
    // Se não há erros, Ok(()). Se há, Err com a lista.
    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

// ============================================================================
// VALIDAÇÃO DE STEP INDIVIDUAL
// ============================================================================

/// Valida um step individual.
///
/// Esta função é chamada para cada step do plano.
/// Ela verifica:
/// - ID não está vazio
/// - Action é conhecida
/// - Parâmetros específicos da action estão presentes
/// - Dependências existem e não formam ciclos
///
/// ## Parâmetros:
///
/// - `step`: O step a validar
/// - `all_step_ids`: Lista de todos os IDs do plano
/// - `errors`: Vetor onde adicionar erros encontrados
fn validate_step(step: &Step, all_step_ids: &[&str], errors: &mut Vec<ValidationError>) {
    // Verifica ID vazio.
    // `.trim()` remove espaços em branco.
    // `.is_empty()` verifica se está vazio.
    if step.id.trim().is_empty() {
        errors.push(ValidationError::EmptyStepId {
            step_id: "<vazio>".to_string(),
        });
        // Não faz sentido continuar sem ID válido.
        return;
    }

    // Verifica se a action é conhecida.
    // `.contains()` procura na lista de actions válidas.
    if !KNOWN_ACTIONS.contains(&step.action.as_str()) {
        errors.push(ValidationError::UnknownAction {
            step_id: step.id.clone(),
            action: step.action.clone(),
        });
    }

    // Valida parâmetros específicos por action.
    // `match` é como um switch/case em outras linguagens.
    // Cada action tem parâmetros obrigatórios diferentes.
    match step.action.as_str() {
        "http_request" => validate_http_request_params(step, errors),
        "wait" | "sleep" => validate_wait_params(step, errors),
        _ => {} // Ações desconhecidas já foram reportadas acima
    }

    // Verifica dependências.
    // Para cada dependência declarada, verifica se existe.
    for dep in &step.depends_on {
        // Verifica se o step referenciado existe.
        if !all_step_ids.contains(&dep.as_str()) {
            errors.push(ValidationError::UnknownDependency {
                step_id: step.id.clone(),
                dep: dep.clone(),
            });
        }

        // Verifica auto-referência (step depende de si mesmo).
        // Isso é uma dependência circular simples.
        if dep == &step.id {
            errors.push(ValidationError::CircularDependency {
                step_id: step.id.clone(),
            });
        }
    }
}

// ============================================================================
// VALIDAÇÃO DE PARÂMETROS ESPECÍFICOS
// ============================================================================

/// Valida parâmetros obrigatórios de http_request.
///
/// Uma requisição HTTP precisa obrigatoriamente de:
/// - `method`: GET, POST, PUT, DELETE, etc.
/// - `path`: O caminho da URL (ex: "/api/users")
///
/// ## Para leigos:
///
/// Para fazer uma requisição HTTP, você precisa dizer:
/// 1. O que você quer fazer (GET=buscar, POST=criar, etc.)
/// 2. Onde fazer (o caminho/endpoint)
fn validate_http_request_params(step: &Step, errors: &mut Vec<ValidationError>) {
    // Verifica se method existe e é válido.
    //
    // `.get("method")` busca a chave "method" nos params
    // `.and_then(|v| v.as_str())` converte para string se existir
    let method = step.params.get("method").and_then(|v| v.as_str());

    match method {
        // Method não foi informado.
        None => {
            errors.push(ValidationError::MissingParam {
                step_id: step.id.clone(),
                param: "method".to_string(),
            });
        }
        // Method foi informado, verifica se é válido.
        Some(m) => {
            // `.to_uppercase()` converte para maiúsculas para comparar
            if !VALID_HTTP_METHODS.contains(&m.to_uppercase().as_str()) {
                errors.push(ValidationError::InvalidHttpMethod {
                    step_id: step.id.clone(),
                    method: m.to_string(),
                });
            }
        }
    }

    // Verifica se path existe.
    // Path é o caminho da URL (ex: "/api/users/123")
    if step.params.get("path").and_then(|v| v.as_str()).is_none() {
        errors.push(ValidationError::MissingParam {
            step_id: step.id.clone(),
            param: "path".to_string(),
        });
    }
}

/// Valida parâmetros obrigatórios de wait/sleep.
///
/// Uma ação de espera precisa de:
/// - `duration_ms`: Tempo em milissegundos
///
/// ## Para leigos:
///
/// Para pausar a execução, você precisa dizer por quanto tempo.
/// O tempo é em milissegundos (1000ms = 1 segundo).
fn validate_wait_params(step: &Step, errors: &mut Vec<ValidationError>) {
    // Verifica se duration_ms existe e é um número.
    // `.as_u64()` tenta converter para número inteiro sem sinal.
    if step.params.get("duration_ms").and_then(|v| v.as_u64()).is_none() {
        errors.push(ValidationError::MissingParam {
            step_id: step.id.clone(),
            param: "duration_ms".to_string(),
        });
    }
}

// ============================================================================
// VALIDAÇÃO DE DAG (DETECÇÃO DE CICLOS)
// ============================================================================

/// Valida que o grafo de dependências não contém ciclos.
///
/// ## Algoritmo: DFS (Depth-First Search) para detecção de ciclos
///
/// Usa um algoritmo de coloração de nós:
/// - Branco (0): Não visitado
/// - Cinza (1): Em processamento (visitando descendentes)
/// - Preto (2): Completamente processado
///
/// Se durante a DFS encontramos um nó cinza, temos um ciclo!
///
/// ## Para leigos:
///
/// Imagine que você está explorando um labirinto e marcando onde já passou.
/// Se você encontrar uma marca que fez NESTA MESMA exploração (não numa anterior),
/// significa que andou em círculos - encontrou um ciclo!
///
/// ## Exemplo de ciclo:
/// ```text
/// A → B → C → A  (ciclo!)
///
/// Explorando A: marca A como "explorando"
/// Explorando B: marca B como "explorando"  
/// Explorando C: marca C como "explorando"
/// C depende de A, mas A está "explorando" → CICLO DETECTADO!
/// ```
fn validate_dag(steps: &[Step]) -> Result<(), Vec<ValidationError>> {
    use std::collections::HashMap;
    
    // Mapa de step_id → lista de dependências
    let mut graph: HashMap<&str, Vec<&str>> = HashMap::new();
    
    // Constrói o grafo de dependências
    for step in steps {
        let deps: Vec<&str> = step.depends_on.iter().map(|s| s.as_str()).collect();
        graph.insert(step.id.as_str(), deps);
    }
    
    // Estado de cada nó: 0=branco, 1=cinza, 2=preto
    let mut color: HashMap<&str, u8> = HashMap::new();
    for step in steps {
        color.insert(step.id.as_str(), 0);
    }
    
    let mut errors = Vec::new();
    
    // Executa DFS a partir de cada nó não visitado
    for step in steps {
        if color.get(step.id.as_str()) == Some(&0) {
            detect_cycle_dfs(step.id.as_str(), &graph, &mut color, &mut errors);
        }
    }
    
    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// DFS recursivo para detectar ciclos no grafo.
///
/// Retorna true se encontrou um ciclo a partir deste nó.
fn detect_cycle_dfs<'a>(
    node: &'a str,
    graph: &HashMap<&'a str, Vec<&'a str>>,
    color: &mut HashMap<&'a str, u8>,
    errors: &mut Vec<ValidationError>,
) -> bool {
    // Marca como cinza (em processamento)
    color.insert(node, 1);
    
    // Visita todas as dependências
    if let Some(deps) = graph.get(node) {
        for dep in deps {
            match color.get(dep) {
                Some(1) => {
                    // Encontrou nó cinza = ciclo!
                    errors.push(ValidationError::CircularDependency {
                        step_id: node.to_string(),
                    });
                    return true;
                }
                Some(0) => {
                    // Nó branco, continua DFS
                    if detect_cycle_dfs(dep, graph, color, errors) {
                        return true;
                    }
                }
                _ => {
                    // Nó preto (já processado), ignora
                }
            }
        }
    }
    
    // Marca como preto (processamento completo)
    color.insert(node, 2);
    false
}

// ============================================================================
// TESTES
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{Meta, Config, Step};
    use serde_json::json;
    use std::collections::HashMap;

    /// Cria um plano de teste com os steps fornecidos.
    fn create_test_plan(steps: Vec<Step>) -> Plan {
        Plan {
            spec_version: SUPPORTED_SPEC_VERSION.to_string(), // Usa versão suportada
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

    #[test]
    fn test_unsupported_spec_version() {
        let plan = Plan {
            spec_version: "0.2".to_string(), // Versão não suportada
            meta: Meta {
                id: "test".to_string(),
                name: "Test".to_string(),
                description: None,
                tags: vec![],
                created_at: "2024-01-01T00:00:00Z".to_string(),
            },
            config: Config {
                base_url: "https://api.example.com".to_string(),
                timeout_ms: 5000,
                global_headers: HashMap::new(),
                variables: HashMap::new(),
            },
            steps: vec![create_http_step("step1", "GET", "/test")],
        };

        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(matches!(
            &errors[0],
            ValidationError::UnsupportedSpecVersion { version, expected }
            if version == "0.2" && expected == "0.1"
        ));
    }

    #[test]
    fn test_sleep_action_is_valid() {
        let plan = create_test_plan(vec![Step {
            id: "sleep1".to_string(),
            description: None,
            depends_on: vec![],
            action: "sleep".to_string(), // Alias de wait
            params: json!({ "duration_ms": 100 }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }]);

        let result = validate_plan(&plan);
        assert!(result.is_ok());
    }

    // ========================================================================
    // TESTES DE CICLOS NO DAG
    // ========================================================================

    #[test]
    fn test_circular_dependency_two_nodes() {
        // A → B → A (ciclo simples entre dois nós)
        let plan = create_test_plan(vec![
            Step {
                id: "A".to_string(),
                description: None,
                depends_on: vec!["B".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/a" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "B".to_string(),
                description: None,
                depends_on: vec!["A".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/b" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
        ]);

        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(errors.iter().any(|e| matches!(e, ValidationError::CircularDependency { .. })));
    }

    #[test]
    fn test_circular_dependency_three_nodes() {
        // A → B → C → A (ciclo complexo com três nós)
        let plan = create_test_plan(vec![
            Step {
                id: "A".to_string(),
                description: None,
                depends_on: vec!["C".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/a" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "B".to_string(),
                description: None,
                depends_on: vec!["A".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/b" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "C".to_string(),
                description: None,
                depends_on: vec!["B".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/c" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
        ]);

        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(errors.iter().any(|e| matches!(e, ValidationError::CircularDependency { .. })));
    }

    #[test]
    fn test_valid_dag_no_cycles() {
        // Grafo válido sem ciclos:
        //     A
        //    / \
        //   B   C
        //    \ /
        //     D
        let plan = create_test_plan(vec![
            Step {
                id: "A".to_string(),
                description: None,
                depends_on: vec![],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/a" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "B".to_string(),
                description: None,
                depends_on: vec!["A".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/b" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "C".to_string(),
                description: None,
                depends_on: vec!["A".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/c" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "D".to_string(),
                description: None,
                depends_on: vec!["B".to_string(), "C".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/d" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
        ]);

        let result = validate_plan(&plan);
        assert!(result.is_ok());
    }

    #[test]
    fn test_partial_cycle_in_dag() {
        // Grafo com ciclo parcial:
        // A → B (ok)
        // C → D → C (ciclo)
        let plan = create_test_plan(vec![
            Step {
                id: "A".to_string(),
                description: None,
                depends_on: vec![],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/a" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "B".to_string(),
                description: None,
                depends_on: vec!["A".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/b" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "C".to_string(),
                description: None,
                depends_on: vec!["D".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/c" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
            Step {
                id: "D".to_string(),
                description: None,
                depends_on: vec!["C".to_string()],
                action: "http_request".to_string(),
                params: json!({ "method": "GET", "path": "/d" }),
                assertions: vec![],
                extract: vec![],
                recovery_policy: None,
            },
        ]);

        let result = validate_plan(&plan);
        assert!(result.is_err());
        let errors = result.unwrap_err();
        assert!(errors.iter().any(|e| matches!(e, ValidationError::CircularDependency { .. })));
    }
}
