//! # Módulo de Telemetria OpenTelemetry
//!
//! Fornece integração completa com OpenTelemetry para observabilidade distribuída.
//! Exporta traces/spans com atributos detalhados de cada requisição HTTP.
//!
//! ## Funcionalidades
//!
//! - Configuração de tracer com OTLP exporter
//! - Suporte a sampling configurável
//! - Spans instrumentados com atributos HTTP semânticos
//! - Integração com tracing-subscriber

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

/// Configuração do sistema de telemetria.
#[derive(Debug, Clone)]
pub struct TelemetryConfig {
    /// Nome do serviço para identificação nos traces.
    pub service_name: String,
    /// Endpoint OTLP para envio de traces (ex: "http://localhost:4317").
    pub otlp_endpoint: Option<String>,
    /// Taxa de sampling (0.0 a 1.0). 1.0 = 100% dos traces.
    pub sampling_ratio: f64,
    /// Se deve habilitar logging para console também.
    pub enable_console_logging: bool,
    /// Nível de log mínimo.
    pub log_level: Level,
}

impl Default for TelemetryConfig {
    fn default() -> Self {
        Self {
            service_name: "autonomous-quality-agent-runner".to_string(),
            otlp_endpoint: None,
            sampling_ratio: 1.0,
            enable_console_logging: true,
            log_level: Level::INFO,
        }
    }
}

impl TelemetryConfig {
    /// Cria configuração a partir de variáveis de ambiente.
    ///
    /// Variáveis suportadas:
    /// - OTEL_SERVICE_NAME: Nome do serviço
    /// - OTEL_EXPORTER_OTLP_ENDPOINT: Endpoint OTLP
    /// - OTEL_TRACES_SAMPLER_ARG: Taxa de sampling (0.0-1.0)
    pub fn from_env() -> Self {
        let mut config = Self::default();

        if let Ok(name) = std::env::var("OTEL_SERVICE_NAME") {
            config.service_name = name;
        }

        if let Ok(endpoint) = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT") {
            config.otlp_endpoint = Some(endpoint);
        }

        if let Ok(ratio) = std::env::var("OTEL_TRACES_SAMPLER_ARG") {
            if let Ok(r) = ratio.parse::<f64>() {
                config.sampling_ratio = r.clamp(0.0, 1.0);
            }
        }

        config
    }
}

/// Inicializa o sistema de telemetria com OpenTelemetry.
///
/// Configura:
/// - Tracer com OTLP exporter (se endpoint configurado)
/// - Sampler com ratio configurável
/// - Integração com tracing-subscriber
///
/// # Exemplo
///
/// ```ignore
/// let config = TelemetryConfig {
///     service_name: "my-service".to_string(),
///     otlp_endpoint: Some("http://localhost:4317".to_string()),
///     sampling_ratio: 0.5, // 50% dos traces
///     ..Default::default()
/// };
/// init_telemetry(config)?;
/// ```
pub fn init_telemetry(config: TelemetryConfig) -> anyhow::Result<Option<Tracer>> {
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(config.log_level.to_string()));

    // Se temos endpoint OTLP, configuramos o exporter
    if let Some(endpoint) = &config.otlp_endpoint {
        let tracer = init_otlp_tracer(&config.service_name, endpoint, config.sampling_ratio)?;

        let telemetry_layer = OpenTelemetryLayer::new(tracer.clone());

        let subscriber = tracing_subscriber::registry()
            .with(env_filter)
            .with(telemetry_layer);

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
        // Sem OTLP, apenas console logging
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

/// Cria um tracer com OTLP exporter.
fn init_otlp_tracer(
    service_name: &str,
    endpoint: &str,
    sampling_ratio: f64,
) -> anyhow::Result<Tracer> {
    let sampler = if sampling_ratio >= 1.0 {
        Sampler::AlwaysOn
    } else if sampling_ratio <= 0.0 {
        Sampler::AlwaysOff
    } else {
        Sampler::TraceIdRatioBased(sampling_ratio)
    };

    // Cria o TracerProvider manualmente
    let tracer_provider = TracerProvider::builder()
        .with_batch_exporter(
            opentelemetry_otlp::new_exporter()
                .tonic()
                .with_endpoint(endpoint)
                .build_span_exporter()?,
            Tokio,
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

    // Obtém o tracer do provider
    let tracer = tracer_provider.tracer(service_name.to_string());

    // Registra o provider globalmente
    global::set_tracer_provider(tracer_provider);

    Ok(tracer)
}

/// Encerra o sistema de telemetria, flushing traces pendentes.
///
/// Deve ser chamado antes do encerramento da aplicação para garantir
/// que todos os traces sejam enviados.
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

        assert!(attrs.iter().any(|(k, v)| *k == "http.method" && v == "POST"));
        assert!(attrs
            .iter()
            .any(|(k, v)| *k == "http.target" && v == "/api/orders"));
        assert!(attrs
            .iter()
            .any(|(k, v)| *k == "http.status_code" && v == "201"));
    }
}
