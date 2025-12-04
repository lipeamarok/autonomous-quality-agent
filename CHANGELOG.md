# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## Licenciamento

- **Versões < 1.0.0**: Licenciadas sob [MIT License](https://opensource.org/licenses/MIT)
- **Versões >= 1.0.0**: Licenciadas sob [Elastic License 2.0 (ELv2)](https://www.elastic.co/licensing/elastic-license)

---

## [Unreleased]

### Planejado para 1.0.0 (MVP)
- Mudança de licença para ELv2
- Documentação completa
- Estabilização de APIs

---

## [0.3.0] - 2024-12-04

### Adicionado
- **LLM Provider Strategy**: Sistema de providers com mock/real toggle
  - `MockLLMProvider` para testes determinísticos
  - `RealLLMProvider` com suporte a OpenAI, Anthropic, xAI via LiteLLM
  - Flag `--llm-mode` e variável `AQA_LLM_MODE`
- **Testes E2E com Runner real**: 10 testes que executam o binário Rust
  - Health check, multi-step, POST, assertions, timestamps
- **ExecutionSummary no Runner**: Estatísticas de execução
  - total_steps, passed, failed, skipped, total_retries, duration_ms
- **Flags no generate_cmd**: `--include-negative` e `--include-auth`
- **Configuração ruff**: Linting Python configurado no pyproject.toml

### Alterado
- Runner atualizado para versão 0.3.0 (alinhamento com Brain)
- Documentação TDD atualizada com novas seções (4.16-4.19)
- Estrutura de diretórios documentada (seção 7.1)

### Corrigido
- Skip de testes Windows no CI Linux (sys.platform check)
- Formatação Rust (cargo fmt)

---

## [0.2.0] - 2024-11-XX

### Adicionado
- **Detecção de Segurança**: Análise automática de OpenAPI para OAuth2, Bearer, API Key
- **Casos Negativos**: Geração automática de testes de boundary e validação
- **CLI completo**: Comandos init, generate, plan, validate, run, explain, demo
- **Cache de planos**: Armazenamento local com hash de requisitos
- **Validador UTDL**: Validação de schema com erros detalhados

### Alterado
- Migração para estrutura monorepo (brain/ + runner/)
- Runner com suporte a execução paralela

---

## [0.1.0] - 2024-10-XX

### Adicionado
- **Brain (Python)**: Módulo de IA para geração de planos
  - Parser de OpenAPI/Swagger
  - Integração com LLMs via LiteLLM
  - Gerador de planos UTDL
- **Runner (Rust)**: Motor de execução de alta performance
  - Executor HTTP assíncrono
  - Suporte a interpolação de variáveis
  - Relatórios JSON estruturados
- **Protocolo UTDL**: Formato de definição de testes
  - Spec version 0.1
  - Steps, assertions, extractions
- **CI/CD**: GitHub Actions com testes Python e Rust

---

## Convenções de Versionamento

- **MAJOR (X.0.0)**: Mudanças incompatíveis de API ou licença
- **MINOR (0.X.0)**: Novas funcionalidades retrocompatíveis
- **PATCH (0.0.X)**: Correções de bugs retrocompatíveis

## Links

- [Repositório](https://github.com/lipeamarok/autonomous-quality-agent)
- [Issues](https://github.com/lipeamarok/autonomous-quality-agent/issues)
- [Documentação Técnica (TDD)](docs/Technical%20Design%20Document%20(TDD).md)
