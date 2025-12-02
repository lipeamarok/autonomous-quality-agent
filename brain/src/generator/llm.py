"""
Integração com LLM para Geração de UTDL.

Este módulo utiliza o LiteLLM para abstrair o provedor LLM específico
(OpenAI, Claude, Gemini, etc.), permitindo trocar modelos facilmente.

Funcionalidades principais:
- Geração de planos UTDL a partir de requisitos em linguagem natural
- Validação automática via Pydantic
- Loop de autocorreção quando a validação falha
- Extração robusta de JSON de respostas de LLM
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from litellm import completion  # type: ignore[import-untyped]

from ..validator import Plan
from .prompts import ERROR_CORRECTION_PROMPT, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


class UTDLGenerator:
    """
    Gerador de planos de teste UTDL usando LLM.

    Esta classe encapsula toda a lógica de interação com o LLM para gerar
    planos de teste válidos. Inclui um loop de autocorreção que reenvia
    erros de validação ao LLM até obter um plano válido.

    Attributes:
        model: Identificador do modelo LLM (ex: "gpt-4", "claude-3-opus")
        max_correction_attempts: Máximo de tentativas de correção
        temperature: Temperatura para sampling (0.0 = determinístico)

    Example:
        >>> generator = UTDLGenerator(model="gpt-4")
        >>> plan = generator.generate("Testar API de login", "https://api.example.com")
        >>> print(plan.to_json())
    """

    def __init__(
        self,
        model: str = "gpt-4",
        max_correction_attempts: int = 3,
        temperature: float = 0.2,
    ) -> None:
        """
        Inicializa o gerador UTDL.

        Args:
            model: Modelo LLM a usar (compatível com LiteLLM)
            max_correction_attempts: Máximo de tentativas de autocorreção
            temperature: Temperatura para geração (menor = mais determinístico)
        """
        self.model = model
        self.max_correction_attempts = max_correction_attempts
        self.temperature = temperature

    def generate(
        self,
        requirement: str,
        base_url: str = "https://api.example.com",
    ) -> Plan:
        """
        Gera um plano UTDL validado a partir de uma descrição de requisitos.

        O método faz uma chamada inicial ao LLM e, se a validação falhar,
        entra em um loop de autocorreção enviando os erros de volta ao LLM
        até obter um plano válido ou esgotar as tentativas.

        Args:
            requirement: Descrição em linguagem natural do que testar
            base_url: URL base da API sob teste

        Returns:
            Objeto Plan validado e pronto para execução

        Raises:
            ValueError: Se não conseguir gerar um plano válido após max tentativas
        """
        user_prompt = USER_PROMPT_TEMPLATE.format(
            requirement=requirement,
            base_url=base_url,
        )

        # Geração inicial
        raw_json = self._call_llm(SYSTEM_PROMPT, user_prompt)
        last_errors: str | None = None

        # Loop de validação e autocorreção
        for attempt in range(self.max_correction_attempts):
            plan, errors = self._validate_json(raw_json)

            if plan is not None:
                return plan

            last_errors = errors

            # Tenta correção
            print(f"Validação falhou (tentativa {attempt + 1}). Solicitando correção...")
            correction_prompt = ERROR_CORRECTION_PROMPT.format(
                errors=errors,
                original_json=raw_json,
            )
            raw_json = self._call_llm(SYSTEM_PROMPT, correction_prompt)

        raise ValueError(
            f"Falha ao gerar UTDL válido após {self.max_correction_attempts} tentativas. "
            f"Últimos erros: {last_errors}"
        )

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Faz chamada ao LLM e retorna o conteúdo da resposta.

        Args:
            system_prompt: Prompt de sistema com instruções e schema
            user_prompt: Prompt do usuário com requisitos específicos

        Returns:
            String JSON extraída da resposta do LLM
        """
        response: Any = completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
        )
        content: str = str(response.choices[0].message.content or "")
        return self._extract_json(content)

    def _extract_json(self, content: str) -> str:
        """
        Extrai JSON da resposta do LLM.

        Lida com casos onde o LLM envolve o JSON em blocos de código markdown
        ou inclui texto adicional antes/depois do JSON.

        Args:
            content: Texto bruto da resposta do LLM

        Returns:
            String contendo apenas o JSON extraído
        """
        # Tenta encontrar JSON em blocos de código
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            return json_match.group(1).strip()

        # Tenta encontrar JSON bruto (começa com {)
        json_start = content.find("{")
        if json_start != -1:
            # Encontra a chave de fechamento correspondente
            depth = 0
            for i, char in enumerate(content[json_start:]):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return content[json_start : json_start + i + 1]

        return content.strip()

    def _validate_json(self, raw_json: str) -> tuple[Plan | None, str | None]:
        """
        Valida string JSON contra o schema UTDL usando Pydantic.

        Args:
            raw_json: String JSON a validar

        Returns:
            Tupla (Plan, None) se válido, ou (None, string_de_erros) se inválido
        """
        try:
            data = json.loads(raw_json)
            plan = Plan.model_validate(data)
            return plan, None
        except json.JSONDecodeError as e:
            return None, f"JSON inválido: {e}"
        except ValidationError as e:
            error_messages: list[str] = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                error_messages.append(f"{loc}: {error['msg']}")
            return None, "\n".join(error_messages)


def generate_utdl(
    requirement: str,
    base_url: str = "https://api.example.com",
    model: str = "gpt-4",
) -> Plan:
    """
    Função de conveniência para gerar um plano UTDL.

    Esta é uma interface simplificada para o UTDLGenerator, útil para
    casos de uso simples onde não é necessário configurar o gerador.

    Args:
        requirement: Descrição em linguagem natural do que testar
        base_url: URL base da API sob teste
        model: Modelo LLM a usar (padrão: gpt-4)

    Returns:
        Objeto Plan validado e pronto para execução

    Example:
        >>> plan = generate_utdl(
        ...     requirement="Testar o endpoint de login com credenciais válidas e inválidas",
        ...     base_url="https://api.meuapp.com"
        ... )
    """
    generator = UTDLGenerator(model=model)
    return generator.generate(requirement, base_url)
