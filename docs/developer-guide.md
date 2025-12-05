# Autonomous Quality Agent - Developer Guide

> Guia para desenvolvedores: como contribuir, estrutura do código, testes e padrões.

## Índice

1. [Setup de Desenvolvimento](#1-setup-de-desenvolvimento)
2. [Estrutura do Projeto](#2-estrutura-do-projeto)
3. [Brain (Python)](#3-brain-python)
4. [Runner (Rust)](#4-runner-rust)
5. [Schema UTDL e Conformidade](#5-schema-utdl-e-conformidade)
6. [Testes](#6-testes)
7. [Padrões de Código](#7-padrões-de-código)
8. [Fluxo de Contribuição](#8-fluxo-de-contribuição)
9. [CI/CD](#9-cicd)

---

## 1. Setup de Desenvolvimento

### Pré-requisitos

- Python 3.11+
- Rust 1.75+
- Git
- Make (opcional, mas recomendado)

### Clone e Setup Inicial

```bash
git clone https://github.com/lipeamarok/autonomous-quality-agent.git
cd autonomous-quality-agent

# Setup completo via Make
make setup

# Ou manualmente:
# Brain
cd brain
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Runner
cd ../runner
cargo build
```

### Verificar Instalação

```bash
# Testes Python
cd brain && pytest tests/ -v

# Testes Rust
cd runner && cargo test

# Tudo via Make
make test
```

---

## 2. Estrutura do Projeto

```
autonomous-quality-agent/
├── brain/                    # 🐍 Python - Orquestração e IA
│   ├── src/
│   │   ├── cli/              # Interface de linha de comando
│   │   │   ├── commands/     # Subcomandos (generate, run, etc)
│   │   │   └── main.py       # Entry point CLI
│   │   ├── generator/        # Geração de planos via LLM
│   │   ├── ingestion/        # Parsing de OpenAPI, segurança
│   │   ├── llm/              # Providers de LLM (mock/real)
│   │   ├── runner/           # Integração com Runner Rust
│   │   ├── storage/          # Persistência (SQLite/S3/JSON)
│   │   ├── validator/        # Validação de UTDL
│   │   ├── cache.py          # Cache de planos
│   │   ├── config.py         # Configuração centralizada
│   │   └── main.py           # Entry point programático
│   ├── tests/                # Testes unitários e E2E
│   ├── pyproject.toml        # Dependências Python
│   └── requirements.txt      # Lock file
│
├── runner/                   # 🦀 Rust - Execução de alta performance
│   ├── src/
│   │   ├── context/          # Variáveis e interpolação
│   │   ├── executors/        # HTTP, Wait, GraphQL
│   │   ├── extractors/       # Extração de dados
│   │   ├── limits/           # Rate limiting
│   │   ├── loader/           # Parser UTDL
│   │   ├── planner/          # DAG de execução
│   │   ├── protocol/         # Tipos UTDL
│   │   ├── retry/            # Políticas de retry
│   │   ├── telemetry/        # OTEL
│   │   ├── validation/       # Validação de planos
│   │   ├── errors/           # Códigos de erro estruturados
│   │   └── main.rs           # Entry point
│   └── Cargo.toml            # Dependências Rust
│
├── schemas/                  # JSON Schemas
│   ├── utdl.schema.json      # Schema canônico UTDL (fonte de verdade)
│   ├── context.schema.json
│   └── runner_report.schema.json
│
├── scripts/                  # Scripts de CI/CD
│   └── validate_schema.py    # Validação de consistência
│
├── docs/                     # Documentação
│   ├── user-guide.md         # Para usuários
│   ├── developer-guide.md    # Este arquivo
│   ├── architecture.md       # Decisões técnicas
│   └── error_codes.md        # Referência de erros
│
├── Makefile                  # Comandos de desenvolvimento
└── README.md                 # Visão geral
```

---

## 3. Brain (Python)

### Stack Tecnológica

| Componente | Tecnologia | Propósito |
|------------|------------|-----------|
| CLI | Click | Interface de linha de comando |
| Validação | Pydantic v2 | Validação de schemas UTDL |
| LLM | LiteLLM | Abstração de providers |
| Parsing | PyYAML, orjson | Parsing eficiente |
| Testes | pytest | Framework de testes |
| Tipos | pyright | Type checking estático |

### Módulos Principais

#### `cli/` - Interface de Linha de Comando

```python
# brain/src/cli/main.py
@click.group()
def cli():
    """Autonomous Quality Agent CLI"""
    pass

@cli.command()
@click.option("--input", "-i", help="Requisito em texto")
def generate(input: str):
    """Gera plano UTDL"""
    ...
```

#### `llm/` - Providers de LLM

Implementa o padrão Strategy para alternar entre LLMs:

```python
# brain/src/llm/base.py
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> LLMResponse:
        """Gera resposta do LLM"""
        pass

# brain/src/llm/providers.py
def get_llm_provider(mode: str = "real") -> BaseLLMProvider:
    if mode == "mock":
        return MockLLMProvider()
    return RealLLMProvider()
```

#### `validator/` - Validação UTDL

```python
# brain/src/validator/utdl_validator.py
class UTDLValidator:
    def validate(self, data: dict) -> ValidationResult:
        """Valida plano UTDL"""
        # 1. Estrutura Pydantic
        # 2. IDs únicos
        # 3. Dependências existem
        # 4. Sem ciclos
        # 5. Actions válidas
```

#### `storage/` - Persistência

Três backends disponíveis:

```python
# SQLite (padrão)
storage = SQLiteStorage(db_path="history.db")

# S3 (cloud)
storage = S3Storage(bucket="my-bucket")

# JSON (legacy)
storage = JsonStorage(history_dir="./history")

# Factory
storage = create_storage("sqlite")
```

### Adicionando um Novo Comando CLI

O AQA usa um sistema de **registry** para gerenciar comandos CLI, evitando imports circulares e facilitando a extensibilidade.

#### Sistema de Registry

```python
# brain/src/cli/registry.py
from typing import TypeVar
import click

T = TypeVar("T", bound=click.Command)

def register_command(cmd: T) -> T:
    """Decorator que registra um comando automaticamente."""
    _registered_commands.append(cmd)
    return cmd
```

#### Adicionando um Comando Simples

1. Crie o arquivo em `brain/src/cli/commands/`:

```python
# brain/src/cli/commands/my_cmd.py
import click
from ..registry import register_command

@register_command
@click.command("mycommand")
@click.option("--param", "-p", help="Descrição")
def my_command(param: str) -> None:
    """Descrição do comando"""
    click.echo(f"Executando com {param}")
```

2. Adicione à lista de imports em `brain/src/cli/commands/__init__.py`:

```python
from .my_cmd import my_command

__all__ = [..., "my_command"]
```

**Pronto!** O comando será registrado automaticamente.

#### Adicionando um Grupo de Comandos

Para comandos com subcomandos, use `@click.group()`:

```python
# brain/src/cli/commands/mygroup_cmd.py
import click
from ..registry import register_command

@register_command
@click.group()
def mygroup() -> None:
    """Grupo de comandos relacionados."""
    pass

@mygroup.command()
def sub1() -> None:
    """Primeiro subcomando."""
    click.echo("sub1")

@mygroup.command()
def sub2() -> None:
    """Segundo subcomando."""
    click.echo("sub2")
```

#### Por que usar o Registry?

| Antes (imports diretos) | Depois (registry) |
|-------------------------|-------------------|
| Imports no final de `main.py` | Decorator `@register_command` |
| Risco de imports circulares | Sem dependências circulares |
| Difícil testar isoladamente | Fácil testar |
| Acoplamento alto | Baixo acoplamento |

---

## 4. Runner (Rust)

### Stack Tecnológica

| Componente | Crate | Propósito |
|------------|-------|-----------|
| Async Runtime | tokio | I/O assíncrono |
| HTTP Client | reqwest | Requisições HTTP |
| Serialização | serde, serde_json | JSON parsing |
| CLI | clap | Argumentos |
| Telemetria | tracing, opentelemetry | Observabilidade |
| Erros | anyhow, thiserror | Error handling |

### Módulos Principais

#### `executors/` - Executores de Ações

Implementa o trait `StepExecutor`:

```rust
// runner/src/executors/mod.rs
#[async_trait]
pub trait StepExecutor: Send + Sync {
    fn can_handle(&self, action: &str) -> bool;
    async fn execute(&self, step: &Step, ctx: &mut Context) -> Result<StepResult>;
}

// runner/src/executors/http.rs
pub struct HttpExecutor { ... }

impl StepExecutor for HttpExecutor {
    fn can_handle(&self, action: &str) -> bool {
        action == "http_request"
    }
    // ...
}
```

#### `context/` - Variáveis e Interpolação

```rust
// runner/src/context/mod.rs
pub struct Context {
    variables: HashMap<String, Value>,
}

impl Context {
    pub fn interpolate(&self, template: &str) -> String {
        // Substitui ${var} pelos valores
    }

    pub fn set(&mut self, key: &str, value: Value) {
        self.variables.insert(key.to_string(), value);
    }
}
```

#### `planner/` - DAG de Execução

```rust
// runner/src/planner/mod.rs
pub struct ExecutionPlan {
    dag: HashMap<String, Vec<String>>,
    roots: Vec<String>,
}

impl ExecutionPlan {
    pub fn from_steps(steps: &[Step]) -> Result<Self> {
        // Constrói DAG
        // Detecta ciclos
        // Identifica raízes
    }
}
```

### Adicionando um Novo Executor

1. Crie o arquivo em `runner/src/executors/`:

```rust
// runner/src/executors/grpc.rs
use super::{StepExecutor, StepResult};

pub struct GrpcExecutor;

#[async_trait]
impl StepExecutor for GrpcExecutor {
    fn can_handle(&self, action: &str) -> bool {
        action == "grpc_call"
    }

    async fn execute(&self, step: &Step, ctx: &mut Context) -> Result<StepResult> {
        // Implementação
    }
}
```

2. Registre em `runner/src/executors/mod.rs`:

```rust
mod grpc;
pub use grpc::GrpcExecutor;

pub fn get_executors() -> Vec<Box<dyn StepExecutor>> {
    vec![
        Box::new(HttpExecutor::new()),
        Box::new(WaitExecutor),
        Box::new(GrpcExecutor),  // Novo
    ]
}
```

---

## 5. Schema UTDL e Conformidade

O projeto mantém um **schema canônico** em `schemas/utdl.schema.json` que serve como fonte de verdade para o formato UTDL. Este schema é sincronizado com:

- **Pydantic (Python)**: `brain/src/validator/models.py`
- **Serde (Rust)**: `runner/src/protocol/mod.rs`

### Arquitetura do Schema

```
schemas/utdl.schema.json     ← Schema canônico (JSON Schema Draft-07)
        ↓
brain/src/schema/            ← Módulo de geração e comparação
├── generator.py             ← Gera schema Pydantic, compara com canônico
└── __init__.py
        ↓
brain/tests/test_conformance.py  ← Testes de cross-validation
```

### Testes de Conformidade

Os testes de conformidade geram **planos aleatórios** e validam em múltiplas camadas:

```python
# brain/tests/test_conformance.py
class TestCrossValidation:
    def test_random_plan_validates_in_pydantic(self):
        """Plano aleatório valida em Pydantic"""
        plan = PlanGenerator().generate_random_plan()
        Plan.model_validate(plan)  # Deve passar

    def test_random_plan_validates_in_rust(self):
        """Plano aleatório valida no Runner Rust"""
        plan = PlanGenerator().generate_random_plan()
        result = run_rust_validation(plan)
        assert result.returncode == 0
```

### Validação de CI

Execute o script de validação para verificar consistência:

```bash
python scripts/validate_schema.py
```

Este script:
1. Verifica se arquivos de schema existem
2. Valida que modelos essenciais existem em Pydantic e Rust
3. Executa testes de conformidade

### Adicionando Novos Campos ao UTDL

1. **Atualize o schema canônico**:
   ```json
   // schemas/utdl.schema.json
   "Step": {
     "properties": {
       "new_field": { "type": "string" }
     }
   }
   ```

2. **Atualize Pydantic**:
   ```python
   # brain/src/validator/models.py
   class Step(BaseModel):
       new_field: str | None = None
   ```

3. **Atualize Rust**:
   ```rust
   // runner/src/protocol/mod.rs
   #[derive(Deserialize)]
   pub struct Step {
       pub new_field: Option<String>,
   }
   ```

4. **Execute validação**:
   ```bash
   python scripts/validate_schema.py
   pytest brain/tests/test_conformance.py -v
   ```

---

## 6. Testes

### Estrutura de Testes

```
brain/tests/
├── test_cli.py              # Testes de CLI
├── test_validator.py        # Validação UTDL
├── test_llm_providers.py    # Mock/Real providers
├── test_storage.py          # Backends de storage
├── test_swagger.py          # Parsing OpenAPI
├── test_security.py         # Detecção de auth
├── test_negative_cases.py   # Casos negativos
├── test_integration.py      # Integração Brain
├── test_e2e_runner*.py      # E2E com Runner
└── conftest.py              # Fixtures compartilhadas

runner/src/
├── context/mod.rs           # #[cfg(test)] mod tests
├── executors/http.rs        # #[cfg(test)] mod tests
└── ...
```

### Executando Testes

```bash
# Todos os testes Python
cd brain && pytest tests/ -v

# Testes específicos
pytest tests/test_validator.py -v
pytest tests/test_storage.py::TestSQLiteStorage -v

# Com cobertura
pytest tests/ --cov=src --cov-report=html

# Testes Rust
cd runner && cargo test

# Testes específicos Rust
cargo test context::tests
cargo test --test integration

# Tudo via Make
make test
```

### Escrevendo Testes Python

```python
# brain/tests/test_example.py
import pytest
from src.validator import UTDLValidator

class TestMyFeature:
    """Testes para minha feature"""

    @pytest.fixture
    def validator(self) -> UTDLValidator:
        return UTDLValidator()

    def test_valid_plan(self, validator: UTDLValidator) -> None:
        """Plano válido deve passar"""
        plan = {"spec_version": "0.1", "meta": {...}, ...}
        result = validator.validate(plan)
        assert result.is_valid

    def test_invalid_plan_raises(self, validator: UTDLValidator) -> None:
        """Plano inválido deve falhar"""
        with pytest.raises(ValueError):
            validator.validate({})
```

### Escrevendo Testes Rust

```rust
// runner/src/my_module.rs
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic() {
        let result = my_function();
        assert_eq!(result, expected);
    }

    #[tokio::test]
    async fn test_async() {
        let result = my_async_function().await;
        assert!(result.is_ok());
    }
}
```

### Fixtures Importantes

```python
# brain/tests/conftest.py

@pytest.fixture
def sample_plan() -> dict:
    """Plano UTDL válido para testes"""
    return {
        "spec_version": "0.1",
        "meta": {"id": "test", "name": "Test"},
        "config": {"base_url": "https://api.test"},
        "steps": [...]
    }

@pytest.fixture
def mock_llm_provider():
    """Provider mock para testes"""
    from src.llm import MockLLMProvider
    return MockLLMProvider()
```

---

## 7. Padrões de Código

### Python

#### Type Hints Obrigatórios

```python
# ✅ Correto
def process(data: dict[str, Any]) -> ValidationResult:
    ...

# ❌ Errado
def process(data):
    ...
```

#### Docstrings

```python
def validate(self, data: dict[str, Any]) -> ValidationResult:
    """Valida um plano UTDL.

    Args:
        data: Dicionário com o plano UTDL

    Returns:
        ValidationResult com is_valid e errors

    Raises:
        ValueError: Se estrutura básica inválida
    """
```

#### Formatação

```bash
# Formatter
black src/ tests/

# Linter
ruff check src/ tests/

# Type checker
pyright src/
```

### Rust

#### Error Handling

```rust
// ✅ Use Result e ?
fn parse(json: &str) -> Result<Plan> {
    let plan: Plan = serde_json::from_str(json)?;
    Ok(plan)
}

// ❌ Evite unwrap em produção
fn parse(json: &str) -> Plan {
    serde_json::from_str(json).unwrap()  // Pode panic
}
```

#### Formatação

```bash
# Formatter
cargo fmt

# Linter
cargo clippy -- -D warnings
```

### Commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add GraphQL executor support
fix: resolve timeout issue in HTTP executor
docs: update developer guide
test: add E2E tests for auth flow
refactor: extract validation logic
chore: update dependencies
```

---

## 8. Fluxo de Contribuição

### 1. Fork e Clone

```bash
# Fork via GitHub UI
git clone https://github.com/SEU-USER/autonomous-quality-agent.git
cd autonomous-quality-agent
git remote add upstream https://github.com/lipeamarok/autonomous-quality-agent.git
```

### 2. Branch

```bash
git checkout -b feat/my-feature
# ou
git checkout -b fix/issue-123
```

### 3. Desenvolva

```bash
# Faça suas mudanças
# Rode testes frequentemente
make test
```

### 4. Commit

```bash
git add .
git commit -m "feat: add new feature X"
```

### 5. Push e PR

```bash
git push origin feat/my-feature
# Abra PR via GitHub
```

### Checklist do PR

- [ ] Testes passando (`make test`)
- [ ] Lint passando (`make lint`)
- [ ] Type check passando (`pyright`)
- [ ] Documentação atualizada (se necessário)
- [ ] Commit messages seguem padrão

---

## 9. CI/CD

### GitHub Actions

O projeto usa GitHub Actions para CI:

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v

  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo test
```

### Makefile

Comandos disponíveis:

```bash
make setup     # Setup inicial
make test      # Todos os testes
make lint      # Linting
make fmt       # Formatação
make build     # Build de produção
make clean     # Limpar artifacts
make demo      # Rodar demo
```

---

## Próximos Passos

- Leia a [Architecture](./architecture.md) para decisões técnicas
- Consulte o [User Guide](./user-guide.md) para uso
- Veja [Error Codes](./error_codes.md) para referência
