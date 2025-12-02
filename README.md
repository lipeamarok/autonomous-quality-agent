# Autonomous Quality Agent (MVP v1.0)

> **Transformando requisitos em testes executáveis com IA e Alta Performance.**

O **Autonomous Quality Agent** é uma plataforma de engenharia de qualidade que atua como um agente inteligente. Ele ingere documentação técnica (Swagger, Texto), planeja cenários de teste usando LLMs (The Brain) e os executa com performance nativa e concorrência extrema (The Runner).

## 🏗 Arquitetura (Monorepo)

O projeto é dividido em dois componentes principais desacoplados pelo protocolo **UTDL (Universal Test Definition Language)**.

### 🧠 The Brain (`/brain`)

- **Linguagem:** Python 3.11+
- **Responsabilidade:** Cognição, Planejamento e Validação.
- **Função:** Lê requisitos, gera planos de teste em JSON (UTDL) e garante que são válidos antes da execução.

### 🦀 The Runner (`/runner`)

- **Linguagem:** Rust (Tokio + Reqwest)
- **Responsabilidade:** Execução Determinística e Performance.
- **Função:** Consome o plano UTDL, executa requisições HTTP em paralelo massivo e gera telemetria (OpenTelemetry).

## 🚀 Como Rodar (Fase 0)

### Pré-requisitos

- Python 3.11+
- Rust (Cargo)
- Make (opcional)

### Setup Inicial

```bash
# Configurar ambiente Python e Rust
make setup
```

### Rodando o Hello World

```bash
# Testa se Brain e Runner estão respondendo
make test
```

## 📄 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.
