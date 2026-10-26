import logging
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

load_dotenv()

__llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3,
    reasoning_format="hidden",
)


class RouterOutput(BaseModel):
    agents: list[str] = Field(
        description="Lista de agentes que devem responder à pergunta"
    )


parser = JsonOutputParser(pydantic_object=RouterOutput)

AGENTES_VALIDOS = {"cartao_credito", "abrir_conta"}


def classifique_intencao_usuario(query: str) -> list[dict]:
    """
    Classifica a pergunta e retorna quais agentes devem ser chamados.
    """

    prompt = f"""
Você é o roteador de agentes do banco MDBank.

Sua responsabilidade é escolher os agentes adequados para
atender à solicitação do usuário.

AGENTES DISPONÍVEIS:

1. cartao_credito

Responsabilidades:
- Solicitar cartões de crédito.
- Consultar cartões.
- Consultar limites.
- Aumentar limites.
- Explicar tipos de cartões.

2. abrir_conta

Responsabilidades:
- Abrir contas bancárias.
- Consultar contas.
- Explicar tipos de contas.
- Realizar pesquisas na internet usando DuckDuckGo.
- Buscar informações sobre assuntos externos ao banco.

REGRAS:

- Uma pergunta pode exigir mais de um agente.
- Se o usuário solicitar uma pesquisa na internet,
  selecione obrigatoriamente "abrir_conta".
- Se a pergunta envolver abertura de conta,
  selecione "abrir_conta".
- Se envolver cartões de crédito,
  selecione "cartao_credito".
- Não invente nomes de agentes.
- Não retorne agentes duplicados.
- Se não houver correspondência clara,
  selecione "abrir_conta" como agente padrão.

EXEMPLOS:

Pergunta: Quero abrir uma conta
Resposta: {{"agents": ["abrir_conta"]}}

Pergunta: Quero solicitar um cartão platinum
Resposta: {{"agents": ["cartao_credito"]}}

Pergunta: Quero buscar sobre Backend for Agents
Resposta: {{"agents": ["abrir_conta"]}}

Pergunta: Quero abrir uma conta e solicitar um cartão
Resposta: {{"agents": ["abrir_conta", "cartao_credito"]}}

Pergunta do usuário:
{query}

{parser.get_format_instructions()}
"""

    resposta = __llm.invoke(prompt)

    resultado = parser.parse(str(resposta.content))

    agentes = resultado.get("agents", [])

    agentes = [agente for agente in dict.fromkeys(agentes) if agente in AGENTES_VALIDOS]

    if not agentes:
        logger.warning("Nenhum agente identificado. Utilizando abrir_conta.")
        agentes = ["abrir_conta"]

    logger.info(f"Agentes selecionados: {agentes}")

    return [{"query": query, "agent": agente} for agente in agentes]
