# Códigos de Erro do Runner

Este documento descreve todos os códigos de erro estruturados do Runner.
Os códigos permitem automação, pesquisa e internacionalização.

## Formato

Todos os códigos seguem o padrão `E{categoria}{número}`:
- **E** = Prefixo de erro
- **{categoria}** = Dígito 1-5 indicando categoria
- **{número}** = Três dígitos identificando erro específico

## Categorias

| Faixa  | Categoria        | Descrição                        |
|--------|------------------|----------------------------------|
| E1xxx  | Validação        | Erro no arquivo de teste         |
| E2xxx  | HTTP             | Erro na requisição HTTP          |
| E3xxx  | Assertion        | Teste não passou na validação    |
| E4xxx  | Configuração     | Problema de setup/ambiente       |
| E5xxx  | Interno          | Bug no próprio Runner            |

---

## E1xxx - Validação

Erros que acontecem antes de executar qualquer coisa.
O problema está no arquivo de teste.

| Código | Nome                    | Descrição                                          |
|--------|-------------------------|----------------------------------------------------|
| E1001  | EMPTY_PLAN              | Plano não tem nenhum step definido                 |
| E1002  | UNSUPPORTED_SPEC_VERSION| spec_version não é suportada (deve ser "0.1")      |
| E1003  | UNKNOWN_ACTION          | Action não é reconhecida (http_request/wait/sleep) |
| E1004  | MISSING_PARAM           | Parâmetro obrigatório ausente (method, path, etc)  |
| E1005  | UNKNOWN_DEPENDENCY      | depends_on referencia step inexistente             |
| E1006  | CIRCULAR_DEPENDENCY     | Dependência circular detectada (A→B→A)             |
| E1007  | INVALID_HTTP_METHOD     | Método HTTP inválido (não é GET/POST/etc)          |
| E1008  | EMPTY_STEP_ID           | ID do step está vazio ou só espaços                |
| E1009  | INVALID_PLAN_FORMAT     | Arquivo JSON/YAML com sintaxe inválida             |
| E1010  | MAX_STEPS_EXCEEDED      | Plano excede limite de steps configurado           |
| E1011  | MAX_RETRIES_EXCEEDED    | Soma de retries excede limite configurado          |
| E1012  | EXECUTION_TIMEOUT       | Execução do plano excedeu tempo limite             |

### Como resolver E1xxx

1. **E1001**: Adicione pelo menos um step ao plano
2. **E1002**: Use `spec_version: "0.1"` no plano
3. **E1003**: Use actions válidas: `http_request`, `wait`, `sleep`
4. **E1004**: Verifique os parâmetros obrigatórios da action
5. **E1005**: Verifique se o step referenciado em `depends_on` existe
6. **E1006**: Reorganize as dependências para eliminar ciclos
7. **E1007**: Use métodos válidos: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
8. **E1008**: Preencha o campo `id` de cada step
9. **E1009**: Valide o JSON/YAML do plano
10. **E1010/E1011**: Reduza steps ou aumente limites via env vars
11. **E1012**: Otimize steps ou aumente timeout via `RUNNER_MAX_EXECUTION_SECS`

---

## E2xxx - Execução HTTP

Erros que acontecem ao fazer requisições HTTP.
O problema pode ser na rede, servidor, ou configuração.

| Código | Nome               | Descrição                              |
|--------|--------------------|----------------------------------------|
| E2001  | HTTP_TIMEOUT       | Servidor não respondeu no tempo limite |
| E2002  | HTTP_CONNECTION_ERROR | Não conseguiu conectar (DNS/rede)    |
| E2003  | HTTP_ERROR_STATUS  | Servidor retornou erro (4xx/5xx)       |
| E2004  | HTTP_INVALID_JSON  | Resposta não é JSON válido             |
| E2005  | HTTP_TLS_ERROR     | Problema com certificado HTTPS         |

### Como resolver E2xxx

1. **E2001**: Aumente timeout ou verifique se servidor está lento
2. **E2002**: Verifique DNS, firewall, ou se servidor está acessível
3. **E2003**: Verifique credenciais, payload, ou estado do servidor
4. **E2004**: Verifique se endpoint retorna JSON ou se há encoding correto
5. **E2005**: Verifique certificado SSL ou desabilite validação (dev only)

---

## E3xxx - Assertions

Erros quando a resposta não é o esperado.
O teste "passou tecnicamente" mas a validação falhou.

| Código | Nome                   | Descrição                              |
|--------|------------------------|----------------------------------------|
| E3001  | ASSERTION_STATUS_CODE  | Status HTTP diferente do esperado      |
| E3002  | ASSERTION_JSON_BODY    | Valor no JSON diferente do esperado    |
| E3003  | ASSERTION_HEADER       | Header HTTP diferente do esperado      |
| E3004  | ASSERTION_LATENCY      | Requisição demorou mais que o limite   |
| E3005  | ASSERTION_PATH_NOT_FOUND | Caminho JSON não existe na resposta  |

### Como resolver E3xxx

1. **E3001**: Verifique se status esperado está correto
2. **E3002**: Verifique o path e valor esperado no JSON
3. **E3003**: Verifique nome e valor do header
4. **E3004**: Otimize endpoint ou ajuste limite de latência
5. **E3005**: Verifique se o path JSON existe na resposta

---

## E4xxx - Configuração/Ambiente

Erros de setup, variáveis de ambiente, arquivos.

| Código | Nome               | Descrição                              |
|--------|--------------------|----------------------------------------|
| E4001  | ENV_VAR_NOT_FOUND  | Variável {{env:VAR}} não está definida |
| E4002  | CONTEXT_VAR_NOT_FOUND | Variável de contexto não foi extraída |
| E4003  | PLAN_FILE_NOT_FOUND | Arquivo de plano não encontrado       |
| E4004  | FILE_PERMISSION_ERROR | Sem permissão para ler arquivo       |

### Como resolver E4xxx

1. **E4001**: Defina a variável de ambiente antes de executar
2. **E4002**: Garanta que o step que extrai a variável execute antes
3. **E4003**: Verifique o caminho do arquivo de plano
4. **E4004**: Verifique permissões do arquivo

---

## E5xxx - Erros Internos

Bugs no próprio Runner. Se você ver esses, reporte!

| Código | Nome                | Descrição                              |
|--------|---------------------|----------------------------------------|
| E5001  | INTERNAL_ERROR      | Erro interno inesperado                |
| E5002  | NO_EXECUTOR_FOR_ACTION | Action válida sem executor (bug)    |
| E5003  | SERIALIZATION_ERROR | Erro ao converter dados internamente   |

### Como resolver E5xxx

Estes são bugs no Runner. Por favor:
1. Anote o código de erro e a mensagem completa
2. Guarde o plano UTDL que causou o erro
3. Abra uma issue no repositório com essas informações

---

## Uso Programático

### No Runner (Rust)

```rust
use crate::errors::{ErrorCode, StructuredError};

// Criar erro estruturado
let error = StructuredError::new(
    ErrorCode::ASSERTION_STATUS_CODE,
    "Status code não corresponde",
)
.with_step_id("login_step");

println!("{}", error); // [E3001] Status code não corresponde (step: login_step)
```

### No Brain (Python)

```python
# Interpretar erro do report
def handle_runner_error(error: dict):
    code = error.get("code", "")
    category = int(code[1]) if len(code) == 5 else 0
    
    if category == 1:
        # Erro de validação - problema no UTDL gerado
        regenerate_plan()
    elif category == 2:
        # Erro HTTP - problema de rede/servidor
        retry_with_backoff()
    elif category == 3:
        # Assertion falhou - comportamento inesperado da API
        report_test_failure()
    elif category == 4:
        # Configuração - problema de ambiente
        check_environment()
    elif category == 5:
        # Bug no Runner
        report_bug()
```

---

## Variáveis de Ambiente para Limites

| Variável                   | Padrão | Descrição                          |
|----------------------------|--------|------------------------------------|
| RUNNER_MAX_STEPS           | 100    | Máximo de steps por plano          |
| RUNNER_MAX_PARALLEL        | 10     | Máximo de steps em paralelo        |
| RUNNER_MAX_RETRIES         | 50     | Máximo de retries no plano todo    |
| RUNNER_MAX_EXECUTION_SECS  | 300    | Timeout total de execução (5 min)  |
| RUNNER_MAX_STEP_TIMEOUT    | 30     | Timeout por step individual        |
