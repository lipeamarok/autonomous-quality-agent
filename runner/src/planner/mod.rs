//! Módulo de Planejamento e Execução Paralela.
//!
//! Implementa um DAG (Directed Acyclic Graph) para executar steps
//! em paralelo quando não há dependências entre eles.

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};
use tokio::task::JoinSet;
use tracing::{info, error, instrument};

use crate::context::Context;
use crate::executors::StepExecutor;
use crate::protocol::{Step, StepResult, StepStatus};

/// Representa um nó no grafo de execução.
#[derive(Debug)]
struct ExecutionNode {
    step: Step,
    /// IDs dos steps que este step depende
    dependencies: HashSet<String>,
    /// IDs dos steps que dependem deste step
    dependents: HashSet<String>,
}

/// Planner que constrói e executa o DAG de steps.
pub struct DagPlanner {
    nodes: HashMap<String, ExecutionNode>,
    /// Steps que não têm dependências (raízes do DAG)
    roots: Vec<String>,
}

impl DagPlanner {
    /// Cria um novo planner a partir de uma lista de steps.
    pub fn new(steps: Vec<Step>) -> Self {
        let mut nodes = HashMap::new();
        let mut dependents_map: HashMap<String, HashSet<String>> = HashMap::new();

        // Primeira passagem: criar nós
        for step in steps {
            let deps: HashSet<String> = step.depends_on.iter().cloned().collect();

            // Registra este step como dependente de cada uma de suas dependências
            for dep in &deps {
                dependents_map
                    .entry(dep.clone())
                    .or_default()
                    .insert(step.id.clone());
            }

            nodes.insert(
                step.id.clone(),
                ExecutionNode {
                    step,
                    dependencies: deps,
                    dependents: HashSet::new(),
                },
            );
        }

        // Segunda passagem: preencher dependents
        for (step_id, deps) in dependents_map {
            if let Some(node) = nodes.get_mut(&step_id) {
                node.dependents = deps;
            }
        }

        // Encontra raízes (steps sem dependências)
        let roots: Vec<String> = nodes
            .iter()
            .filter(|(_, node)| node.dependencies.is_empty())
            .map(|(id, _)| id.clone())
            .collect();

        info!(root_count = roots.len(), total_steps = nodes.len(), "DAG built");

        Self { nodes, roots }
    }

    /// Executa todos os steps respeitando dependências, com máximo paralelismo.
    #[instrument(skip(self, executors, context))]
    pub async fn execute(
        self,
        executors: Arc<Vec<Box<dyn StepExecutor + Send + Sync>>>,
        context: Arc<RwLock<Context>>,
    ) -> Vec<StepResult> {
        let results: Arc<Mutex<Vec<StepResult>>> = Arc::new(Mutex::new(Vec::new()));
        let completed: Arc<RwLock<HashSet<String>>> = Arc::new(RwLock::new(HashSet::new()));
        let failed: Arc<RwLock<HashSet<String>>> = Arc::new(RwLock::new(HashSet::new()));
        let nodes = Arc::new(RwLock::new(self.nodes));

        // Fila de steps prontos para executar
        let ready: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(self.roots));

        loop {
            // Pega todos os steps prontos
            let to_execute: Vec<String> = {
                let mut ready_guard = ready.lock().await;
                std::mem::take(&mut *ready_guard)
            };

            if to_execute.is_empty() {
                // Verifica se ainda há steps pendentes
                let completed_guard = completed.read().await;
                let nodes_guard = nodes.read().await;

                if completed_guard.len() + failed.read().await.len() >= nodes_guard.len() {
                    break; // Todos os steps foram processados
                }

                // Espera um pouco e tenta novamente (pode haver steps em execução)
                tokio::time::sleep(std::time::Duration::from_millis(10)).await;
                continue;
            }

            // Executa steps em paralelo
            let mut join_set = JoinSet::new();

            for step_id in to_execute {
                let nodes_clone = Arc::clone(&nodes);
                let executors_clone = Arc::clone(&executors);
                let context_clone = Arc::clone(&context);
                let results_clone = Arc::clone(&results);
                let completed_clone = Arc::clone(&completed);
                let failed_clone = Arc::clone(&failed);
                let ready_clone = Arc::clone(&ready);

                join_set.spawn(async move {
                    // Obtém o step
                    let step = {
                        let nodes_guard = nodes_clone.read().await;
                        nodes_guard.get(&step_id).map(|n| n.step.clone())
                    };

                    let step = match step {
                        Some(s) => s,
                        None => return,
                    };

                    // Verifica se alguma dependência falhou
                    {
                        let failed_guard = failed_clone.read().await;
                        let nodes_guard = nodes_clone.read().await;
                        if let Some(node) = nodes_guard.get(&step_id) {
                            for dep in &node.dependencies {
                                if failed_guard.contains(dep) {
                                    // Pula este step porque uma dependência falhou
                                    info!(step_id = %step_id, failed_dep = %dep, "Skipping step due to failed dependency");

                                    let result = StepResult {
                                        step_id: step_id.clone(),
                                        status: StepStatus::Skipped,
                                        duration_ms: 0,
                                        error: Some(format!("Dependency '{}' failed", dep)),
                                    };

                                    results_clone.lock().await.push(result);
                                    failed_clone.write().await.insert(step_id.clone());
                                    return;
                                }
                            }
                        }
                    }

                    // Encontra executor
                    let executor = executors_clone
                        .iter()
                        .find(|e| e.can_handle(&step.action));

                    let result = match executor {
                        Some(exec) => {
                            let mut ctx = context_clone.write().await;
                            match exec.execute(&step, &mut ctx).await {
                                Ok(r) => r,
                                Err(e) => {
                                    error!(step_id = %step_id, error = %e, "Step execution failed");
                                    StepResult {
                                        step_id: step_id.clone(),
                                        status: StepStatus::Failed,
                                        duration_ms: 0,
                                        error: Some(e.to_string()),
                                    }
                                }
                            }
                        }
                        None => {
                            StepResult {
                                step_id: step_id.clone(),
                                status: StepStatus::Failed,
                                duration_ms: 0,
                                error: Some(format!("No executor for action: {}", step.action)),
                            }
                        }
                    };

                    let passed = result.status == StepStatus::Passed;
                    info!(step_id = %step_id, status = ?result.status, "Step completed");

                    // Registra resultado
                    results_clone.lock().await.push(result);

                    if passed {
                        completed_clone.write().await.insert(step_id.clone());
                    } else {
                        failed_clone.write().await.insert(step_id.clone());
                    }

                    // Libera dependentes se este step passou
                    if passed {
                        let nodes_guard = nodes_clone.read().await;
                        if let Some(node) = nodes_guard.get(&step_id) {
                            for dependent_id in &node.dependents {
                                // Verifica se todas as dependências do dependente foram completadas
                                if let Some(dependent_node) = nodes_guard.get(dependent_id) {
                                    let completed_guard = completed_clone.read().await;
                                    let all_deps_met = dependent_node
                                        .dependencies
                                        .iter()
                                        .all(|d| completed_guard.contains(d));

                                    if all_deps_met {
                                        ready_clone.lock().await.push(dependent_id.clone());
                                    }
                                }
                            }
                        }
                    }
                });
            }

            // Aguarda todas as tasks deste lote
            while join_set.join_next().await.is_some() {}
        }

        // Retorna resultados ordenados pela ordem original (aproximada)
        let final_results = results.lock().await;
        final_results.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn create_step(id: &str, deps: Vec<&str>) -> Step {
        Step {
            id: id.to_string(),
            description: None,
            depends_on: deps.into_iter().map(String::from).collect(),
            action: "http_request".to_string(),
            params: json!({ "method": "GET", "path": "/test" }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        }
    }

    #[test]
    fn test_dag_identifies_roots() {
        let steps = vec![
            create_step("A", vec![]),
            create_step("B", vec!["A"]),
            create_step("C", vec!["A"]),
            create_step("D", vec!["B", "C"]),
        ];

        let planner = DagPlanner::new(steps);

        assert_eq!(planner.roots.len(), 1);
        assert!(planner.roots.contains(&"A".to_string()));
    }

    #[test]
    fn test_dag_multiple_roots() {
        let steps = vec![
            create_step("A", vec![]),
            create_step("B", vec![]),
            create_step("C", vec!["A", "B"]),
        ];

        let planner = DagPlanner::new(steps);

        assert_eq!(planner.roots.len(), 2);
        assert!(planner.roots.contains(&"A".to_string()));
        assert!(planner.roots.contains(&"B".to_string()));
    }

    #[test]
    fn test_dag_dependents_tracking() {
        let steps = vec![
            create_step("A", vec![]),
            create_step("B", vec!["A"]),
            create_step("C", vec!["A"]),
        ];

        let planner = DagPlanner::new(steps);

        let node_a = planner.nodes.get("A").unwrap();
        assert!(node_a.dependents.contains("B"));
        assert!(node_a.dependents.contains("C"));
    }
}
