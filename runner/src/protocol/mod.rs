//! # Módulo de Protocolo UTDL - Estruturas de Dados
//!
//! Este módulo define todas as **estruturas de dados** que representam
//! um plano de testes UTDL (Universal Test Definition Language).
//!
//! ## O que é UTDL?
//!
//! UTDL é o "idioma" que o Brain e o Runner usam para se comunicar.
//! É um formato JSON com uma estrutura bem definida que descreve:
//! - **O quê** testar (endpoints, payloads)
//! - **Como** validar (assertions)
//! - **O que fazer** em caso de falha (recovery policy)
//!
//! ## Estrutura de um Plano UTDL:
//!
//! ```json
//! {
//!   "spec_version": "0.1",           // Versão do formato
//!   "meta": {                         // Metadados do plano
//!     "id": "uuid",
//!     "name": "Login Test",
//!     "description": "...",
//!     "tags": ["api", "auth"],
//!     "created_at": "2024-01-15T..."
//!   },
//!   "config": {                       // Configurações globais
//!     "base_url": "https://api.example.com",
//!     "timeout_ms": 5000,
//!     "global_headers": {},
//!     "variables": {}
//!   },
//!   "steps": [...]                    // Lista de steps a executar
//! }
//! ```
//!
//! ## Hierarquia de Tipos:
//!
//! ```text
//! Plan
//! ├── Meta (metadados)
//! ├── Config (configurações)
//! └── Steps[] (lista de passos)
//!     ├── Assertion[] (validações)
//!     ├── Extraction[] (extração de dados)
//!     └── RecoveryPolicy (política de retry)
//! ```

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

use crate::extractors::ExtractionResult;

// ============================================================================
// ESTRUTURA PRINCIPAL: PLAN
// ============================================================================

/// Representa um plano de testes UTDL completo.
///
/// Esta é a estrutura raiz que contém todo o plano de testes.
/// Corresponde ao JSON completo do arquivo `.utdl.json`.
///
/// ## Campos:
/// - `spec_version`: Versão do formato UTDL (ex: "0.1")
/// - `meta`: Metadados como ID, nome, descrição
/// - `config`: Configurações globais (base_url, timeout, etc.)
/// - `steps`: Lista de passos a executar
///
/// ## Atributos:
/// - `#[derive(Deserialize)]`: Permite ler de JSON
/// - `#[derive(Serialize)]`: Permite escrever para JSON
/// - `#[derive(Debug)]`: Permite imprimir para debug
#[derive(Debug, Deserialize, Serialize)]
pub struct Plan {
    /// Versão do schema UTDL.
    ///
    /// Atualmente suportada: "0.1"
    /// O Runner valida esta versão antes de executar.
    pub spec_version: String,

    /// Metadados do plano (ID, nome, descrição, tags, etc.).
    pub meta: Meta,

    /// Configurações globais (base_url, timeout, headers, variáveis).
    pub config: Config,

    /// Lista de steps (passos) a executar.
    ///
    /// Cada step é uma ação atômica (requisição HTTP, wait, etc.).
    pub steps: Vec<Step>,
}

// ============================================================================
// METADADOS: META
// ============================================================================

/// Metadados do plano de testes.
///
/// Informações descritivas que não afetam a execução,
/// mas são úteis para organização e rastreabilidade.
#[derive(Debug, Deserialize, Serialize)]
pub struct Meta {
    /// Identificador único do plano (geralmente UUID v4).
    ///
    /// Usado para rastrear execuções e correlacionar relatórios.
    pub id: String,

    /// Nome legível do plano.
    ///
    /// Ex: "Login Flow Test", "User CRUD Operations"
    pub name: String,

    /// Descrição opcional do plano.
    ///
    /// Pode conter detalhes sobre o que o teste valida.
    #[serde(default)] // Se não existir no JSON, usa None
    pub description: Option<String>,

    /// Tags para categorização.
    ///
    /// Ex: ["api", "auth", "critical", "regression"]
    /// Útil para filtrar quais testes executar.
    #[serde(default)] // Se não existir, usa vetor vazio
    pub tags: Vec<String>,

    /// Data/hora de criação em formato ISO8601.
    ///
    /// Ex: "2024-01-15T12:00:00Z"
    pub created_at: String,
}

// ============================================================================
// CONFIGURAÇÕES: CONFIG
// ============================================================================

/// Configurações globais do plano.
///
/// Estas configurações se aplicam a todos os steps do plano.
#[derive(Debug, Deserialize, Serialize)]
pub struct Config {
    /// URL base para requisições HTTP.
    ///
    /// Os paths dos steps são concatenados a esta URL.
    /// Ex: "https://api.example.com" + "/users" = "https://api.example.com/users"
    pub base_url: String,

    /// Timeout padrão em milissegundos.
    ///
    /// Se uma requisição não responder neste tempo, é considerada falha.
    /// Valor típico: 5000 (5 segundos)
    pub timeout_ms: u64,

    /// Headers que serão enviados em todas as requisições.
    ///
    /// Ex: { "Content-Type": "application/json", "X-API-Version": "v1" }
    #[serde(default)]
    pub global_headers: HashMap<String, String>,

    /// Variáveis disponíveis para interpolação.
    ///
    /// Podem ser usadas em qualquer string com ${nome_variavel}.
    /// Ex: { "env": "staging", "admin_email": "admin@test.com" }
    #[serde(default)]
    pub variables: HashMap<String, Value>,
}

// ============================================================================
// PASSO DE EXECUÇÃO: STEP
// ============================================================================

/// Representa um passo (step) de execução.
///
/// Cada step é uma **ação atômica** que o Runner executa.
/// Pode ser uma requisição HTTP, uma espera, ou outras ações.
///
/// ## Campos obrigatórios:
/// - `id`: Identificador único dentro do plano
/// - `action`: Tipo de ação ("http_request", "wait", "sleep")
/// - `params`: Parâmetros específicos da ação
///
/// ## Campos opcionais:
/// - `description`: Texto descritivo para logs
/// - `depends_on`: IDs de steps que devem executar antes
/// - `assertions`: Validações a fazer após a execução
/// - `extract`: Dados a extrair da resposta
/// - `recovery_policy`: O que fazer em caso de falha
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Step {
    /// Identificador único do step dentro do plano.
    ///
    /// Deve ser único. Usado em `depends_on` e nos relatórios.
    /// Ex: "login_step", "create_user", "verify_response"
    pub id: String,

    /// Descrição legível do step (opcional).
    ///
    /// Aparece nos logs para facilitar o debugging.
    /// Ex: "Faz login com credenciais de admin"
    #[serde(default)]
    pub description: Option<String>,

    /// Lista de IDs de steps que devem executar antes deste.
    ///
    /// Permite criar um DAG (grafo acíclico direcionado) de dependências.
    /// Steps sem dependências podem executar em paralelo.
    ///
    /// Ex: ["login_step"] significa que este step só roda após "login_step"
    #[serde(default)]
    pub depends_on: Vec<String>,

    /// Tipo de ação a executar.
    ///
    /// Valores suportados:
    /// - "http_request": Faz uma requisição HTTP
    /// - "wait": Espera um tempo em milissegundos
    /// - "sleep": Alias de "wait"
    pub action: String,

    /// Parâmetros específicos da ação.
    ///
    /// O conteúdo varia conforme a action:
    ///
    /// Para "http_request":
    /// ```json
    /// {
    ///   "method": "POST",
    ///   "path": "/users",
    ///   "headers": { "Authorization": "Bearer ${token}" },
    ///   "body": { "name": "João" }
    /// }
    /// ```
    ///
    /// Para "wait"/"sleep":
    /// ```json
    /// { "duration_ms": 1000 }
    /// ```
    pub params: Value,

    /// Lista de validações a fazer após a execução.
    ///
    /// Se qualquer assertion falhar, o step falha.
    #[serde(default)]
    pub assertions: Vec<Assertion>,

    /// Regras para extrair dados da resposta.
    ///
    /// Os dados extraídos ficam disponíveis para steps seguintes.
    #[serde(default)]
    pub extract: Vec<Extraction>,

    /// Política de recuperação em caso de falha.
    ///
    /// Define se deve fazer retry, ignorar, ou falhar imediatamente.
    #[serde(default)]
    pub recovery_policy: Option<RecoveryPolicy>,
}

// ============================================================================
// VALIDAÇÃO: ASSERTION
// ============================================================================

/// Define uma validação a ser feita após a execução do step.
///
/// Assertions são como "testes dentro do teste". Elas verificam
/// se a resposta está correta.
///
/// ## Tipos de Assertion:
/// - `status_code`: Valida o código HTTP (200, 201, 404, etc.)
/// - `json_body`: Valida um campo específico do JSON de resposta
/// - `header`: Valida um header da resposta
/// - `latency`: Valida o tempo de resposta
///
/// ## Operadores:
/// - `eq`: Igual
/// - `neq`: Diferente
/// - `lt`, `gt`: Menor que, maior que
/// - `lte`, `gte`: Menor ou igual, maior ou igual
/// - `contains`: Contém substring
/// - `exists`, `not_exists`: Campo existe ou não
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Assertion {
    /// Tipo de assertion.
    ///
    /// Valores: "status_code", "json_body", "header", "latency"
    #[serde(rename = "type")] // No JSON é "type", mas em Rust "type" é palavra reservada
    pub assertion_type: String,

    /// Operador de comparação.
    ///
    /// Valores: "eq", "neq", "lt", "gt", "lte", "gte", "contains", "exists"
    pub operator: String,

    /// Valor esperado para a comparação.
    ///
    /// O tipo depende da assertion:
    /// - status_code: número (ex: 200)
    /// - json_body: qualquer valor JSON
    /// - header: string
    /// - latency: número em ms
    pub value: Value,

    /// Caminho para o campo (usado em json_body e header).
    ///
    /// Para json_body: JSONPath ou caminho com pontos (ex: "data.user.id")
    /// Para header: nome do header (ex: "Content-Type")
    #[serde(default)]
    pub path: Option<String>,
}

// ============================================================================
// EXTRAÇÃO DE DADOS: EXTRACTION
// ============================================================================

/// Define uma regra para extrair dados da resposta.
///
/// Os dados extraídos são salvos no contexto e podem ser usados
/// em steps seguintes via interpolação.
///
/// ## Exemplo:
/// ```json
/// {
///   "source": "body",
///   "path": "data.access_token",
///   "target": "auth_token"
/// }
/// ```
///
/// Após a extração, `${auth_token}` fica disponível para uso.
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Extraction {
    /// Fonte dos dados: "body", "header", ou "status_code".
    pub source: String,

    /// Caminho para o dado.
    ///
    /// Para body: JSONPath (ex: "data.user.id", "/data/user/id")
    /// Para header: nome do header (ex: "X-Request-Id")
    /// Para status_code: não usado (pode ser vazio)
    pub path: String,

    /// Nome da variável onde salvar o valor extraído.
    ///
    /// Após a extração, use `${target}` para acessar o valor.
    pub target: String,

    /// Se true, retorna todos os matches como array.
    ///
    /// Útil para JSONPath com wildcard ou regex com múltiplos matches.
    /// Padrão: false (retorna apenas o primeiro).
    #[serde(default)]
    pub all_values: bool,

    /// Se true, a falha desta extração é crítica e deve abortar.
    ///
    /// Quando false, a falha é registrada mas a execução continua.
    /// Padrão: false (tolerante a falhas).
    #[serde(default)]
    pub critical: bool,
}

// ============================================================================
// POLÍTICA DE RECUPERAÇÃO: RECOVERY POLICY
// ============================================================================

/// Define o comportamento em caso de falha do step.
///
/// Permite configurar retry automático com backoff exponencial.
///
/// ## Estratégias:
/// - `retry`: Tenta novamente até max_attempts
/// - `fail_fast`: Falha imediatamente (padrão)
/// - `ignore`: Ignora a falha e marca como passed
///
/// ## Exemplo:
/// ```json
/// {
///   "strategy": "retry",
///   "max_attempts": 3,
///   "backoff_ms": 500,
///   "backoff_factor": 2.0
/// }
/// ```
///
/// Isso tenta 3 vezes com delays de 500ms, 1000ms, 2000ms.
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct RecoveryPolicy {
    /// Estratégia de recuperação: "retry", "fail_fast", "ignore".
    pub strategy: String,

    /// Número máximo de tentativas (incluindo a primeira).
    ///
    /// Ex: 3 significa tentar até 3 vezes.
    pub max_attempts: u32,

    /// Delay base em milissegundos entre tentativas.
    ///
    /// Este é o delay após a primeira falha.
    pub backoff_ms: u64,

    /// Fator multiplicador para backoff exponencial.
    ///
    /// O delay é multiplicado por este fator a cada tentativa.
    /// Exemplo: backoff_ms=500, factor=2.0 → 500ms, 1000ms, 2000ms
    #[serde(default = "default_backoff_factor")]
    pub backoff_factor: f64,
}

/// Valor padrão para o fator de backoff.
fn default_backoff_factor() -> f64 {
    2.0
}

// ============================================================================
// RESULTADO DE STEP: STEP RESULT
// ============================================================================

/// Resultado da execução de um step.
///
/// Gerado após cada step executar (ou falhar).
/// Usado para compor o relatório final.
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct StepResult {
    /// ID do step que foi executado.
    pub step_id: String,

    /// Status final: Passed, Failed, ou Skipped.
    pub status: StepStatus,

    /// Duração da execução em milissegundos.
    pub duration_ms: u64,

    /// Mensagem de erro (se status for Failed).
    ///
    /// `#[serde(skip_serializing_if)]` faz com que não apareça no JSON se for None.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,

    /// Snapshot do contexto ANTES da execução deste step.
    /// Útil para debug: ver quais variáveis estavam disponíveis.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context_before: Option<HashMap<String, Value>>,

    /// Snapshot do contexto APÓS a execução deste step.
    /// Mostra o estado atualizado, incluindo valores extraídos.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context_after: Option<HashMap<String, Value>>,

    /// Resultados das extrações realizadas neste step.
    /// Inclui sucesso/falha de cada regra de extração.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extractions: Option<Vec<ExtractionResult>>,
}

// ============================================================================
// STATUS DE STEP: STEP STATUS
// ============================================================================

/// Status possíveis de um step após execução.
#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
#[serde(rename_all = "lowercase")] // Serializa como "passed", "failed", "skipped"
pub enum StepStatus {
    /// Step executou com sucesso e todas as assertions passaram.
    Passed,

    /// Step falhou (erro de execução ou assertion falhou).
    Failed,

    /// Step foi pulado (dependência falhou).
    Skipped,
}

// ============================================================================
// RELATÓRIO DE EXECUÇÃO: EXECUTION REPORT
// ============================================================================

/// Relatório final de execução de um plano.
///
/// Gerado ao final da execução e salvo em arquivo ou impresso no console.
/// Este formato segue o schema definido em /schemas/runner_report.schema.json.
#[derive(Debug, Serialize)]
pub struct ExecutionReport {
    /// UUID único desta execução.
    /// Permite rastrear esta execução específica em logs/dashboards.
    pub execution_id: String,

    /// ID do plano executado.
    pub plan_id: String,

    /// Status geral: "passed" se todos passaram, "failed" se algum falhou.
    pub status: String,

    /// Data/hora de início em formato ISO8601.
    pub start_time: String,

    /// Data/hora de fim em formato ISO8601.
    pub end_time: String,

    /// Resumo estatístico da execução.
    pub summary: ExecutionSummary,

    /// Resultados de cada step.
    pub steps: Vec<StepResult>,
}

/// Resumo estatístico da execução.
///
/// Contém contagens e métricas úteis para dashboards e CI/CD.
#[derive(Debug, Serialize)]
pub struct ExecutionSummary {
    /// Total de steps no plano.
    pub total_steps: usize,

    /// Número de steps que passaram.
    pub passed: usize,

    /// Número de steps que falharam.
    pub failed: usize,

    /// Número de steps pulados (dependência falhou).
    pub skipped: usize,

    /// Número total de retries realizados.
    pub total_retries: u32,

    /// Duração total da execução em milissegundos.
    pub duration_ms: u64,
}

impl ExecutionSummary {
    /// Cria um summary a partir dos resultados dos steps.
    pub fn from_results(results: &[StepResult], duration_ms: u64) -> Self {
        let passed = results
            .iter()
            .filter(|r| r.status == StepStatus::Passed)
            .count();
        let failed = results
            .iter()
            .filter(|r| r.status == StepStatus::Failed)
            .count();
        let skipped = results
            .iter()
            .filter(|r| r.status == StepStatus::Skipped)
            .count();

        // TODO: Contar retries quando StepResult tiver esse campo
        let total_retries = 0;

        Self {
            total_steps: results.len(),
            passed,
            failed,
            skipped,
            total_retries,
            duration_ms,
        }
    }
}
