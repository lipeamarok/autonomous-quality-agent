"""
================================================================================
MODELOS PYDANTIC PARA UTDL — FONTE DA VERDADE PARA VALIDAÇÃO
================================================================================

Este módulo define as estruturas de dados do UTDL (Universal Test Definition
Language) usando Pydantic, uma biblioteca de validação de dados para Python.

## Para todos entenderem:

Quando recebemos dados (de um arquivo JSON, de uma API, etc.), precisamos
verificar se esses dados estão corretos. Pydantic faz isso automaticamente:

1. Define a estrutura esperada (quais campos, quais tipos)
2. Valida os dados recebidos contra essa estrutura
3. Gera mensagens de erro claras se algo estiver errado

## O que é UTDL?

UTDL = Universal Test Definition Language
É o formato de arquivo que usamos para definir planos de teste.
É basicamente JSON com uma estrutura específica.

## Para que servem estes modelos?

1. **Validar planos gerados por LLM** antes de enviar ao Runner
2. **Fornecer mensagens de erro claras** quando a validação falha
3. **Habilitar autocomplete** e type checking no código

## Hierarquia dos modelos:

```
Plan (raiz)
├── spec_version: "0.1"
├── meta: Meta
│   ├── id, name, description, tags, created_at
├── config: Config
│   ├── base_url, timeout_ms, global_headers, variables
└── steps: [Step, Step, ...]
    └── Step
        ├── id, action, description, depends_on, params
        ├── assertions: [Assertion, ...]
        ├── extract: [Extraction, ...]
        └── recovery_policy: RecoveryPolicy
```

## Tecnologias usadas:

- **Pydantic v2**: Validação de dados com modelos tipados
- **Field validators**: Validação customizada de campos
- **Literal types**: Restringe valores a um conjunto fixo
"""

# =============================================================================
# IMPORTS
# =============================================================================

from __future__ import annotations

# uuid: Para gerar IDs únicos
import uuid

# datetime: Para timestamps
from datetime import datetime, timezone

# typing: Anotações de tipo
from typing import Any, Literal

# Pydantic: Biblioteca de validação de dados
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# MODELOS AUXILIARES
# =============================================================================


class Assertion(BaseModel):
    """
    Define uma regra de validação para a resposta de um step.

    ## Para todos entenderem:
    Assertions são "verificações" que fazemos após uma requisição HTTP.
    Por exemplo: "O status deve ser 200" ou "O campo 'name' deve existir".

    ## Tipos de assertion:

    | Tipo        | O que valida                        | Exemplo                     |
    |-------------|-------------------------------------|-----------------------------|
    | status_code | Código HTTP da resposta             | 200, 404, 500               |
    | json_body   | Campo específico no JSON de resposta| data.user.name              |
    | header      | Header da resposta HTTP             | Content-Type, X-Request-Id  |
    | latency     | Tempo de resposta em milissegundos  | < 500ms                     |

    ## Operadores:

    | Operador | Significado    | Exemplo de uso           |
    |----------|----------------|--------------------------|
    | eq       | igual          | status_code eq 200       |
    | neq      | diferente      | status_code neq 500      |
    | lt       | menor que      | latency lt 1000          |
    | gt       | maior que      | response.count gt 0      |
    | contains | contém string  | body.message contains ok |

    ## Atributos:
        type: Tipo de assertion (status_code, json_body, header, latency)
        operator: Operador de comparação (eq, neq, lt, gt, contains)
        value: Valor esperado para comparação
        path: Caminho JSONPath ou nome do header (opcional, requerido para json_body/header)

    ## Exemplos:
        >>> # Verificar status 200
        >>> assertion = Assertion(type="status_code", operator="eq", value=200)
        >>>
        >>> # Verificar campo no JSON
        >>> assertion = Assertion(type="json_body", path="data.id", operator="eq", value=123)
        >>>
        >>> # Verificar tempo de resposta < 500ms
        >>> assertion = Assertion(type="latency", operator="lt", value=500)
    """

    # Literal restringe os valores possíveis
    type: Literal["status_code", "json_body", "header", "latency"]
    operator: Literal["eq", "neq", "lt", "gt", "contains"]
    value: Any  # Pode ser int, str, bool, etc.
    path: str | None = None  # Obrigatório para json_body e header


class Extraction(BaseModel):
    """
    Define como extrair dados de uma resposta para variáveis de contexto.

    ## Para todos entenderem:
    Extractions permitem "capturar" valores de uma resposta e usar depois.
    Por exemplo: Fazer login, capturar o token, usar em requisições seguintes.

    ## Fluxo típico:

    ```
    Step 1: POST /login
    Response: {"token": "abc123"}
    Extraction: body.token -> variável "auth_token"

    Step 2: GET /users
    Headers: {"Authorization": "Bearer ${auth_token}"}
    ```

    ## Atributos:
        source: De onde extrair - "body" (JSON) ou "header"
        path: Caminho para o valor (JSONPath para body, nome para header)
        target: Nome da variável onde guardar o valor

    ## Exemplos:
        >>> # Extrair token do body
        >>> extraction = Extraction(source="body", path="auth.token", target="token")
        >>> # Após execução, ${token} estará disponível nos próximos steps
        >>>
        >>> # Extrair ID de header
        >>> extraction = Extraction(source="header", path="X-Request-Id", target="request_id")
    """

    source: Literal["body", "header"]
    path: str
    target: str


class RecoveryPolicy(BaseModel):
    """
    Define o comportamento de retry em caso de falha de um step.

    ## Para todos entenderem:
    Às vezes requisições falham por motivos temporários (rede instável,
    servidor sobrecarregado). RecoveryPolicy define o que fazer nesses casos.

    ## Estratégias disponíveis:

    | Estratégia | Comportamento                                    |
    |------------|--------------------------------------------------|
    | retry      | Tenta novamente até max_attempts com backoff     |
    | fail_fast  | Falha imediatamente (padrão)                     |
    | ignore     | Ignora a falha e continua com próximos steps     |

    ## Backoff exponencial:
    O tempo de espera entre tentativas aumenta exponencialmente.
    Com backoff_ms=500 e backoff_factor=2.0:
    - Tentativa 1: imediata
    - Tentativa 2: espera 500ms
    - Tentativa 3: espera 1000ms
    - Tentativa 4: espera 2000ms

    ## Atributos:
        strategy: Estratégia de recuperação
        max_attempts: Número máximo de tentativas (1-10)
        backoff_ms: Tempo inicial de espera entre tentativas em ms
        backoff_factor: Multiplicador para backoff exponencial

    ## Exemplo:
        >>> policy = RecoveryPolicy(strategy="retry", max_attempts=3, backoff_ms=1000)
        >>> # Tentativas: imediato, 1s, 2s (com backoff_factor=2.0 padrão)
    """

    strategy: Literal["retry", "fail_fast", "ignore"] = "fail_fast"
    # Field permite configurar validação e valores padrão
    # ge=1 significa "greater or equal to 1"
    # le=10 significa "less or equal to 10"
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_ms: int = Field(default=500, ge=0)
    backoff_factor: float = Field(default=2.0, ge=1.0)


# =============================================================================
# MODELO DE STEP
# =============================================================================


class Step(BaseModel):
    """
    Uma ação atômica única no plano de testes.

    ## Para todos entenderem:
    Steps são as "unidades básicas" de um plano de teste.
    Cada step representa UMA ação - geralmente uma requisição HTTP.

    ## Anatomia de um step:

    ```json
    {
      "id": "login",                    // Identificador único
      "action": "http_request",         // Tipo de ação
      "description": "Autentica user",  // Descrição legível
      "depends_on": [],                 // Steps que devem executar antes
      "params": {                       // Parâmetros da ação
        "method": "POST",
        "path": "/auth/login",
        "body": {"email": "test@example.com"}
      },
      "assertions": [...],              // Validações
      "extract": [...],                 // Extrações
      "recovery_policy": {...}          // Política de retry
    }
    ```

    ## Atributos:
        id: Identificador único do step (usado para dependências)
        action: Tipo de ação - "http_request" ou "wait"
        description: Descrição legível do que o step faz
        depends_on: Lista de IDs de steps que devem executar antes
        params: Parâmetros específicos da ação
        assertions: Lista de validações a executar na resposta
        extract: Lista de extrações para capturar dados
        recovery_policy: Política de retry em caso de falha

    ## Exemplo:
        >>> step = Step(
        ...     id="login",
        ...     action="http_request",
        ...     description="Autentica o usuário",
        ...     params={"method": "POST", "path": "/auth/login", "body": {"user": "test"}}
        ... )
    """

    id: str
    action: Literal["http_request", "wait"]
    description: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, Any]
    assertions: list[Assertion] = Field(default_factory=list)  # type: ignore[var-annotated]
    extract: list[Extraction] = Field(default_factory=list)  # type: ignore[var-annotated]
    recovery_policy: RecoveryPolicy | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """
        Valida que o ID do step não está vazio.

        ## Para todos entenderem:
        @field_validator é um "decorador" que marca este método
        como validador do campo "id". Pydantic chama automaticamente.

        @classmethod significa que o método pertence à classe,
        não a uma instância específica.

        ## Parâmetros:
            v: Valor do ID a validar

        ## Retorna:
            ID com espaços removidos das extremidades

        ## Erros:
            ValueError: Se o ID for vazio ou contiver apenas espaços
        """
        if not v or not v.strip():
            raise ValueError("O ID do step não pode ser vazio")
        return v.strip()


# =============================================================================
# MODELOS DE METADADOS E CONFIGURAÇÃO
# =============================================================================


class Meta(BaseModel):
    """
    Metadados sobre o plano de testes.

    ## Para todos entenderem:
    Metadados são "dados sobre os dados". Não afetam a execução,
    mas ajudam a identificar e organizar os planos.

    ## Atributos:
        id: UUID único do plano (gerado automaticamente se não fornecido)
            Formato: "550e8400-e29b-41d4-a716-446655440000"

        name: Nome legível do plano de testes
            Exemplo: "Teste de Autenticação"

        description: Descrição detalhada do objetivo do plano
            Exemplo: "Testa fluxos de login, logout e refresh token"

        tags: Lista de tags para categorização
            Exemplo: ["auth", "smoke", "regression"]

        created_at: Timestamp ISO8601 de criação (UTC)
            Formato: "2024-01-15T10:30:00Z"

    ## Exemplo:
        >>> meta = Meta(name="Teste de Login", tags=["auth", "smoke"])
        >>> print(meta.id)  # UUID gerado automaticamente
        >>> print(meta.created_at)  # Timestamp atual
    """

    # default_factory é uma função que gera o valor padrão
    # lambda: ... é uma função anônima inline
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    # Gera timestamp UTC no formato ISO8601
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


class Config(BaseModel):
    """
    Configuração global do plano de testes.

    ## Para todos entenderem:
    Estas configurações se aplicam a TODOS os steps do plano.
    É como "configuração padrão" que pode ser sobrescrita em cada step.

    ## Atributos:
        base_url: URL base para todas as requisições.
            Os paths dos steps são concatenados a esta URL.
            Exemplo: "https://api.example.com" + "/users" = "https://api.example.com/users"

        timeout_ms: Timeout padrão em milissegundos (mínimo 100ms).
            Após esse tempo, a requisição é abortada.

        global_headers: Headers aplicados a TODAS as requisições.
            Útil para headers comuns como Content-Type, API keys, etc.

        variables: Variáveis iniciais disponíveis via ${var}.
            Exemplo: {"env": "staging"} permite usar ${env} nos steps.

    ## Exemplo:
        >>> config = Config(
        ...     base_url="https://api.example.com",
        ...     global_headers={"Authorization": "Bearer ${token}"},
        ...     variables={"env": "staging"}
        ... )
    """

    base_url: str
    # ge=100 significa timeout mínimo de 100ms
    timeout_ms: int = Field(default=5000, ge=100)
    global_headers: dict[str, str] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# MODELO PRINCIPAL - PLAN
# =============================================================================


class Plan(BaseModel):
    """
    Objeto raiz do Plano UTDL - O "documento" completo de testes.

    ## Para todos entenderem:
    Este é o modelo principal! Representa um plano de testes completo
    que pode ser:
    1. Gerado pelo Brain (via LLM)
    2. Validado pelo Pydantic (este módulo)
    3. Executado pelo Runner (Rust)

    ## Estrutura de um Plan:

    ```json
    {
      "spec_version": "0.1",
      "meta": { "id": "...", "name": "...", ... },
      "config": { "base_url": "...", ... },
      "steps": [ {...}, {...}, ... ]
    }
    ```

    ## Validações automáticas:
    - Todos os campos obrigatórios presentes
    - Tipos de dados corretos
    - Dependências existem (step A depende de step B -> B existe)
    - Sem ciclos (A -> B -> C -> A seria inválido)

    ## Atributos:
        spec_version: Versão do schema UTDL (atualmente "0.1")
        meta: Metadados do plano (nome, tags, etc.)
        config: Configuração global (base_url, headers, etc.)
        steps: Lista ordenada de steps a executar

    ## Exemplo:
        >>> plan = Plan(
        ...     meta=Meta(name="Smoke Test"),
        ...     config=Config(base_url="https://api.test.com"),
        ...     steps=[Step(id="health", action="http_request", params={"method": "GET", "path": "/health"})]
        ... )
        >>> json_str = plan.to_json()  # Serializa para JSON
    """

    # Literal["0.1"] significa que APENAS "0.1" é aceito
    spec_version: Literal["0.1"] = "0.1"
    meta: Meta
    config: Config
    steps: list[Step]

    @field_validator("steps")
    @classmethod
    def validate_dependencies(cls, steps: list[Step]) -> list[Step]:
        """
        Garante que todas as referências depends_on apontam para step IDs existentes.

        ## Para todos entenderem:
        Se um step diz "dependo do step X", verificamos se X existe.
        Exemplo de erro: step "get_users" depende de "login", mas "login" não existe.

        ## Parâmetros:
            steps: Lista de steps a validar

        ## Retorna:
            A mesma lista de steps se válida

        ## Erros:
            ValueError: Se um step depende de outro que não existe
        """
        # Cria conjunto com todos os IDs de steps
        # set é mais rápido para busca que list
        step_ids: set[str] = {step.id for step in steps}

        # Verifica cada step
        for step in steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise ValueError(
                        f"Step '{step.id}' depende de step desconhecido '{dep}'"
                    )
        return steps

    @field_validator("steps")
    @classmethod
    def detect_cycles(cls, steps: list[Step]) -> list[Step]:
        """
        Garante que não existem dependências circulares (apenas DAG).

        ## Para todos entenderem:
        DAG = Directed Acyclic Graph (Grafo Direcionado Acíclico)
        Significa que as dependências não podem formar "loops".

        Exemplo de ciclo inválido:
        - step A depende de step B
        - step B depende de step C
        - step C depende de step A
        -> Isso é um ciclo! Nunca terminaria.

        ## Algoritmo usado:
        DFS (Depth-First Search) com pilha de recursão.
        Se durante a busca encontramos um nó que já está na pilha,
        significa que há um ciclo.

        ## Parâmetros:
            steps: Lista de steps a validar

        ## Retorna:
            A mesma lista de steps se não houver ciclos

        ## Erros:
            ValueError: Se detectar dependência circular
        """
        # Constrói grafo: {step_id: [dependências]}
        graph: dict[str, list[str]] = {step.id: step.depends_on for step in steps}

        # Conjuntos para rastrear estado da busca
        visited: set[str] = set()  # Nós já visitados
        rec_stack: set[str] = set()  # Pilha de recursão atual

        def has_cycle(node: str) -> bool:
            """
            Verifica se há ciclo a partir do nó usando DFS.

            ## Para todos entenderem:
            DFS = busca em profundidade. Vai "fundo" antes de "largo".
            A pilha rec_stack guarda o caminho atual.
            Se encontrarmos um nó que já está no caminho, há ciclo.
            """
            visited.add(node)
            rec_stack.add(node)

            # Para cada vizinho (dependência)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    # Se não visitou, visita agora
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Se está na pilha atual, há ciclo!
                    return True

            # Remove da pilha ao sair
            rec_stack.remove(node)
            return False

        # Verifica a partir de cada step
        for step in steps:
            if step.id not in visited:
                if has_cycle(step.id):
                    raise ValueError(
                        f"Dependência circular detectada envolvendo step '{step.id}'"
                    )
        return steps

    def to_json(self) -> str:
        """
        Serializa o plano para string JSON formatada.

        ## Para todos entenderem:
        Serializar = converter objeto Python para texto JSON.
        O JSON gerado pode ser salvo em arquivo ou enviado ao Runner.

        ## Retorna:
            String JSON com indentação de 2 espaços (bonita de ler)
        """
        return self.model_dump_json(indent=2)

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa o plano para dicionário Python.

        ## Para todos entenderem:
        Às vezes queremos o plano como dicionário Python,
        não como string JSON. Esta função faz isso.

        ## Retorna:
            Dicionário com todos os campos do plano
        """
        return self.model_dump()
