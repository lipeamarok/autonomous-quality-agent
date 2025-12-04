//! # Módulo de Telemetria OpenTelemetry
//!
//! Fornece integração completa com OpenTelemetry para observabilidade distribuída.
//! Exporta traces/spans com atributos detalhados de cada requisição HTTP.
//!
//! ## Para todos entenderem:
//!
//! Telemetria é como ter uma câmera gravando tudo que seu programa faz.
//! Você pode depois assistir a gravação para entender:
//! - Por que algo demorou?
//! - Onde aconteceu um erro?
//! - Qual foi o caminho de uma requisição?
//!
//! OpenTelemetry é um padrão da indústria para isso.
//! Os dados podem ser visualizados em ferramentas como:
//! - Jaeger
//! - Zipkin
//! - Grafana Tempo
//! - AWS X-Ray
//!
//! ## Conceitos:
//!
//! ### Trace (rastreamento)
//!
//! Um trace é como uma "história" de uma operação.
//! Por exemplo: "Usuário fez login" pode envolver:
//! - Receber a requisição
//! - Validar credenciais
//! - Buscar no banco
//! - Retornar resposta
//!
//! ### Span (intervalo)
//!
//! Cada pedaço do trace é um span.
//! Spans podem ter filhos (hierarquia).
//!
//! ```text
//! [Login Request] ─────────────────────────────────>
//!   [Validate] ───>
//!              [DB Query] ────────>
//!                               [Response] ─>
//! ```
//!
//! ### Atributos
//!
//! Metadados sobre cada span:
//! - http.method: "GET"
//! - http.status_code: 200
//! - http.url: "/api/users"
//!
//! ## Configuração via variáveis de ambiente:
//!
//! - `OTEL_SERVICE_NAME`: Nome do serviço
//! - `OTEL_EXPORTER_OTLP_ENDPOINT`: URL do coletor OTLP
//! - `OTEL_TRACES_SAMPLER_ARG`: Taxa de sampling (0.0-1.0)
//!
//! ## Exemplo de uso:
//!
//! ```ignore
//! let config = TelemetryConfig {
//!     service_name: "my-tests".to_string(),
//!     otlp_endpoint: Some("http://localhost:4317".to_string()),
//!     sampling_ratio: 1.0, // 100% dos traces
//!     ..Default::default()
//! };
//!
//! init_telemetry(config)?;
//!
//! // ... executar testes ...
//!
//! shutdown_telemetry(); // Flush dos dados
//! ```

use opentelemetry::trace::TracerProvider as _;
use opentelemetry::{global, KeyValue};
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::runtime::Tokio;
use opentelemetry_sdk::trace::{RandomIdGenerator, Sampler, Tracer, TracerProvider};
use opentelemetry_sdk::{trace as sdktrace, Resource};
use tracing::Level;
use tracing_opentelemetry::OpenTelemetryLayer;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;

// ============================================================================
// CONFIGURAÇÃO
// ============================================================================

/// Configuração do sistema de telemetria.
///
/// Esta struct contém todas as opções para configurar o rastreamento.
/// Pode ser criada manualmente ou via `from_env()`.
#[derive(Debug, Clone)]
pub struct TelemetryConfig {
    /// Nome do serviço para identificação nos traces.
    /// Aparece em dashboards e ajuda a filtrar dados.
    pub service_name: String,

    /// Endpoint OTLP para envio de traces.
    /// Exemplo: "http://localhost:4317" (gRPC)
    /// Se None, apenas loga para console.
    pub otlp_endpoint: Option<String>,

    /// Taxa de sampling (0.0 a 1.0).
    /// - 1.0 = 100% dos traces são coletados
    /// - 0.1 = 10% dos traces são coletados
    /// - 0.0 = nenhum trace é coletado
    pub sampling_ratio: f64,

    /// Se deve habilitar logging para console.
    /// Útil para desenvolvimento e debugging.
    pub enable_console_logging: bool,

    /// Nível de log mínimo (INFO, DEBUG, WARN, ERROR).
    pub log_level: Level,
}

/// Implementação de Default para TelemetryConfig.
///
/// Valores padrão são conservadores e funcionam sem configuração extra.
impl Default for TelemetryConfig {
    fn default() -> Self {
        Self {
            service_name: "autonomous-quality-agent-runner".to_string(),
            otlp_endpoint: None, // Sem OTLP por padrão
            sampling_ratio: 1.0, // 100% por padrão
            enable_console_logging: true,
            log_level: Level::INFO,
        }
    }
}

impl TelemetryConfig {
    /// Cria configuração a partir de variáveis de ambiente.
    ///
    /// Esta é a forma recomendada em produção, pois permite
    /// configurar sem recompilar o código.
    ///
    /// ## Variáveis suportadas:
    ///
    /// - `OTEL_SERVICE_NAME`: Nome do serviço
    /// - `OTEL_EXPORTER_OTLP_ENDPOINT`: URL do coletor OTLP
    /// - `OTEL_TRACES_SAMPLER_ARG`: Taxa de sampling (0.0-1.0)
    ///
    /// ## Exemplo:
    ///
    /// ```bash
    /// export OTEL_SERVICE_NAME="my-tests"
    /// export OTEL_EXPORTER_OTLP_ENDPOINT="http://jaeger:4317"
    /// export OTEL_TRACES_SAMPLER_ARG="0.5"  # 50% sampling
    /// ```
    pub fn from_env() -> Self {
        // Começa com valores padrão.
        let mut config = Self::default();

        // Sobrescreve com variáveis de ambiente se existirem.
        if let Ok(name) = std::env::var("OTEL_SERVICE_NAME") {
            config.service_name = name;
        }

        if let Ok(endpoint) = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT") {
            config.otlp_endpoint = Some(endpoint);
        }

        if let Ok(ratio) = std::env::var("OTEL_TRACES_SAMPLER_ARG") {
            if let Ok(r) = ratio.parse::<f64>() {
                // Garante que o valor está entre 0.0 e 1.0.
                config.sampling_ratio = r.clamp(0.0, 1.0);
            }
        }

        config
    }
}

// ============================================================================
// INICIALIZAÇÃO
// ============================================================================

/// Inicializa o sistema de telemetria com OpenTelemetry.
///
/// Esta função configura toda a infraestrutura de rastreamento:
/// 1. Cria o TracerProvider com exporter OTLP (se configurado)
/// 2. Configura o sampler (taxa de coleta)
/// 3. Integra com tracing-subscriber para spans automáticos
///
/// ## Parâmetros:
///
/// - `config`: Configuração do sistema de telemetria
///
/// ## Retorno:
///
/// - `Ok(Some(Tracer))`: OTLP configurado, tracer retornado
/// - `Ok(None)`: Apenas console logging (sem OTLP)
/// - `Err`: Erro ao configurar
///
/// ## Para todos entenderem sobre tracing-subscriber:
///
/// O tracing-subscriber é uma biblioteca que recebe "eventos de log"
/// e decide o que fazer com eles (imprimir, enviar para servidor, etc).
/// Aqui configuramos para enviar para OpenTelemetry.
pub fn init_telemetry(config: TelemetryConfig) -> anyhow::Result<Option<Tracer>> {
    // Configura filtro de nível de log.
    // Primeiro tenta ler de RUST_LOG, senão usa o padrão.
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(config.log_level.to_string()));

    // Se temos endpoint OTLP, configuramos o exporter.
    if let Some(endpoint) = &config.otlp_endpoint {
        let tracer = init_otlp_tracer(&config.service_name, endpoint, config.sampling_ratio)?;

        // Cria layer que envia spans para OpenTelemetry.
        let telemetry_layer = OpenTelemetryLayer::new(tracer.clone());

        // Monta o subscriber com as layers.
        let subscriber = tracing_subscriber::registry()
            .with(env_filter)
            .with(telemetry_layer);

        // Adiciona console logging se habilitado.
        if config.enable_console_logging {
            subscriber
                .with(tracing_subscriber::fmt::layer().compact())
                .init();
        } else {
            subscriber.init();
        }

        tracing::info!(
            service_name = %config.service_name,
            endpoint = %endpoint,
            sampling_ratio = config.sampling_ratio,
            "Telemetria OTEL inicializada"
        );

        Ok(Some(tracer))
    } else {
        // Sem OTLP, apenas console logging.
        let subscriber = tracing_subscriber::registry().with(env_filter);

        if config.enable_console_logging {
            subscriber
                .with(tracing_subscriber::fmt::layer().compact())
                .init();
        } else {
            subscriber.init();
        }

        tracing::info!("Telemetria inicializada (apenas console, sem OTLP)");
        Ok(None)
    }
}

// ============================================================================
// TRACER OTLP
// ============================================================================

/// Cria um tracer com OTLP exporter.
///
/// Esta função cria a infraestrutura de baixo nível:
/// - Exporter que envia dados via gRPC
/// - Sampler que decide quais traces coletar
/// - TracerProvider que gerencia tudo
///
/// ## Parâmetros:
///
/// - `service_name`: Nome do serviço
/// - `endpoint`: URL do coletor OTLP (ex: "http://localhost:4317")
/// - `sampling_ratio`: Taxa de sampling (0.0-1.0)
fn init_otlp_tracer(
    service_name: &str,
    endpoint: &str,
    sampling_ratio: f64,
) -> anyhow::Result<Tracer> {
    // Configura o sampler baseado na taxa.
    let sampler = if sampling_ratio >= 1.0 {
        Sampler::AlwaysOn // 100%: sempre coleta
    } else if sampling_ratio <= 0.0 {
        Sampler::AlwaysOff // 0%: nunca coleta
    } else {
        // Entre 0 e 1: coleta baseado no trace ID.
        // Isso garante que traces relacionados são coletados juntos.
        Sampler::TraceIdRatioBased(sampling_ratio)
    };

    // Cria o TracerProvider com batch exporter.
    // Batch significa que acumula spans e envia em lotes (mais eficiente).
    let tracer_provider = TracerProvider::builder()
        .with_batch_exporter(
            opentelemetry_otlp::new_exporter()
                .tonic() // Usa gRPC (protocolo binário)
                .with_endpoint(endpoint) // URL do coletor
                .build_span_exporter()?, // Cria o exporter
            Tokio, // Usa runtime Tokio
        )
        .with_config(
            sdktrace::Config::default()
                .with_sampler(sampler)
                .with_id_generator(RandomIdGenerator::default())
                .with_resource(Resource::new(vec![KeyValue::new(
                    "service.name",
                    service_name.to_string(),
                )])),
        )
        .build();

    // Obtém o tracer do provider.
    let tracer = tracer_provider.tracer(service_name.to_string());

    // Registra o provider globalmente.
    // Isso permite usar `global::tracer()` em qualquer lugar.
    global::set_tracer_provider(tracer_provider);

    Ok(tracer)
}

// ============================================================================
// ENCERRAMENTO
// ============================================================================

/// Encerra o sistema de telemetria, flushing traces pendentes.
///
/// **IMPORTANTE**: Deve ser chamado antes do encerramento da aplicação.
///
/// Por quê? O batch exporter acumula spans na memória.
/// Se a aplicação terminar sem flush, esses spans são perdidos.
///
/// ## Exemplo:
///
/// ```ignore
/// async fn main() {
///     init_telemetry(config)?;
///
///     run_tests().await;
///
///     shutdown_telemetry(); // <-- Não esquecer!
/// }
/// ```
pub fn shutdown_telemetry() {
    global::shutdown_tracer_provider();
    tracing::info!("Telemetria OTEL encerrada");
}

/// Macros e helpers para instrumentação de spans.
#[allow(dead_code)]
pub mod instrumentation {
    use std::time::Instant;

    /// Contexto de instrumentação para uma requisição HTTP.
    #[derive(Debug)]
    pub struct HttpSpanContext {
        /// Método HTTP (GET, POST, etc.)
        pub method: String,
        /// Path da requisição
        pub path: String,
        /// Início da requisição
        pub start_time: Instant,
        /// Status code da resposta (preenchido após execução)
        pub status_code: Option<u16>,
        /// Duração em millisegundos (preenchido após execução)
        pub duration_ms: Option<u64>,
        /// ID do step
        pub step_id: String,
        /// Nome do step
        pub step_name: Option<String>,
    }

    impl HttpSpanContext {
        /// Cria novo contexto de span HTTP.
        pub fn new(method: &str, path: &str, step_id: &str) -> Self {
            Self {
                method: method.to_string(),
                path: path.to_string(),
                start_time: Instant::now(),
                status_code: None,
                duration_ms: None,
                step_id: step_id.to_string(),
                step_name: None,
            }
        }

        /// Define o nome do step.
        pub fn with_name(mut self, name: &str) -> Self {
            self.step_name = Some(name.to_string());
            self
        }

        /// Finaliza o span com o resultado.
        pub fn finish(&mut self, status_code: u16) {
            self.status_code = Some(status_code);
            self.duration_ms = Some(self.start_time.elapsed().as_millis() as u64);
        }

        /// Retorna os atributos como KeyValues para OTEL.
        pub fn attributes(&self) -> Vec<(&'static str, String)> {
            let mut attrs = vec![
                ("http.method", self.method.clone()),
                ("http.target", self.path.clone()),
                ("step.id", self.step_id.clone()),
            ];

            if let Some(name) = &self.step_name {
                attrs.push(("step.name", name.clone()));
            }

            if let Some(status) = self.status_code {
                attrs.push(("http.status_code", status.to_string()));
            }

            if let Some(duration) = self.duration_ms {
                attrs.push(("http.duration_ms", duration.to_string()));
            }

            attrs
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_default() {
        let config = TelemetryConfig::default();
        assert_eq!(config.service_name, "autonomous-quality-agent-runner");
        assert!(config.otlp_endpoint.is_none());
        assert_eq!(config.sampling_ratio, 1.0);
        assert!(config.enable_console_logging);
    }

    #[test]
    fn test_http_span_context() {
        use instrumentation::HttpSpanContext;

        let mut ctx = HttpSpanContext::new("GET", "/api/users", "step-1").with_name("List Users");

        assert_eq!(ctx.method, "GET");
        assert_eq!(ctx.path, "/api/users");
        assert_eq!(ctx.step_id, "step-1");
        assert_eq!(ctx.step_name, Some("List Users".to_string()));
        assert!(ctx.status_code.is_none());

        ctx.finish(200);

        assert_eq!(ctx.status_code, Some(200));
        assert!(ctx.duration_ms.is_some());
    }

    #[test]
    fn test_http_span_attributes() {
        use instrumentation::HttpSpanContext;

        let mut ctx = HttpSpanContext::new("POST", "/api/orders", "step-2");
        ctx.finish(201);

        let attrs = ctx.attributes();

        assert!(attrs
            .iter()
            .any(|(k, v)| *k == "http.method" && v == "POST"));
        assert!(attrs
            .iter()
            .any(|(k, v)| *k == "http.target" && v == "/api/orders"));
        assert!(attrs
            .iter()
            .any(|(k, v)| *k == "http.status_code" && v == "201"));
    }
}
