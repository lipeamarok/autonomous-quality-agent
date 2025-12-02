"""
Modelos Pydantic para UTDL — Fonte da verdade para validação de planos.

Este módulo define os modelos que espelham o JSON Schema UTDL v0.1 e são usados para:
1. Validar planos gerados por LLM antes de enviar ao Runner
2. Fornecer mensagens de erro claras quando a validação falha
3. Habilitar autocomplete e type checking no codebase do Brain

Os modelos seguem as melhores práticas do Pydantic v2:
- Tipagem explícita com generics modernos (list[], dict[])
- Field validators para validação customizada
- Serialização/deserialização otimizada
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Assertion(BaseModel):
    """
    Define uma regra de validação para a resposta de um step.

    Assertions são usadas para verificar se a resposta de uma requisição
    HTTP atende aos critérios esperados (status code, corpo JSON, headers, etc.).

    Attributes:
        type: Tipo de assertion (status_code, json_body, header, latency)
        operator: Operador de comparação (eq, neq, lt, gt, contains)
        value: Valor esperado para comparação
        path: Caminho JSONPath para json_body ou nome do header (opcional)

    Example:
        >>> assertion = Assertion(type="status_code", operator="eq", value=200)
        >>> assertion = Assertion(type="json_body", path="data.id", operator="eq", value=123)
    """

    type: Literal["status_code", "json_body", "header", "latency"]
    operator: Literal["eq", "neq", "lt", "gt", "contains"]
    value: Any
    path: str | None = None


class Extraction(BaseModel):
    """
    Define como extrair dados de uma resposta para variáveis de contexto.

    Extractions permitem capturar valores de respostas HTTP e armazená-los
    em variáveis que podem ser usadas em steps subsequentes via interpolação ${var}.

    Attributes:
        source: Origem da extração (body para JSON, header para cabeçalhos)
        path: Caminho JSONPath (para body) ou nome do header
        target: Nome da variável de destino no contexto

    Example:
        >>> extraction = Extraction(source="body", path="auth.token", target="token")
        >>> # Após execução, ${token} estará disponível nos próximos steps
    """

    source: Literal["body", "header"]
    path: str
    target: str


class RecoveryPolicy(BaseModel):
    """
    Define o comportamento de retry em caso de falha de um step.

    Recovery policies permitem implementar resiliência em testes,
    especialmente útil para lidar com flaky tests ou instabilidades de rede.

    Attributes:
        strategy: Estratégia de recuperação
            - retry: Tenta novamente até max_attempts
            - fail_fast: Falha imediatamente (padrão)
            - ignore: Ignora a falha e continua
        max_attempts: Número máximo de tentativas (1-10)
        backoff_ms: Tempo inicial de espera entre tentativas em ms
        backoff_factor: Multiplicador exponencial para backoff

    Example:
        >>> policy = RecoveryPolicy(strategy="retry", max_attempts=3, backoff_ms=1000)
        >>> # Tentativas: imediato, 1s, 2s, 4s (com backoff_factor=2.0)
    """

    strategy: Literal["retry", "fail_fast", "ignore"] = "fail_fast"
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_ms: int = Field(default=500, ge=0)
    backoff_factor: float = Field(default=2.0, ge=1.0)


class Step(BaseModel):
    """
    Uma ação atômica única no plano de testes.

    Steps são as unidades básicas de execução do UTDL. Cada step representa
    uma ação (como uma requisição HTTP) com suas assertions e extrações.

    Attributes:
        id: Identificador único do step (usado para dependências)
        action: Tipo de ação (http_request, wait)
        description: Descrição legível do que o step faz
        depends_on: Lista de IDs de steps que devem executar antes
        params: Parâmetros específicos da ação (method, path, body, etc.)
        assertions: Lista de validações a executar na resposta
        extract: Lista de extrações para capturar dados da resposta
        recovery_policy: Política de retry em caso de falha

    Example:
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

        Args:
            v: Valor do ID a validar

        Returns:
            ID com espaços removidos das extremidades

        Raises:
            ValueError: Se o ID for vazio ou contiver apenas espaços
        """
        if not v or not v.strip():
            raise ValueError("O ID do step não pode ser vazio")
        return v.strip()


class Meta(BaseModel):
    """
    Metadados sobre o plano de testes.

    Contém informações descritivas sobre o plano, úteis para
    identificação, organização e rastreabilidade.

    Attributes:
        id: UUID único do plano (gerado automaticamente se não fornecido)
        name: Nome legível do plano de testes
        description: Descrição detalhada do objetivo do plano
        tags: Lista de tags para categorização (ex: ["auth", "smoke", "regression"])
        created_at: Timestamp ISO8601 de criação (UTC)

    Example:
        >>> meta = Meta(name="Teste de Login", tags=["auth", "smoke"])
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


class Config(BaseModel):
    """
    Configuração global do plano de testes.

    Define parâmetros que se aplicam a todos os steps do plano,
    como URL base, timeout padrão, headers globais e variáveis.

    Attributes:
        base_url: URL base para todas as requisições (ex: https://api.example.com)
        timeout_ms: Timeout padrão em milissegundos (mínimo 100ms)
        global_headers: Headers aplicados a todas as requisições
        variables: Variáveis iniciais disponíveis via ${var}

    Example:
        >>> config = Config(
        ...     base_url="https://api.example.com",
        ...     global_headers={"Authorization": "Bearer ${token}"},
        ...     variables={"env": "staging"}
        ... )
    """

    base_url: str
    timeout_ms: int = Field(default=5000, ge=100)
    global_headers: dict[str, str] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    """
    Objeto raiz do Plano UTDL.

    Este é o plano de testes completo que será:
    1. Gerado pelo Brain (via LLM)
    2. Validado pelo Pydantic
    3. Executado pelo Runner (Rust)

    O Plan garante:
    - Validação de schema via Pydantic
    - Detecção de dependências inexistentes entre steps
    - Detecção de ciclos no grafo de dependências (DAG only)

    Attributes:
        spec_version: Versão do schema UTDL (atualmente "0.1")
        meta: Metadados do plano (nome, tags, etc.)
        config: Configuração global (base_url, headers, etc.)
        steps: Lista ordenada de steps a executar

    Example:
        >>> plan = Plan(
        ...     meta=Meta(name="Smoke Test"),
        ...     config=Config(base_url="https://api.test.com"),
        ...     steps=[Step(id="health", action="http_request", params={"method": "GET", "path": "/health"})]
        ... )
        >>> json_str = plan.to_json()  # Serializa para JSON
    """

    spec_version: Literal["0.1"] = "0.1"
    meta: Meta
    config: Config
    steps: list[Step]

    @field_validator("steps")
    @classmethod
    def validate_dependencies(cls, steps: list[Step]) -> list[Step]:
        """
        Garante que todas as referências depends_on apontam para step IDs existentes.

        Args:
            steps: Lista de steps a validar

        Returns:
            A mesma lista de steps se válida

        Raises:
            ValueError: Se um step depende de outro que não existe
        """
        step_ids: set[str] = {step.id for step in steps}
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

        Usa algoritmo de detecção de ciclos via DFS com pilha de recursão.

        Args:
            steps: Lista de steps a validar

        Returns:
            A mesma lista de steps se não houver ciclos

        Raises:
            ValueError: Se detectar dependência circular
        """
        graph: dict[str, list[str]] = {step.id: step.depends_on for step in steps}
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(node: str) -> bool:
            """Verifica se há ciclo a partir do nó usando DFS."""
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

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

        Returns:
            String JSON com indentação de 2 espaços
        """
        return self.model_dump_json(indent=2)

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa o plano para dicionário Python.

        Returns:
            Dicionário com todos os campos do plano
        """
        return self.model_dump()
