//! # Módulo de Planejamento e Execução Paralela (DAG)
//!
//! Este módulo implementa um sistema de execução inteligente que roda
//! steps em paralelo quando possível, respeitando dependências.
//!
//! ## Para todos entenderem:
//!
//! Imagine que você tem uma lista de tarefas para fazer na casa:
//! - Lavar roupa (não depende de nada)
//! - Fazer café (não depende de nada)
//! - Dobrar roupa (depende de "lavar roupa")
//! - Tomar café (depende de "fazer café")
//!
//! Um DAG (Directed Acyclic Graph - Grafo Direcionado Acíclico) organiza
//! essas tarefas de forma que você pode fazer "lavar roupa" e "fazer café"
//! AO MESMO TEMPO, porque elas não dependem uma da outra.
//!
//! Depois que "lavar roupa" terminar, você pode "dobrar roupa".
//! E depois que "fazer café" terminar, você pode "tomar café".
//!
//! ## Por que isso é importante?
//!
//! - **Velocidade**: Executar em paralelo é mais rápido
//! - **Eficiência**: Usa melhor os recursos do computador
//! - **Corretude**: Garante que dependências são respeitadas
//!
//! ## Conceitos:
//!
//! - **Nó (Node)**: Cada step é um nó no grafo
//! - **Aresta (Edge)**: Dependência entre steps
//! - **Raiz (Root)**: Step sem dependências (pode começar imediatamente)
//! - **DAG**: Grafo que não tem ciclos (A→B→C é ok, A→B→A é proibido)
//!
//! ## Exemplo visual:
//!
//! ```text
//!     [A]     [B]     <- Raízes (podem rodar em paralelo)
//!      |       |
//!      v       v
//!     [C]     [D]     <- Dependem de A e B respectivamente
//!      |       |
//!      +---+---+
//!          |
//!          v
//!         [E]         <- Depende de C e D (só roda quando ambos terminam)
//! ```

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock, Semaphore};
use tokio::task::JoinSet;
use tracing::{info, error, instrument};

use crate::context::Context;
use crate::executors::StepExecutor;
use crate::limits::ExecutionLimits;
use crate::protocol::{Step, StepResult, StepStatus};

// ============================================================================
// ESTRUTURA DO NÓ DE EXECUÇÃO
// ============================================================================

/// Representa um nó no grafo de execução (DAG).
///
/// Cada step do plano se torna um ExecutionNode com informações
/// sobre suas dependências e quem depende dele.
///
/// ## Para todos entenderem:
///
/// É como uma ficha de tarefa que diz:
/// - Qual é a tarefa (step)
/// - O que preciso terminar antes (dependencies)
/// - O que posso liberar quando terminar (dependents)
#[derive(Debug)]
struct ExecutionNode {
    /// O step a ser executado.
    step: Step,

    /// IDs dos steps que ESTE step depende.
    /// Exemplo: Se este step tem depends_on: ["A", "B"],
    /// então dependencies = {"A", "B"}
    dependencies: HashSet<String>,

    /// IDs dos steps que DEPENDEM deste step.
    /// Exemplo: Se steps C e D têm depends_on contendo nosso ID,
    /// então dependents = {"C", "D"}
    dependents: HashSet<String>,
}

// ============================================================================
// DAG PLANNER
// ============================================================================

/// Planejador que constrói e executa o DAG de steps.
///
/// O DagPlanner analisa as dependências entre steps e organiza
/// a execução de forma a maximizar o paralelismo.
///
/// ## Fluxo de uso:
///
/// 1. `DagPlanner::new(steps)` - Constrói o grafo
/// 2. `planner.execute(executors, context)` - Executa tudo
///
/// ## Thread Safety:
///
/// A execução usa locks e mutexes para garantir que múltiplas
/// tasks podem rodar em paralelo sem corromper dados.
pub struct DagPlanner {
    /// Mapa de ID do step → Nó de execução.
    /// HashMap é como um dicionário: chave → valor.
    nodes: HashMap<String, ExecutionNode>,

    /// Steps que não têm dependências (raízes do DAG).
    /// Estes podem começar a executar imediatamente.
    roots: Vec<String>,
}

impl DagPlanner {
    /// Cria um novo planner a partir de uma lista de steps.
    ///
    /// Este construtor analisa todos os steps e:
    /// 1. Cria um nó para cada step
    /// 2. Identifica dependências
    /// 3. Calcula quem depende de quem (relação inversa)
    /// 4. Encontra as raízes (steps sem dependências)
    ///
    /// ## Parâmetros:
    ///
    /// - `steps`: Lista de steps do plano
    ///
    /// ## Retorno:
    ///
    /// Um DagPlanner pronto para executar.
    pub fn new(steps: Vec<Step>) -> Self {
        let mut nodes = HashMap::new();

        // Mapa auxiliar: step_id → quem depende dele.
        // Usado para preencher o campo `dependents` de cada nó.
        let mut dependents_map: HashMap<String, HashSet<String>> = HashMap::new();

        // Primeira passagem: criar nós e mapear dependentes.
        for step in steps {
            // Converte Vec<String> para HashSet<String>.
            // HashSet é mais eficiente para verificar se contém algo.
            let deps: HashSet<String> = step.depends_on.iter().cloned().collect();

            // Para cada dependência deste step, registra que este step
            // depende dela (para depois preencher `dependents`).
            for dep in &deps {
                dependents_map
                    .entry(dep.clone())       // Pega ou cria entrada
                    .or_default()             // Se não existe, cria HashSet vazio
                    .insert(step.id.clone()); // Adiciona este step como dependente
            }

            // Cria o nó (ainda sem dependents preenchido).
            nodes.insert(
                step.id.clone(),
                ExecutionNode {
                    step,
                    dependencies: deps,
                    dependents: HashSet::new(),
                },
            );
        }

        // Segunda passagem: preencher dependents de cada nó.
        for (step_id, deps) in dependents_map {
            if let Some(node) = nodes.get_mut(&step_id) {
                node.dependents = deps;
            }
        }

        // Encontra raízes: steps que não dependem de ninguém.
        // Estes podem começar a executar imediatamente.
        let roots: Vec<String> = nodes
            .iter()
            .filter(|(_, node)| node.dependencies.is_empty())
            .map(|(id, _)| id.clone())
            .collect();

        info!(root_count = roots.len(), total_steps = nodes.len(), "DAG construído");

        Self { nodes, roots }
    }

    // ========================================================================
    // EXECUÇÃO DO DAG
    // ========================================================================

    /// Executa todos os steps respeitando dependências, com máximo paralelismo.
    ///
    /// Este é o coração do sistema de execução paralela.
    ///
    /// ## Algoritmo:
    ///
    /// 1. Começa com as raízes (steps sem dependências)
    /// 2. Executa todos que estão prontos em paralelo (até max_parallel)
    /// 3. Quando um step termina com sucesso, libera seus dependentes
    /// 4. Quando um step falha, marca seus dependentes como "skipped"
    /// 5. Repete até todos os steps serem processados
    ///
    /// ## Parâmetros:
    ///
    /// - `executors`: Lista de executores disponíveis
    /// - `context`: Contexto compartilhado (variáveis, etc.)
    /// - `limits`: Limites de execução (max_parallel, timeouts, etc.)
    ///
    /// ## Retorno:
    ///
    /// Vec<StepResult> com o resultado de cada step executado.
    ///
    /// ## Thread Safety:
    ///
    /// Usamos `Arc` (referência contada) e locks (`Mutex`, `RwLock`)
    /// para garantir acesso seguro aos dados compartilhados.
    /// Um `Semaphore` controla o número máximo de steps em paralelo.
    #[instrument(skip(self, executors, context, limits))]
    pub async fn execute(
        self,
        executors: Arc<Vec<Box<dyn StepExecutor + Send + Sync>>>,
        context: Arc<RwLock<Context>>,
        limits: ExecutionLimits,
    ) -> Vec<StepResult> {
        // Semáforo para limitar paralelismo.
        // Se max_parallel = 0, usamos número de steps (sem limite efetivo).
        let max_parallel = if limits.max_parallel > 0 {
            limits.max_parallel as usize
        } else {
            self.nodes.len().max(1)
        };
        let semaphore = Arc::new(Semaphore::new(max_parallel));
        info!(max_parallel = max_parallel, "DAG executor initialized with concurrency limit");

        // Resultados de cada step (compartilhado entre tasks).
        let results: Arc<Mutex<Vec<StepResult>>> = Arc::new(Mutex::new(Vec::new()));

        // Set de steps já completados com sucesso.
        let completed: Arc<RwLock<HashSet<String>>> = Arc::new(RwLock::new(HashSet::new()));

        // Set de steps que falharam.
        let failed: Arc<RwLock<HashSet<String>>> = Arc::new(RwLock::new(HashSet::new()));

        // Nós do grafo (compartilhado para lookup de dependências).
        let nodes = Arc::new(RwLock::new(self.nodes));

        // Fila de steps prontos para executar.
        // Começa com as raízes.
        let ready: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(self.roots));

        // Loop principal de execução.
        loop {
            // Pega todos os steps que estão prontos para executar.
            // `std::mem::take` esvazia o vetor e retorna seu conteúdo.
            let to_execute: Vec<String> = {
                let mut ready_guard = ready.lock().await;
                std::mem::take(&mut *ready_guard)
            };

            // Se não há steps prontos, verifica se terminamos.
            if to_execute.is_empty() {
                let completed_guard = completed.read().await;
                let nodes_guard = nodes.read().await;

                // Se todos os steps foram processados (sucesso + falha), terminamos.
                if completed_guard.len() + failed.read().await.len() >= nodes_guard.len() {
                    break;
                }

                // Ainda há steps em execução, aguarda um pouco.
                tokio::time::sleep(std::time::Duration::from_millis(10)).await;
                continue;
            }

            // Executa todos os steps prontos em paralelo.
            // JoinSet é um conjunto de tasks que podemos aguardar juntas.
            let mut join_set = JoinSet::new();

            for step_id in to_execute {
                // Clona as referências Arc para a task.
                // Arc permite múltiplas referências ao mesmo dado.
                let nodes_clone = Arc::clone(&nodes);
                let executors_clone = Arc::clone(&executors);
                let context_clone = Arc::clone(&context);
                let results_clone = Arc::clone(&results);
                let completed_clone = Arc::clone(&completed);
                let failed_clone = Arc::clone(&failed);
                let ready_clone = Arc::clone(&ready);
                let semaphore_clone = Arc::clone(&semaphore);

                // Spawna uma nova task assíncrona para este step.
                join_set.spawn(async move {
                    // Adquire permit do semáforo para controlar paralelismo.
                    // Isso garante que no máximo max_parallel steps rodem ao mesmo tempo.
                    let _permit = semaphore_clone.acquire().await.expect("Semaphore closed");

                    // Obtém o step do nó.
                    let step = {
                        let nodes_guard = nodes_clone.read().await;
                        nodes_guard.get(&step_id).map(|n| n.step.clone())
                    };

                    // Se não encontrou o step, retorna (não deveria acontecer).
                    let step = match step {
                        Some(s) => s,
                        None => return,
                    };

                    // Verifica se alguma dependência falhou.
                    // Se sim, pula este step.
                    let failed_dep = {
                        let failed_guard = failed_clone.read().await;
                        let nodes_guard = nodes_clone.read().await;
                        let mut found_failed_dep: Option<String> = None;
                        if let Some(node) = nodes_guard.get(&step_id) {
                            for dep in &node.dependencies {
                                if failed_guard.contains(dep) {
                                    found_failed_dep = Some(dep.clone());
                                    break;
                                }
                            }
                        }
                        found_failed_dep
                    }; // Guards são dropados aqui

                    if let Some(dep) = failed_dep {
                        // Pula este step porque uma dependência falhou
                        info!(step_id = %step_id, failed_dep = %dep, "Skipping step due to failed dependency");

                        // Captura contexto atual para debug
                        let ctx = context_clone.read().await;
                        let context_snapshot = ctx.variables.clone();
                        drop(ctx); // Libera o lock explicitamente
                        let result = StepResult {
                            step_id: step_id.clone(),
                            status: StepStatus::Skipped,
                            duration_ms: 0,
                            error: Some(format!("Dependency '{}' failed", dep)),
                            context_before: Some(context_snapshot.clone()),
                            context_after: Some(context_snapshot),
                            extractions: None,
                        };

                        results_clone.lock().await.push(result);
                        failed_clone.write().await.insert(step_id.clone());
                        return;
                    }

                    // Encontra executor
                    let executor = executors_clone
                        .iter()
                        .find(|e| e.can_handle(&step.action));

                    let result = match executor {
                        Some(exec) => {
                            let mut ctx = context_clone.write().await;
                            // Snapshot do contexto antes da execução
                            let context_before = ctx.variables.clone();
                            match exec.execute(&step, &mut ctx).await {
                                Ok(r) => r,
                                Err(e) => {
                                    error!(step_id = %step_id, error = %e, "Step execution failed");
                                    // Captura contexto após erro para debug
                                    let context_after = ctx.variables.clone();
                                    StepResult {
                                        step_id: step_id.clone(),
                                        status: StepStatus::Failed,
                                        duration_ms: 0,
                                        error: Some(e.to_string()),
                                        context_before: Some(context_before),
                                        context_after: Some(context_after),
                                        extractions: None,
                                    }
                                }
                            }
                        }
                        None => {
                            // Sem executor - captura contexto atual para debug
                            let ctx = context_clone.read().await;
                            let context_snapshot = ctx.variables.clone();
                            StepResult {
                                step_id: step_id.clone(),
                                status: StepStatus::Failed,
                                duration_ms: 0,
                                error: Some(format!("No executor for action: {}", step.action)),
                                context_before: Some(context_snapshot.clone()),
                                context_after: Some(context_snapshot),
                                extractions: None,
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

                    // Libera dependentes para processamento
                    // Se passou: dependentes podem executar normalmente
                    // Se falhou: dependentes serão marcados como skipped
                    //
                    // NOTA: Adquirimos todos os locks necessários de uma vez para evitar deadlock
                    let dependents_to_add: Vec<String> = {
                        let nodes_guard = nodes_clone.read().await;
                        let completed_guard = completed_clone.read().await;
                        let failed_guard = failed_clone.read().await;

                        let mut to_add = Vec::new();
                        if let Some(node) = nodes_guard.get(&step_id) {
                            for dependent_id in &node.dependents {
                                if let Some(dependent_node) = nodes_guard.get(dependent_id) {
                                    // Verifica se todas as deps foram processadas (passou ou falhou)
                                    let all_deps_processed = dependent_node
                                        .dependencies
                                        .iter()
                                        .all(|d| completed_guard.contains(d) || failed_guard.contains(d));

                                    if all_deps_processed {
                                        to_add.push(dependent_id.clone());
                                    }
                                }
                            }
                        }
                        to_add
                    };

                    // Agora adiciona à fila ready (lock separado)
                    if !dependents_to_add.is_empty() {
                        let mut ready_guard = ready_clone.lock().await;
                        ready_guard.extend(dependents_to_add);
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

    fn create_step_with_action(id: &str, action: &str) -> Step {
        Step {
            id: id.to_string(),
            description: None,
            depends_on: vec![],
            action: action.to_string(),
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

    #[tokio::test]
    async fn test_context_snapshots_on_no_executor() {
        // Testa que context_before/after são preenchidos quando não há executor
        let steps = vec![create_step_with_action("unknown_step", "unknown_action")];
        let planner = DagPlanner::new(steps);

        let mut context = Context::new();
        context.set("test_var", json!("test_value"));

        // Sem executores, o step deve falhar com "No executor"
        let executors: Arc<Vec<Box<dyn StepExecutor + Send + Sync>>> = Arc::new(vec![]);
        let context = Arc::new(RwLock::new(context));
        let limits = ExecutionLimits::default();

        let results = planner.execute(executors, context, limits).await;

        assert_eq!(results.len(), 1);
        let result = &results[0];

        assert_eq!(result.status, StepStatus::Failed);
        assert!(result.error.as_ref().unwrap().contains("No executor"));

        // Verifica que context_before e context_after estão preenchidos
        assert!(result.context_before.is_some(), "context_before should be Some");
        assert!(result.context_after.is_some(), "context_after should be Some");

        // Verifica que contêm a variável de teste
        let ctx_before = result.context_before.as_ref().unwrap();
        assert_eq!(ctx_before.get("test_var").unwrap(), &json!("test_value"));
    }

    #[tokio::test]
    async fn test_context_snapshots_on_skipped_step() {
        // Testa que context snapshots são preenchidos quando step é pulado
        // step_a vai falhar (sem executor), step_b depende de step_a e será pulado
        let step_a = Step {
            id: "step_a".to_string(),
            description: None,
            depends_on: vec![],
            action: "unknown_action".to_string(),
            params: json!({}),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        };
        let step_b = Step {
            id: "step_b".to_string(),
            description: None,
            depends_on: vec!["step_a".to_string()],
            action: "http_request".to_string(),
            params: json!({ "method": "GET", "path": "/test" }),
            assertions: vec![],
            extract: vec![],
            recovery_policy: None,
        };

        let planner = DagPlanner::new(vec![step_a, step_b]);

        let mut context = Context::new();
        context.set("initial_var", json!(42));

        let executors: Arc<Vec<Box<dyn StepExecutor + Send + Sync>>> = Arc::new(vec![]);
        let context = Arc::new(RwLock::new(context));
        let limits = ExecutionLimits::default();

        let results = planner.execute(executors, context, limits).await;

        assert_eq!(results.len(), 2);

        // Encontra o step pulado
        let skipped = results.iter().find(|r| r.step_id == "step_b").unwrap();

        assert_eq!(skipped.status, StepStatus::Skipped);
        assert!(skipped.context_before.is_some(), "Skipped step should have context_before");
        assert!(skipped.context_after.is_some(), "Skipped step should have context_after");

        // Verifica que a variável inicial está presente
        let ctx = skipped.context_before.as_ref().unwrap();
        assert_eq!(ctx.get("initial_var").unwrap(), &json!(42));
    }
}
