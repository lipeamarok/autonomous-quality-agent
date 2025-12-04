//! # Módulo de Contexto - Gerenciamento de Estado e Interpolação
//!
//! Este módulo é o **coração do sistema de variáveis** do Runner.
//! Ele gerencia todo o estado durante a execução dos testes.
//!
//! ## O que este módulo faz?
//!
//! 1. **Armazena variáveis** definidas no plano ou extraídas de respostas
//! 2. **Interpola placeholders** como `${token}` em strings
//! 3. **Gera valores dinâmicos** como UUIDs, timestamps, números aleatórios
//! 4. **Acessa variáveis de ambiente** de forma segura
//!
//! ## Exemplos de Interpolação:
//!
//! ```text
//! "Bearer ${auth_token}"     → "Bearer eyJhbGciOiJIUzI1..."
//! "user_${random_uuid}"      → "user_550e8400-e29b-41d4-a716-446655440000"
//! "created_at: ${timestamp}" → "created_at: 1701619200"
//! "key=${env:API_KEY}"       → "key=sk_live_abc123..."
//! ```
//!
//! ## Funções Dinâmicas Disponíveis:
//!
//! | Placeholder      | Descrição                          | Exemplo de Saída              |
//! |-----------------|------------------------------------|-----------------------------|
//! | `${random_uuid}` | UUID v4 aleatório                  | `550e8400-e29b-41d4-...`   |
//! | `${timestamp}`   | Unix timestamp (segundos)          | `1701619200`               |
//! | `${timestamp_ms}`| Unix timestamp (milissegundos)     | `1701619200000`            |
//! | `${now}`         | Data/hora ISO8601 UTC              | `2024-01-15T12:00:00+00:00`|
//! | `${now_local}`   | Data/hora ISO8601 local            | `2024-01-15T09:00:00-03:00`|
//! | `${random_int}`  | Inteiro aleatório 0-4294967295     | `2847593021`               |
//! | `${env:VAR}`     | Variável de ambiente               | (valor da variável)        |
//! | `${ENV_VAR}`     | Variável de ambiente (formato legado) | (valor da variável)     |
//! | `${base64:text}` | Codifica texto em Base64           | `dGV4dA==`                 |
//! | `${sha256:text}` | Hash SHA-256 do texto (hex)        | `9f86d081884c7d659a2f...`  |

use anyhow::{anyhow, Result};
use base64::{engine::general_purpose::STANDARD as BASE64_STANDARD, Engine as _};
use chrono::{Local, Utc};
use once_cell::sync::Lazy;
use regex::Regex;
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use uuid::Uuid;

// ============================================================================
// EXPRESSÃO REGULAR PARA INTERPOLAÇÃO
// ============================================================================

/// Regex compilada uma única vez (lazy) para encontrar placeholders `${...}`.
///
/// ## Por que usar `Lazy`?
///
/// Compilar uma regex é custoso. `Lazy` garante que a regex seja compilada
/// apenas uma vez, na primeira vez que for usada, e depois reutilizada.
///
/// ## O que a regex captura?
///
/// Padrão: `\$\{([A-Za-z0-9_.:-]+)\}`
///
/// - `\$\{` → Início literal `${`
/// - `([A-Za-z0-9_.:-]+)` → Captura o nome da variável (grupo 1)
/// - `\}` → Fim literal `}`
///
/// Exemplos de match:
/// - `${token}` → captura "token"
/// - `${env:API_KEY}` → captura "env:API_KEY"
/// - `${user.name}` → captura "user.name"
static INTERPOLATION_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"\$\{([A-Za-z0-9_.:-]+)\}").expect("valid interpolation regex"));

// ============================================================================
// ESTRUTURA CONTEXT
// ============================================================================

/// Armazena o estado de execução, incluindo variáveis e valores extraídos.
///
/// O `Context` é como um "dicionário global" que:
/// - Começa com variáveis definidas no `config.variables` do plano
/// - É enriquecido com valores extraídos das respostas HTTP (`extract`)
/// - Pode ser consultado para interpolação de strings
///
/// ## Exemplo de uso:
///
/// ```rust
/// let mut ctx = Context::new();
///
/// // Define variáveis
/// ctx.set("user_id", Value::String("123".to_string()));
/// ctx.set("count", Value::Number(42.into()));
///
/// // Interpola strings
/// let result = ctx.interpolate_str("User ${user_id} has ${count} items")?;
/// // → "User 123 has 42 items"
/// ```
#[derive(Debug, Default)]
pub struct Context {
    /// HashMap que armazena todas as variáveis.
    ///
    /// Chave: nome da variável (String)
    /// Valor: qualquer valor JSON (String, Number, Bool, Array, Object, Null)
    pub variables: HashMap<String, Value>,
}

impl Context {
    /// Cria um novo contexto vazio.
    ///
    /// ## Exemplo:
    /// ```rust
    /// let ctx = Context::new();
    /// assert!(ctx.variables.is_empty());
    /// ```
    pub fn new() -> Self {
        Self {
            variables: HashMap::new(),
        }
    }

    /// Define ou atualiza uma variável no contexto.
    ///
    /// ## Parâmetros:
    /// - `key`: Nome da variável (qualquer tipo que implemente `Into<String>`)
    /// - `value`: Valor JSON a armazenar
    ///
    /// ## Comportamento:
    /// - Se a chave já existir, o valor será sobrescrito e um warning será logado.
    /// - Isso ajuda a detectar extrações conflitantes entre steps.
    ///
    /// ## Exemplo:
    /// ```rust
    /// ctx.set("auth_token", Value::String("abc123".to_string()));
    /// ctx.set("retry_count", Value::Number(3.into()));
    /// ```
    pub fn set(&mut self, key: impl Into<String>, value: Value) {
        let key_str = key.into();

        // Proteção contra sobrescrita acidental de variáveis
        if let Some(old_value) = self.variables.get(&key_str) {
            // Só loga warning se o valor realmente mudou
            if old_value != &value {
                tracing::warn!(
                    key = %key_str,
                    old_value = %old_value,
                    new_value = %value,
                    "Variável sobrescrita no contexto. Verifique se dois steps extraem a mesma chave."
                );
            }
        }

        self.variables.insert(key_str, value);
    }

    /// Adiciona múltiplas variáveis de uma vez.
    ///
    /// Útil para carregar as variáveis do `config.variables` do plano.
    ///
    /// ## Parâmetros:
    /// - `entries`: HashMap com as variáveis a adicionar
    ///
    /// ## Exemplo:
    /// ```rust
    /// let mut vars = HashMap::new();
    /// vars.insert("env".to_string(), Value::String("staging".to_string()));
    /// vars.insert("timeout".to_string(), Value::Number(5000.into()));
    ///
    /// ctx.extend(&vars);
    /// ```
    pub fn extend(&mut self, entries: &HashMap<String, Value>) {
        for (k, v) in entries {
            self.variables.insert(k.clone(), v.clone());
        }
    }

    /// Recupera uma variável do contexto.
    ///
    /// ## Parâmetros:
    /// - `key`: Nome da variável a buscar
    ///
    /// ## Retorno:
    /// - `Some(&Value)` se a variável existir
    /// - `None` se não existir
    ///
    /// ## Exemplo:
    /// ```rust
    /// if let Some(token) = ctx.get("auth_token") {
    ///     println!("Token: {}", token);
    /// }
    /// ```
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.variables.get(key)
    }

    /// Interpola placeholders `${...}` em uma string.
    ///
    /// Esta é a função principal de interpolação. Ela:
    /// 1. Encontra todos os placeholders na string
    /// 2. Resolve cada um (variável, função dinâmica, ou env var)
    /// 3. Substitui pelo valor resolvido
    ///
    /// ## Parâmetros:
    /// - `input`: String contendo placeholders
    ///
    /// ## Retorno:
    /// - `Ok(String)` com todos os placeholders substituídos
    /// - `Err` se algum placeholder não puder ser resolvido
    ///
    /// ## Exemplo:
    /// ```rust
    /// ctx.set("name", Value::String("João".to_string()));
    ///
    /// let result = ctx.interpolate_str("Olá, ${name}!")?;
    /// assert_eq!(result, "Olá, João!");
    /// ```
    pub fn interpolate_str(&self, input: &str) -> Result<String> {
        let mut result = String::new();
        let mut last_index = 0;

        // Itera sobre todos os matches da regex.
        for capture in INTERPOLATION_RE.captures_iter(input) {
            let matched = capture.get(0).unwrap(); // O match completo (ex: "${token}")

            // Adiciona o texto antes do match.
            result.push_str(&input[last_index..matched.start()]);

            // Extrai o nome do token (grupo 1 da regex).
            let token = capture.get(1).unwrap().as_str(); // Ex: "token"

            // Resolve o token para seu valor.
            let resolved = self.resolve_token(token)?;

            // Adiciona o valor resolvido.
            result.push_str(&resolved);

            // Atualiza o índice para continuar após o match.
            last_index = matched.end();
        }

        // Adiciona o texto restante após o último match.
        result.push_str(&input[last_index..]);

        Ok(result)
    }

    /// Interpola placeholders recursivamente em valores JSON.
    ///
    /// Esta função é usada para interpolar bodies de requisição,
    /// que podem ser objetos JSON complexos.
    ///
    /// ## Comportamento por tipo:
    /// - **String**: Interpola placeholders
    /// - **Array**: Interpola cada elemento
    /// - **Object**: Interpola cada valor (chaves não são interpoladas)
    /// - **Outros**: Retorna sem alteração
    ///
    /// ## Exemplo:
    /// ```rust
    /// let body = json!({
    ///     "user": "${user_id}",
    ///     "items": ["${item1}", "${item2}"]
    /// });
    ///
    /// let interpolated = ctx.interpolate_value(&body)?;
    /// ```
    pub fn interpolate_value(&self, value: &Value) -> Result<Value> {
        match value {
            // Strings: interpola placeholders.
            Value::String(s) => Ok(Value::String(self.interpolate_str(s)?)),

            // Arrays: interpola cada elemento.
            Value::Array(items) => {
                let mut result = Vec::with_capacity(items.len());
                for item in items {
                    result.push(self.interpolate_value(item)?);
                }
                Ok(Value::Array(result))
            }

            // Objetos: interpola cada valor.
            Value::Object(map) => {
                let mut new_map = Map::with_capacity(map.len());
                for (k, v) in map {
                    new_map.insert(k.clone(), self.interpolate_value(v)?);
                }
                Ok(Value::Object(new_map))
            }

            // Outros tipos (Number, Bool, Null): retorna como está.
            _ => Ok(value.clone()),
        }
    }

    /// Resolve um token para seu valor como string.
    ///
    /// Esta função é chamada internamente por `interpolate_str` para
    /// cada placeholder encontrado.
    ///
    /// ## Ordem de resolução:
    /// 1. Funções dinâmicas (`random_uuid`, `timestamp`, etc.)
    /// 2. Variáveis de ambiente com prefixo `env:` (`${env:API_KEY}`)
    /// 3. Variáveis de ambiente com prefixo `ENV_` (`${ENV_API_KEY}`)
    /// 4. Variáveis do contexto
    ///
    /// ## Parâmetros:
    /// - `token`: Nome do token a resolver (sem `${}`)
    ///
    /// ## Retorno:
    /// - `Ok(String)` com o valor resolvido
    /// - `Err` se o token não puder ser resolvido
    fn resolve_token(&self, token: &str) -> Result<String> {
        // ====================================================================
        // FUNÇÕES DINÂMICAS (Magic Variables)
        // ====================================================================

        match token {
            // Gera um UUID v4 aleatório.
            // Útil para criar IDs únicos em testes.
            "random_uuid" => return Ok(Uuid::new_v4().to_string()),

            // Retorna o timestamp Unix em segundos.
            // Útil para campos de data/hora.
            "timestamp" => return Ok(Utc::now().timestamp().to_string()),

            // Retorna o timestamp Unix em milissegundos.
            // Útil para maior precisão.
            "timestamp_ms" => return Ok(Utc::now().timestamp_millis().to_string()),

            // Retorna a data/hora atual em formato ISO8601 UTC.
            "now" => return Ok(Utc::now().to_rfc3339()),

            // Retorna a data/hora atual em formato ISO8601 com timezone local.
            "now_local" => return Ok(Local::now().to_rfc3339()),

            // Gera um inteiro aleatório de 32 bits (0 a 4.294.967.295).
            "random_int" => return Ok(rand::random::<u32>().to_string()),

            // Não é uma função dinâmica conhecida, continua para próximas opções.
            _ => {}
        }

        // ====================================================================
        // VARIÁVEIS DE AMBIENTE - Formato ${env:VAR_NAME}
        // ====================================================================

        // Este é o formato preferido, pois é mais explícito.
        if let Some(var_name) = token.strip_prefix("env:") {
            return std::env::var(var_name)
                .map_err(|_| anyhow!("Variável de ambiente '{}' não definida.", var_name));
        }

        // ====================================================================
        // FUNÇÃO BASE64 - Formato ${base64:texto}
        // ====================================================================

        // Codifica o texto em Base64 (RFC 4648 standard).
        // Útil para headers de autenticação Basic, payloads binários, etc.
        if let Some(text) = token.strip_prefix("base64:") {
            // Primeiro interpola o texto interno caso contenha variáveis
            let interpolated = self
                .interpolate_str(text)
                .unwrap_or_else(|_| text.to_string());
            return Ok(BASE64_STANDARD.encode(interpolated.as_bytes()));
        }

        // ====================================================================
        // FUNÇÃO SHA256 - Formato ${sha256:texto}
        // ====================================================================

        // Calcula o hash SHA-256 do texto (retorna hex lowercase).
        // Útil para checksums, validação de integridade, tokens de cache.
        if let Some(text) = token.strip_prefix("sha256:") {
            // Primeiro interpola o texto interno caso contenha variáveis
            let interpolated = self
                .interpolate_str(text)
                .unwrap_or_else(|_| text.to_string());
            let mut hasher = Sha256::new();
            hasher.update(interpolated.as_bytes());
            let result = hasher.finalize();
            return Ok(format!("{:x}", result));
        }

        // ====================================================================
        // VARIÁVEIS DE AMBIENTE - Formato legado ${ENV_VAR_NAME}
        // ====================================================================

        // Mantido para compatibilidade com versões anteriores.
        if let Some(rest) = token.strip_prefix("ENV_") {
            return std::env::var(rest)
                .map_err(|_| anyhow!("Variável de ambiente '{}' não definida.", rest));
        }

        // ====================================================================
        // VARIÁVEIS DO CONTEXTO
        // ====================================================================

        // Tenta encontrar no HashMap de variáveis.
        if let Some(value) = self.variables.get(token) {
            return match value {
                // Strings são retornadas diretamente.
                Value::String(s) => Ok(s.clone()),
                // Outros tipos são convertidos para string JSON.
                primitive => Ok(primitive.to_string()),
            };
        }

        // ====================================================================
        // ERRO: VARIÁVEL NÃO ENCONTRADA
        // ====================================================================

        // Se chegou aqui, o token não foi resolvido.
        // Retorna erro com lista de variáveis disponíveis para ajudar no debug.
        Err(anyhow!(
            "Variável '{}' não encontrada. Disponíveis: {:?}",
            token,
            self.variables.keys().collect::<Vec<_>>()
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_random_uuid_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("id: ${random_uuid}").unwrap();

        // UUID v4 tem formato xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        assert!(result.starts_with("id: "));
        let uuid_part = &result[4..];
        assert_eq!(uuid_part.len(), 36);
        assert!(uuid_part.contains('-'));
    }

    #[test]
    fn test_timestamp_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("ts: ${timestamp}").unwrap();

        let ts_part = &result[4..];
        let ts: i64 = ts_part.parse().expect("deve ser número");
        assert!(ts > 1700000000); // Após 2023
    }

    #[test]
    fn test_timestamp_ms_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("ts: ${timestamp_ms}").unwrap();

        let ts_part = &result[4..];
        let ts: i64 = ts_part.parse().expect("deve ser número");
        assert!(ts > 1700000000000); // Após 2023 em ms
    }

    #[test]
    fn test_now_interpolation() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("${now}").unwrap();

        // Formato RFC3339: 2024-01-15T12:34:56+00:00
        assert!(result.contains("T"));
        assert!(result.len() > 20);
    }

    #[test]
    fn test_random_int_interpolation() {
        let ctx = Context::new();
        let result1 = ctx.interpolate_str("${random_int}").unwrap();
        let result2 = ctx.interpolate_str("${random_int}").unwrap();

        // Ambos devem ser números
        let _: u32 = result1.parse().expect("deve ser número");
        let _: u32 = result2.parse().expect("deve ser número");

        // Alta probabilidade de serem diferentes
        // (não garantido, mas extremamente improvável serem iguais)
    }

    #[test]
    fn test_multiple_dynamic_vars() {
        let ctx = Context::new();
        let result = ctx
            .interpolate_str("uuid=${random_uuid}&ts=${timestamp}")
            .unwrap();

        assert!(result.contains("uuid="));
        assert!(result.contains("&ts="));
        assert!(!result.contains("${"));
    }

    #[test]
    fn test_mixed_static_and_dynamic() {
        let mut ctx = Context::new();
        ctx.set("user", Value::String("john".to_string()));

        let result = ctx
            .interpolate_str("user=${user}&session=${random_uuid}")
            .unwrap();

        assert!(result.starts_with("user=john&session="));
        assert!(!result.contains("${"));
    }

    #[test]
    fn test_env_colon_syntax() {
        // Seta uma variável de ambiente para o teste
        std::env::set_var("TEST_API_KEY", "secret123");

        let ctx = Context::new();
        let result = ctx.interpolate_str("key=${env:TEST_API_KEY}").unwrap();

        assert_eq!(result, "key=secret123");

        // Limpa a variável
        std::env::remove_var("TEST_API_KEY");
    }

    #[test]
    fn test_env_legacy_syntax() {
        // Seta uma variável de ambiente para o teste
        std::env::set_var("MY_TOKEN", "token456");

        let ctx = Context::new();
        let result = ctx.interpolate_str("auth=${ENV_MY_TOKEN}").unwrap();

        assert_eq!(result, "auth=token456");

        // Limpa a variável
        std::env::remove_var("MY_TOKEN");
    }

    #[test]
    fn test_env_missing_variable() {
        let ctx = Context::new();
        let result = ctx.interpolate_str("key=${env:NONEXISTENT_VAR_12345}");

        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("não definida"));
    }

    #[test]
    fn test_base64_encoding() {
        let ctx = Context::new();

        // Testa codificação base64 básica
        let result = ctx.interpolate_str("${base64:hello}").unwrap();
        assert_eq!(result, "aGVsbG8=");

        // Testa com texto mais longo
        let result = ctx.interpolate_str("${base64:user:password}").unwrap();
        assert_eq!(result, "dXNlcjpwYXNzd29yZA==");
    }

    #[test]
    fn test_sha256_hashing() {
        let ctx = Context::new();

        // Testa hash SHA-256 (verificado com ferramentas externas)
        let result = ctx.interpolate_str("${sha256:hello}").unwrap();
        assert_eq!(
            result,
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        );

        // Testa hash vazio
        let result = ctx.interpolate_str("${sha256:}").unwrap();
        assert_eq!(
            result,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn test_base64_in_header() {
        let ctx = Context::new();

        // Simula header de autenticação Basic
        let result = ctx
            .interpolate_str("Basic ${base64:admin:secret123}")
            .unwrap();
        assert_eq!(result, "Basic YWRtaW46c2VjcmV0MTIz");
    }

    #[test]
    fn test_sha256_for_cache_key() {
        let ctx = Context::new();

        // Simula geração de cache key
        let result = ctx.interpolate_str("cache:${sha256:mykey}").unwrap();
        assert!(result.starts_with("cache:"));
        assert_eq!(result.len(), 6 + 64); // "cache:" + 64 hex chars
    }
}
