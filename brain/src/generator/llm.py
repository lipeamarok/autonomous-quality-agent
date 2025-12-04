"""
================================================================================
INTEGRAÇÃO COM LLM PARA GERAÇÃO DE UTDL
================================================================================

Este módulo é o "cérebro" do Brain - ele se comunica com modelos de linguagem
(como GPT-5.1, Grok, etc.) para gerar planos de teste automaticamente.

## Para todos entenderem:

Imagine que você tem um assistente muito inteligente que entende linguagem
natural. Você diz "quero testar a API de login" e ele gera automaticamente
todas as requisições HTTP, validações e dependências necessárias.

Este módulo:
1. Recebe uma descrição em português/inglês do que testar
2. Envia para um modelo de IA (LLM = Large Language Model)
3. Recebe um JSON com o plano de testes
4. Valida se o JSON está correto
5. Se não estiver, pede para a IA corrigir (até 3 tentativas)

## Provedores suportados:

| Provedor | Modelo              | Uso                    |
|----------|---------------------|------------------------|
| OpenAI   | gpt-5.1             | Padrão (SOTA)          |
| xAI      | grok-4-1-fast       | Fallback               |

## Funcionalidades principais:
- Geração de planos UTDL a partir de requisitos em linguagem natural
- Validação automática via Pydantic (biblioteca de validação Python)
- Loop de autocorreção quando a validação falha
- Extração robusta de JSON de respostas de LLM
- **Fallback automático** entre provedores quando um falha

## Exemplo de uso:
    >>> generator = UTDLGenerator()  # Usa GPT-5.1 por padrão
    >>> plan = generator.generate("Testar API de login", "https://api.example.com")
    >>> print(plan.to_json())
"""

# =============================================================================
# IMPORTS - Bibliotecas necessárias
# =============================================================================

# __future__.annotations permite usar tipos mais modernos em Python 3.9+
from __future__ import annotations

# json: Para parsear e serializar JSON (formato de dados)
import json

# re: Expressões regulares para buscar padrões em texto
import re

# typing: Anotações de tipo para melhor documentação e checagem
# (removido Any pois não é mais usado)

# ValidationError: Exceção lançada quando dados não passam na validação
from pydantic import ValidationError

# Providers: Sistema de provedores LLM com fallback
from .providers import LLMProvider, ProviderName

# Plan: Nosso modelo Pydantic que define a estrutura do plano UTDL
from ..validator import Plan

# Prompts: Os templates de texto que enviamos ao LLM
from .prompts import ERROR_CORRECTION_PROMPT, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

# Cache: Sistema de cache para evitar chamadas repetidas ao LLM
from ..cache import PlanCache


# =============================================================================
# CLASSE PRINCIPAL - UTDLGenerator
# =============================================================================


class UTDLGenerator:
    """
    Gerador de planos de teste UTDL usando LLM.

    Esta classe encapsula toda a lógica de interação com o LLM para gerar
    planos de teste válidos. Inclui um loop de autocorreção que reenvia
    erros de validação ao LLM até obter um plano válido.

    ## Para todos entenderem:

    Pense nesta classe como um "tradutor" entre você e a IA:
    - Você diz o que quer testar em português
    - A classe formata isso de um jeito que a IA entende
    - A IA responde com um JSON
    - A classe valida se o JSON está correto
    - Se não estiver, a classe pede correção automaticamente

    ## Cache de Planos:

    Para economizar custos e garantir determinismo, o gerador cacheia
    resultados baseado no hash da requisição (requirements + base_url +
    provider + model). Se o mesmo input for passado novamente, retorna
    o plano cacheado sem chamar o LLM.

    ## Provedores com Fallback:

    O gerador tenta primeiro o provedor primário (OpenAI GPT-5.1).
    Se falhar (rate limit, timeout, etc.), usa automaticamente o fallback (Grok).

    ## Atributos:
        provider: Provedor LLM com suporte a fallback
        max_correction_attempts: Máximo de tentativas de correção
        verbose: Se True, loga detalhes das chamadas
        cache: Cache de planos para evitar regeneração

    ## Exemplo:
        >>> generator = UTDLGenerator()  # Usa GPT-5.1 por padrão
        >>> plan = generator.generate("Testar API de login", "https://api.example.com")
        >>> print(plan.to_json())

        >>> # Segunda chamada com mesmo input: retorna do cache!
        >>> plan2 = generator.generate("Testar API de login", "https://api.example.com")
    """

    def __init__(
        self,
        provider: ProviderName | str | None = None,
        max_correction_attempts: int = 3,
        temperature: float = 0.2,
        verbose: bool = False,
        cache_enabled: bool = True,
        cache: PlanCache | None = None,
    ) -> None:
        """
        Inicializa o gerador UTDL.

        ## Para todos entenderem:
        Este é o "construtor" da classe. É chamado quando você cria
        um novo gerador: `generator = UTDLGenerator()`

        ## Parâmetros:
            provider: Provedor LLM a usar. Opções:
                - None: Usa OpenAI GPT-5.1 (padrão)
                - "openai": OpenAI GPT-5.1
                - "xai": xAI Grok
            max_correction_attempts: Quantas vezes tentar corrigir erros
            temperature: Quão "criativa" a IA deve ser (0.0-2.0)
            verbose: Se True, mostra logs detalhados
            cache_enabled: Se True, usa cache (default: True)
            cache: Instância de PlanCache (None = usa default)
        """
        # Converte string para ProviderName se necessário
        if provider is None:
            primary = ProviderName.OPENAI
        elif isinstance(provider, ProviderName):
            primary = provider
        else:
            primary = ProviderName(provider.lower())

        # Cria o provedor com fallback
        self._provider = LLMProvider(
            primary=primary,
            temperature=temperature,
            verbose=verbose,
        )

        self.max_correction_attempts = max_correction_attempts
        self.verbose = verbose
        self._last_provider_used: ProviderName | None = None

        # Configura cache
        self._cache_enabled = cache_enabled
        if cache is not None:
            self._cache = cache
        elif cache_enabled:
            # Usa cache global por padrão com TTL de 30 dias
            self._cache = PlanCache.global_cache(
                enabled=True,
                ttl_days=30,
                compress=True,
            )
        else:
            self._cache = PlanCache(enabled=False)

        # Guarda info do provider para o hash do cache
        self._primary_provider = primary

    def generate(
        self,
        requirement: str,
        base_url: str = "https://api.example.com",
        skip_cache: bool = False,
    ) -> Plan:
        """
        Gera um plano UTDL validado a partir de uma descrição de requisitos.

        ## Para todos entenderem:
        Esta é a função principal! Você passa uma descrição do que quer
        testar e ela retorna um plano de testes completo e validado.

        ## Cache de Planos:

        Por padrão, o gerador verifica se já existe um plano cacheado
        para o mesmo input (requirements + base_url + provider + model).
        Se existir e não estiver expirado, retorna do cache sem chamar
        o LLM. Use `skip_cache=True` para forçar nova geração.

        ## Como funciona internamente:
        1. Verifica se existe plano no cache
        2. Se sim, retorna do cache (rápido e grátis!)
        3. Se não, formata o prompt com os requisitos do usuário
        4. Envia para o LLM e recebe JSON bruto
        5. Tenta validar o JSON
        6. Se falhar, entra no loop de correção:
           - Envia os erros de volta para o LLM
           - LLM corrige e retorna novo JSON
           - Repete até validar ou esgotar tentativas
        7. Armazena plano válido no cache

        ## Parâmetros:
            requirement: Descrição em linguagem natural do que testar
                Exemplo: "Testar o fluxo de login com email e senha"
            base_url: URL base da API sob teste
                Exemplo: "https://api.meusite.com"
            skip_cache: Se True, ignora cache e força nova geração

        ## Retorna:
            Objeto Plan validado e pronto para execução pelo Runner

        ## Erros possíveis:
            ValueError: Se não conseguir gerar um plano válido após
                        todas as tentativas de correção
        """
        provider_name = self._primary_provider.value
        model_name = self._provider.primary_model

        # =====================================================================
        # PASSO 1: Verificar cache
        # =====================================================================

        if self._cache_enabled and not skip_cache:
            cached_plan = self._cache.get(
                requirements=requirement,
                base_url=base_url,
                provider=provider_name,
                model=model_name,
            )

            if cached_plan is not None:
                if self.verbose:
                    print(f"[Cache HIT] Retornando plano do cache")
                # Converte dict para Plan
                return Plan.model_validate(cached_plan)

        # =====================================================================
        # PASSO 2: Gerar via LLM
        # =====================================================================

        # Formata o prompt do usuário usando o template
        # .format() substitui {requirement} e {base_url} pelos valores reais
        user_prompt = USER_PROMPT_TEMPLATE.format(
            requirement=requirement,
            base_url=base_url,
        )

        # Faz a primeira chamada ao LLM
        # raw_json é a string JSON retornada pelo LLM
        raw_json = self._call_llm(SYSTEM_PROMPT, user_prompt)

        # Variável para guardar os últimos erros (para mensagem final)
        last_errors: str | None = None

        # Loop de validação e autocorreção
        # range(3) = [0, 1, 2] = 3 tentativas
        for attempt in range(self.max_correction_attempts):
            # Tenta validar o JSON
            # Retorna (Plan, None) se válido ou (None, "erros") se inválido
            plan, errors = self._validate_json(raw_json)

            # Se validou com sucesso, armazena no cache e retorna!
            if plan is not None:
                # Armazena no cache para próximas chamadas
                if self._cache_enabled:
                    self._cache.store(
                        requirements=requirement,
                        base_url=base_url,
                        plan=plan.model_dump(mode="json"),
                        provider=provider_name,
                        model=model_name,
                    )
                    if self.verbose:
                        print(f"[Cache STORE] Plano armazenado no cache")

                return plan

            # Guarda os erros para possível mensagem final
            last_errors = errors

            # Informa ao usuário que estamos tentando corrigir
            print(f"Validação falhou (tentativa {attempt + 1}). Solicitando correção...")

            # Prepara prompt de correção com os erros encontrados
            correction_prompt = ERROR_CORRECTION_PROMPT.format(
                errors=errors,
                original_json=raw_json,
            )

            # Chama o LLM novamente pedindo correção
            raw_json = self._call_llm(SYSTEM_PROMPT, correction_prompt)

        # Se chegou aqui, esgotou todas as tentativas sem sucesso
        raise ValueError(
            f"Falha ao gerar UTDL válido após {self.max_correction_attempts} tentativas. "
            f"Últimos erros: {last_errors}"
        )

    def invalidate_cache(
        self,
        requirement: str,
        base_url: str,
    ) -> bool:
        """
        Remove plano específico do cache (invalidação manual).

        Útil quando você sabe que o plano cacheado está desatualizado
        e quer forçar regeneração.

        ## Parâmetros:
            requirement: Descrição usada na geração original
            base_url: URL base usada na geração original

        ## Retorna:
            True se entry foi removida, False se não existia
        """
        if not self._cache_enabled:
            return False

        return self._cache.invalidate(
            requirements=requirement,
            base_url=base_url,
            provider=self._primary_provider.value,
            model=self._provider.primary_model,
        )

    def clear_cache(self) -> int:
        """
        Limpa todo o cache de planos.

        ## Retorna:
            Número de entries removidas
        """
        if not self._cache_enabled:
            return 0

        return self._cache.clear()

    def cache_stats(self) -> dict:
        """
        Retorna estatísticas do cache.

        ## Retorna:
            Dict com enabled, entries, expired_entries, size_bytes, etc.
        """
        stats = self._cache.stats()
        return {
            "enabled": stats.enabled,
            "entries": stats.entries,
            "expired_entries": stats.expired_entries,
            "size_bytes": stats.size_bytes,
            "compressed_entries": stats.compressed_entries,
            "cache_dir": stats.cache_dir,
        }

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Faz chamada ao LLM e retorna o conteúdo da resposta.

        ## Para todos entenderem:
        Esta função é quem realmente "conversa" com a IA.
        O underscore no início (_call_llm) indica que é uma função
        "privada" - só deve ser usada internamente pela classe.

        ## Fallback automático:
        Se o provedor primário falhar, automaticamente tenta o fallback.
        Isso garante maior disponibilidade do sistema.

        ## Parâmetros:
            system_prompt: Instruções gerais para a IA (quem ela é,
                          o que deve fazer, o schema do JSON)
            user_prompt: O pedido específico do usuário

        ## Retorna:
            String JSON extraída da resposta do LLM
        """
        # Chama o provedor com fallback automático
        content, provider_used = self._provider.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Guarda qual provedor foi usado (útil para logs/debug)
        self._last_provider_used = provider_used

        # Extrai e retorna apenas o JSON (remove markdown, texto extra, etc.)
        return self._extract_json(content)

    def _extract_json(self, content: str) -> str:
        """
        Extrai JSON da resposta do LLM.

        ## Para todos entenderem:
        Às vezes o LLM retorna o JSON "embrulhado" em coisas extras:
        - Blocos de código markdown: ```json ... ```
        - Texto antes: "Aqui está o plano: {...}"
        - Texto depois: "{...} Espero que ajude!"

        Esta função remove tudo isso e retorna só o JSON limpo.

        ## Técnica usada:
        1. Primeiro, tenta encontrar blocos de código markdown
        2. Se não encontrar, procura por { e } correspondentes
        3. Conta os colchetes para achar o par correto

        ## Parâmetros:
            content: Texto bruto da resposta do LLM

        ## Retorna:
            String contendo apenas o JSON extraído
        """
        # Tenta encontrar JSON em blocos de código markdown
        # Regex: ```json ... ``` ou ``` ... ```
        # [\s\S]*? significa "qualquer caractere, incluindo newlines, não-guloso"
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            # .group(1) retorna o conteúdo capturado pelo primeiro ()
            return json_match.group(1).strip()

        # Se não achou bloco de código, procura JSON bruto
        # Encontra a primeira chave de abertura
        json_start = content.find("{")
        if json_start != -1:
            # Usa contador de profundidade para achar a chave de fechamento correspondente
            # Isso é necessário porque o JSON pode ter objetos aninhados
            depth = 0
            for i, char in enumerate(content[json_start:]):
                if char == "{":
                    depth += 1  # Encontrou abertura, aumenta profundidade
                elif char == "}":
                    depth -= 1  # Encontrou fechamento, diminui profundidade
                    if depth == 0:
                        # Chegou na profundidade 0 = achou o par correspondente
                        return content[json_start : json_start + i + 1]

        # Se nada funcionou, retorna o conteúdo limpo
        return content.strip()

    def _validate_json(self, raw_json: str) -> tuple[Plan | None, str | None]:
        """
        Valida string JSON contra o schema UTDL usando Pydantic.

        ## Para todos entenderem:
        Esta função verifica se o JSON gerado pelo LLM está correto:
        1. O JSON é válido sintaticamente? (vírgulas, aspas, etc.)
        2. O JSON segue o schema UTDL? (tem os campos certos?)

        ## Tipo de retorno:
        - tuple[Plan | None, str | None]
        - Isso significa: retorna uma tupla de dois valores
        - (Plan, None) se válido: retorna o plano e nenhum erro
        - (None, "erros") se inválido: retorna nenhum plano e os erros

        ## Parâmetros:
            raw_json: String JSON a validar

        ## Retorna:
            Tupla (Plan, None) se válido, ou (None, string_de_erros) se inválido
        """
        try:
            # Primeiro, parseia o JSON para um dicionário Python
            # json.loads = JSON string -> Python dict
            data = json.loads(raw_json)

            # Depois, valida contra o modelo Pydantic
            # model_validate verifica todos os campos e tipos
            plan = Plan.model_validate(data)

            # Se chegou aqui, tudo certo!
            return plan, None

        except json.JSONDecodeError as e:
            # JSON mal formado (faltando vírgula, aspas erradas, etc.)
            return None, f"JSON inválido: {e}"

        except ValidationError as e:
            # JSON válido, mas não segue o schema UTDL
            # Formata os erros de forma legível
            error_messages: list[str] = []
            for error in e.errors():
                # error["loc"] é o caminho do campo com erro
                # Ex: ("steps", 0, "id") -> "steps.0.id"
                loc = ".".join(str(x) for x in error["loc"])
                error_messages.append(f"{loc}: {error['msg']}")
            return None, "\n".join(error_messages)


def generate_utdl(
    requirement: str,
    base_url: str = "https://api.example.com",
    provider: str | None = None,
    verbose: bool = False,
) -> Plan:
    """
    Função de conveniência para gerar um plano UTDL.

    Esta é uma interface simplificada para o UTDLGenerator, útil para
    casos de uso simples onde não é necessário configurar o gerador.

    ## Provedores:

    - None ou "openai": Usa GPT-5.1 (padrão)
    - "xai": Usa Grok como primário

    Args:
        requirement: Descrição em linguagem natural do que testar
        base_url: URL base da API sob teste
        provider: Provedor LLM a usar (padrão: OpenAI GPT-5.1)
        verbose: Se True, mostra logs detalhados

    Returns:
        Objeto Plan validado e pronto para execução

    Example:
        >>> plan = generate_utdl(
        ...     requirement="Testar o endpoint de login com credenciais válidas e inválidas",
        ...     base_url="https://api.meuapp.com"
        ... )
    """
    generator = UTDLGenerator(provider=provider, verbose=verbose)
    return generator.generate(requirement, base_url)
