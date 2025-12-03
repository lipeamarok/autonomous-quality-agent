//! # Módulo de Códigos de Erro Estruturados
//!
//! Define códigos de erro padronizados para melhor UX e integração
//! com sistemas externos (CI/CD, dashboards, alertas).
//!
//! ## Para todos entenderem:
//!
//! Quando algo dá errado, este módulo fornece códigos únicos
//! que identificam exatamente o que aconteceu.
//!
//! É como ter um "número do erro" que você pode pesquisar
//! na documentação ou passar para o suporte.
//!
//! ## Categorias de Erro
//!
//! Os códigos são organizados por categoria:
//!
//! | Faixa  | Categoria       | Descrição                     |
//! |--------|-----------------|-------------------------------|
//! | E1xxx  | Validação       | Erro no arquivo de teste      |
//! | E2xxx  | HTTP            | Erro na requisição HTTP       |
//! | E3xxx  | Assertion       | Teste não passou              |
//! | E4xxx  | Configuração    | Problema de setup/ambiente    |
//! | E5xxx  | Interno         | Bug no próprio Runner         |
//!
//! ## Por que usar códigos numéricos?
//!
//! 1. **Automação**: CI/CD pode agir baseado no código
//! 2. **Pesquisa**: Fácil buscar na documentação
//! 3. **Logs**: Mais compacto que mensagens longas
//! 4. **Internacionalização**: Código funciona em qualquer idioma
//!
//! ## Exemplo:
//!
//! ```text
//! Error E3001: Assertion status_code falhou
//!   Esperado: 200
//!   Recebido: 404
//!   Step: get_user
//! ```
//!
//! Com o código E3001, você sabe que:
//! - É um erro de assertion (3xxx)
//! - Especificamente status_code (001)

use std::fmt;

// ============================================================================
// CÓDIGO DE ERRO
// ============================================================================

/// Código de erro estruturado com categoria e número.
///
/// O código é um número de 4 dígitos onde:
/// - Primeiro dígito: categoria (1-5)
/// - Últimos 3 dígitos: erro específico (001-999)
///
/// ## Para todos entenderem:
///
/// É como um CEP: a primeira parte diz a região,
/// o resto é o endereço específico.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ErrorCode(u16);

impl ErrorCode {
    // ========================================================================
    // E1xxx: Validação/Parsing
    // ========================================================================
    // Erros que acontecem antes de executar qualquer coisa.
    // Problema está no arquivo de teste.

    /// Plano UTDL vazio (sem steps).
    /// Causa: Arquivo de teste não tem nenhum step definido.
    pub const EMPTY_PLAN: Self = Self(1001);

    /// Versão de spec não suportada.
    /// Causa: spec_version no arquivo não é "0.1".
    pub const UNSUPPORTED_SPEC_VERSION: Self = Self(1002);

    /// Action desconhecida no step.
    /// Causa: action não é "http_request", "wait", ou "sleep".
    pub const UNKNOWN_ACTION: Self = Self(1003);

    /// Parâmetro obrigatório ausente.
    /// Causa: Falta method, path, duration_ms, etc.
    pub const MISSING_PARAM: Self = Self(1004);

    /// Dependência de step não encontrada.
    /// Causa: depends_on referencia step que não existe.
    pub const UNKNOWN_DEPENDENCY: Self = Self(1005);

    /// Dependência circular detectada.
    /// Causa: A depende de B que depende de A.
    pub const CIRCULAR_DEPENDENCY: Self = Self(1006);

    /// Método HTTP inválido.
    /// Causa: method não é GET, POST, PUT, DELETE, etc.
    pub const INVALID_HTTP_METHOD: Self = Self(1007);

    /// ID de step vazio.
    /// Causa: step.id está em branco ou só espaços.
    pub const EMPTY_STEP_ID: Self = Self(1008);

    /// JSON/YAML inválido no plano.
    /// Causa: Arquivo de teste com sintaxe inválida.
    pub const INVALID_PLAN_FORMAT: Self = Self(1009);

    // ========================================================================
    // E2xxx: Execução HTTP
    // ========================================================================
    // Erros que acontecem ao fazer requisições HTTP.
    // Problema pode ser na rede, servidor, ou configuração.

    /// Timeout na requisição HTTP.
    /// Causa: Servidor não respondeu no tempo configurado.
    pub const HTTP_TIMEOUT: Self = Self(2001);

    /// Erro de conexão (DNS, rede).
    /// Causa: Não conseguiu conectar no servidor.
    pub const HTTP_CONNECTION_ERROR: Self = Self(2002);

    /// Resposta HTTP com status de erro (4xx/5xx).
    /// Causa: Servidor retornou erro.
    pub const HTTP_ERROR_STATUS: Self = Self(2003);

    /// Erro ao parsear resposta JSON.
    /// Causa: Resposta não é JSON válido.
    pub const HTTP_INVALID_JSON: Self = Self(2004);

    /// SSL/TLS error.
    /// Causa: Problema com certificado ou protocolo HTTPS.
    pub const HTTP_TLS_ERROR: Self = Self(2005);

    // ========================================================================
    // E3xxx: Assertions
    // ========================================================================
    // Erros quando a resposta não é o esperado.
    // O teste "passou tecnicamente" mas a validação falhou.

    /// Assertion de status_code falhou.
    /// Causa: Status HTTP diferente do esperado.
    pub const ASSERTION_STATUS_CODE: Self = Self(3001);

    /// Assertion de json_body falhou.
    /// Causa: Valor no JSON diferente do esperado.
    pub const ASSERTION_JSON_BODY: Self = Self(3002);

    /// Assertion de header falhou.
    /// Causa: Header HTTP diferente do esperado.
    pub const ASSERTION_HEADER: Self = Self(3003);

    /// Assertion de latency falhou.
    /// Causa: Requisição demorou mais que o limite.
    pub const ASSERTION_LATENCY: Self = Self(3004);

    /// Path JSON não encontrado na resposta.
    /// Causa: O caminho especificado não existe no JSON.
    pub const ASSERTION_PATH_NOT_FOUND: Self = Self(3005);

    // ========================================================================
    // E4xxx: Configuração/Ambiente
    // ========================================================================
    // Erros de setup, variáveis de ambiente, arquivos.

    /// Variável de ambiente não definida.
    /// Causa: {{env:VAR}} usada mas VAR não existe.
    pub const ENV_VAR_NOT_FOUND: Self = Self(4001);

    /// Variável de contexto não encontrada.
    /// Causa: {{var_name}} usada mas nunca foi extraída.
    pub const CONTEXT_VAR_NOT_FOUND: Self = Self(4002);

    /// Arquivo de plano não encontrado.
    /// Causa: Caminho passado para --plan-file não existe.
    pub const PLAN_FILE_NOT_FOUND: Self = Self(4003);

    /// Erro de permissão ao acessar arquivo.
    /// Causa: Runner não tem permissão para ler arquivo.
    pub const FILE_PERMISSION_ERROR: Self = Self(4004);

    // ========================================================================
    // E5xxx: Erros Internos
    // ========================================================================
    // Bugs no próprio Runner. Se você ver esses, reporte!

    /// Erro interno inesperado.
    /// Causa: Bug no Runner, por favor reporte.
    pub const INTERNAL_ERROR: Self = Self(5001);

    /// Executor não encontrado para action.
    /// Causa: Bug interno, action válida sem executor.
    pub const NO_EXECUTOR_FOR_ACTION: Self = Self(5002);

    /// Erro de serialização.
    /// Causa: Problema ao converter dados internamente.
    pub const SERIALIZATION_ERROR: Self = Self(5003);

    // ========================================================================
    // MÉTODOS
    // ========================================================================

    /// Retorna o código numérico.
    ///
    /// Exemplo: ErrorCode::EMPTY_PLAN.code() == 1001
    pub fn code(&self) -> u16 {
        self.0
    }

    /// Retorna o código formatado com prefixo "E".
    ///
    /// Exemplo: ErrorCode::EMPTY_PLAN.formatted() == "E1001"
    pub fn formatted(&self) -> String {
        format!("E{:04}", self.0)
    }

    /// Retorna a categoria do erro baseado no primeiro dígito.
    ///
    /// Exemplo: E1001 → Validation, E3001 → Assertion
    pub fn category(&self) -> ErrorCategory {
        match self.0 / 1000 {
            1 => ErrorCategory::Validation,
            2 => ErrorCategory::HttpExecution,
            3 => ErrorCategory::Assertion,
            4 => ErrorCategory::Configuration,
            5 => ErrorCategory::Internal,
            _ => ErrorCategory::Unknown,
        }
    }

    /// Retorna uma descrição curta do erro.
    ///
    /// Útil para exibir em logs ou mensagens de erro.
    pub fn description(&self) -> &'static str {
        match self.0 {
            1001 => "Plano vazio",
            1002 => "Versão de spec não suportada",
            1003 => "Action desconhecida",
            1004 => "Parâmetro obrigatório ausente",
            1005 => "Dependência não encontrada",
            1006 => "Dependência circular",
            1007 => "Método HTTP inválido",
            1008 => "ID de step vazio",
            1009 => "Formato de plano inválido",
            2001 => "Timeout HTTP",
            2002 => "Erro de conexão",
            2003 => "Status HTTP de erro",
            2004 => "JSON de resposta inválido",
            2005 => "Erro TLS/SSL",
            3001 => "Assertion status_code falhou",
            3002 => "Assertion json_body falhou",
            3003 => "Assertion header falhou",
            3004 => "Assertion latency falhou",
            3005 => "Path JSON não encontrado",
            4001 => "Variável de ambiente não definida",
            4002 => "Variável de contexto não encontrada",
            4003 => "Arquivo de plano não encontrado",
            4004 => "Erro de permissão",
            5001 => "Erro interno",
            5002 => "Executor não encontrado",
            5003 => "Erro de serialização",
            _ => "Erro desconhecido",
        }
    }
}

/// Implementação de Display para ErrorCode.
///
/// Permite usar ErrorCode em format!() e println!().
impl fmt::Display for ErrorCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.formatted())
    }
}

// ============================================================================
// CATEGORIA DE ERRO
// ============================================================================

/// Categoria de erro baseada no primeiro dígito do código.
///
/// Útil para agrupar erros em relatórios ou dashboards.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCategory {
    /// Erros de validação/parsing (E1xxx).
    /// Problema está no arquivo de teste.
    Validation,

    /// Erros de execução HTTP (E2xxx).
    /// Problema na rede ou servidor.
    HttpExecution,

    /// Erros de assertion (E3xxx).
    /// Teste falhou na validação.
    Assertion,

    /// Erros de configuração/ambiente (E4xxx).
    /// Problema de setup.
    Configuration,

    /// Erros internos (E5xxx).
    /// Bug no Runner.
    Internal,

    /// Categoria desconhecida.
    /// Código fora das faixas conhecidas.
    Unknown,
}

/// Implementação de Display para ErrorCategory.
impl fmt::Display for ErrorCategory {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Validation => write!(f, "Validação"),
            Self::HttpExecution => write!(f, "Execução HTTP"),
            Self::Assertion => write!(f, "Assertion"),
            Self::Configuration => write!(f, "Configuração"),
            Self::Internal => write!(f, "Interno"),
            Self::Unknown => write!(f, "Desconhecido"),
        }
    }
}

/// Erro estruturado com código, mensagem e contexto.
#[derive(Debug)]
pub struct StructuredError {
    /// Código do erro.
    pub code: ErrorCode,
    /// Mensagem detalhada.
    pub message: String,
    /// Contexto adicional (step_id, path, etc.).
    pub context: Option<ErrorContext>,
}

/// Contexto adicional do erro.
#[derive(Debug, Clone)]
pub struct ErrorContext {
    /// ID do step onde ocorreu o erro.
    pub step_id: Option<String>,
    /// Path ou campo relacionado.
    pub path: Option<String>,
    /// Valor esperado.
    pub expected: Option<String>,
    /// Valor obtido.
    pub actual: Option<String>,
}

impl StructuredError {
    /// Cria um novo erro estruturado.
    pub fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            context: None,
        }
    }

    /// Adiciona contexto ao erro.
    pub fn with_context(mut self, context: ErrorContext) -> Self {
        self.context = Some(context);
        self
    }

    /// Adiciona step_id ao contexto.
    pub fn with_step_id(mut self, step_id: impl Into<String>) -> Self {
        let ctx = self.context.get_or_insert(ErrorContext {
            step_id: None,
            path: None,
            expected: None,
            actual: None,
        });
        ctx.step_id = Some(step_id.into());
        self
    }

    /// Formata o erro para exibição ao usuário.
    pub fn user_message(&self) -> String {
        let mut msg = format!("[{}] {}", self.code, self.message);

        if let Some(ctx) = &self.context {
            if let Some(step_id) = &ctx.step_id {
                msg.push_str(&format!(" (step: {})", step_id));
            }
            if let Some(expected) = &ctx.expected {
                if let Some(actual) = &ctx.actual {
                    msg.push_str(&format!(" [esperado: {}, obtido: {}]", expected, actual));
                }
            }
        }

        msg
    }
}

impl fmt::Display for StructuredError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.user_message())
    }
}

impl std::error::Error for StructuredError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_code_formatting() {
        assert_eq!(ErrorCode::EMPTY_PLAN.formatted(), "E1001");
        assert_eq!(ErrorCode::HTTP_TIMEOUT.formatted(), "E2001");
        assert_eq!(ErrorCode::ASSERTION_STATUS_CODE.formatted(), "E3001");
    }

    #[test]
    fn test_error_code_category() {
        assert_eq!(ErrorCode::EMPTY_PLAN.category(), ErrorCategory::Validation);
        assert_eq!(ErrorCode::HTTP_TIMEOUT.category(), ErrorCategory::HttpExecution);
        assert_eq!(ErrorCode::ASSERTION_LATENCY.category(), ErrorCategory::Assertion);
        assert_eq!(ErrorCode::ENV_VAR_NOT_FOUND.category(), ErrorCategory::Configuration);
        assert_eq!(ErrorCode::INTERNAL_ERROR.category(), ErrorCategory::Internal);
    }

    #[test]
    fn test_structured_error_display() {
        let err = StructuredError::new(
            ErrorCode::ASSERTION_STATUS_CODE,
            "Status code não corresponde",
        )
        .with_step_id("step1");

        let msg = err.user_message();
        assert!(msg.contains("E3001"));
        assert!(msg.contains("step1"));
        assert!(msg.contains("Status code"));
    }

    #[test]
    fn test_structured_error_with_context() {
        let err = StructuredError::new(
            ErrorCode::ASSERTION_JSON_BODY,
            "Valor do campo não corresponde",
        )
        .with_context(ErrorContext {
            step_id: Some("create_user".to_string()),
            path: Some("/data/id".to_string()),
            expected: Some("123".to_string()),
            actual: Some("456".to_string()),
        });

        let msg = err.user_message();
        assert!(msg.contains("esperado: 123"));
        assert!(msg.contains("obtido: 456"));
    }
}
