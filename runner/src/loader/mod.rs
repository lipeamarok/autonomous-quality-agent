//! # Módulo de Carregamento - Leitura de Arquivos UTDL
//!
//! Este módulo é responsável por **ler e parsear** arquivos UTDL do disco.
//!
//! ## O que este módulo faz?
//!
//! 1. Lê o conteúdo de um arquivo do sistema de arquivos
//! 2. Converte o JSON em estruturas Rust (deserialização)
//! 3. Retorna erros claros se algo der errado
//!
//! ## Exemplo de uso:
//!
//! ```rust
//! use loader::load_plan_from_file;
//!
//! let plan = load_plan_from_file("./plans/login_test.utdl.json")?;
//! println!("Plano carregado: {}", plan.meta.name);
//! ```
//!
//! ## Por que um módulo separado?
//!
//! Separar o carregamento permite:
//! - Testar a lógica de carregamento isoladamente
//! - Adicionar suporte a outros formatos (YAML, TOML) no futuro
//! - Implementar cache de planos se necessário

use crate::protocol::Plan;
use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

/// Carrega um plano UTDL de um arquivo JSON.
///
/// Esta função lê o arquivo do disco e converte o conteúdo JSON
/// em uma estrutura `Plan` que pode ser executada pelo Runner.
///
/// ## Parâmetros:
/// - `path`: Caminho para o arquivo UTDL (qualquer tipo que implemente `AsRef<Path>`)
///
/// ## Retorno:
/// - `Ok(Plan)`: Plano carregado e parseado com sucesso
/// - `Err`: Erro se o arquivo não existir ou o JSON for inválido
///
/// ## Exemplos de erro:
/// - "Failed to read plan file" → Arquivo não existe ou sem permissão
/// - "Failed to parse plan JSON" → JSON malformado ou estrutura inválida
///
/// ## Exemplo:
/// ```rust
/// let plan = load_plan_from_file("./test.utdl.json")?;
/// println!("Loaded plan: {}", plan.meta.name);
/// println!("Steps: {}", plan.steps.len());
/// ```
pub fn load_plan_from_file<P: AsRef<Path>>(path: P) -> Result<Plan> {
    // Converte o path para referência.
    // `AsRef<Path>` permite passar &str, String, PathBuf, etc.
    let path_ref = path.as_ref();

    // Lê todo o conteúdo do arquivo como string.
    // `with_context` adiciona informação extra ao erro se falhar.
    let content = fs::read_to_string(path_ref)
        .with_context(|| format!("Failed to read plan file {:?}", path_ref))?;

    // Parseia o JSON para a estrutura Plan.
    // `serde_json::from_str` usa as anotações #[derive(Deserialize)] do Plan.
    let plan = serde_json::from_str(&content)
        .with_context(|| format!("Failed to parse plan JSON {:?}", path_ref))?;

    Ok(plan)
}
