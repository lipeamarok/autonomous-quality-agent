//! Módulo de Códigos de Erro Estruturados.
//!
//! Define códigos de erro padronizados para melhor UX e integração
//! com sistemas externos (CI/CD, dashboards, alertas).
//!
//! ## Categorias de Erro
//!
//! - E1xxx: Erros de validação/parsing
//! - E2xxx: Erros de execução HTTP
//! - E3xxx: Erros de assertion
//! - E4xxx: Erros de configuração/ambiente
//! - E5xxx: Erros internos do runner

use std::fmt;

/// Código de erro estruturado com categoria e número.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ErrorCode(u16);

impl ErrorCode {
    // === E1xxx: Validação/Parsing ===
    
    /// Plano UTDL vazio (sem steps).
    pub const EMPTY_PLAN: Self = Self(1001);
    /// Versão de spec não suportada.
    pub const UNSUPPORTED_SPEC_VERSION: Self = Self(1002);
    /// Action desconhecida no step.
    pub const UNKNOWN_ACTION: Self = Self(1003);
    /// Parâmetro obrigatório ausente.
    pub const MISSING_PARAM: Self = Self(1004);
    /// Dependência de step não encontrada.
    pub const UNKNOWN_DEPENDENCY: Self = Self(1005);
    /// Dependência circular detectada.
    pub const CIRCULAR_DEPENDENCY: Self = Self(1006);
    /// Método HTTP inválido.
    pub const INVALID_HTTP_METHOD: Self = Self(1007);
    /// ID de step vazio.
    pub const EMPTY_STEP_ID: Self = Self(1008);
    /// JSON/YAML inválido no plano.
    pub const INVALID_PLAN_FORMAT: Self = Self(1009);

    // === E2xxx: Execução HTTP ===
    
    /// Timeout na requisição HTTP.
    pub const HTTP_TIMEOUT: Self = Self(2001);
    /// Erro de conexão (DNS, rede).
    pub const HTTP_CONNECTION_ERROR: Self = Self(2002);
    /// Resposta HTTP com status de erro (4xx/5xx).
    pub const HTTP_ERROR_STATUS: Self = Self(2003);
    /// Erro ao parsear resposta JSON.
    pub const HTTP_INVALID_JSON: Self = Self(2004);
    /// SSL/TLS error.
    pub const HTTP_TLS_ERROR: Self = Self(2005);

    // === E3xxx: Assertions ===
    
    /// Assertion de status_code falhou.
    pub const ASSERTION_STATUS_CODE: Self = Self(3001);
    /// Assertion de json_body falhou.
    pub const ASSERTION_JSON_BODY: Self = Self(3002);
    /// Assertion de header falhou.
    pub const ASSERTION_HEADER: Self = Self(3003);
    /// Assertion de latency falhou.
    pub const ASSERTION_LATENCY: Self = Self(3004);
    /// Path JSON não encontrado na resposta.
    pub const ASSERTION_PATH_NOT_FOUND: Self = Self(3005);

    // === E4xxx: Configuração/Ambiente ===
    
    /// Variável de ambiente não definida.
    pub const ENV_VAR_NOT_FOUND: Self = Self(4001);
    /// Variável de contexto não encontrada.
    pub const CONTEXT_VAR_NOT_FOUND: Self = Self(4002);
    /// Arquivo de plano não encontrado.
    pub const PLAN_FILE_NOT_FOUND: Self = Self(4003);
    /// Erro de permissão ao acessar arquivo.
    pub const FILE_PERMISSION_ERROR: Self = Self(4004);

    // === E5xxx: Erros Internos ===
    
    /// Erro interno inesperado.
    pub const INTERNAL_ERROR: Self = Self(5001);
    /// Executor não encontrado para action.
    pub const NO_EXECUTOR_FOR_ACTION: Self = Self(5002);
    /// Erro de serialização.
    pub const SERIALIZATION_ERROR: Self = Self(5003);

    /// Retorna o código numérico.
    pub fn code(&self) -> u16 {
        self.0
    }

    /// Retorna o código formatado (ex: "E1001").
    pub fn formatted(&self) -> String {
        format!("E{:04}", self.0)
    }

    /// Retorna a categoria do erro.
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

impl fmt::Display for ErrorCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.formatted())
    }
}

/// Categoria de erro.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCategory {
    /// Erros de validação/parsing (E1xxx).
    Validation,
    /// Erros de execução HTTP (E2xxx).
    HttpExecution,
    /// Erros de assertion (E3xxx).
    Assertion,
    /// Erros de configuração/ambiente (E4xxx).
    Configuration,
    /// Erros internos (E5xxx).
    Internal,
    /// Categoria desconhecida.
    Unknown,
}

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
