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
    temperature=0.7,
    reasoning_format="hidden",
)


class RouterOutput(BaseModel):
    agents: list[str] = Field(
        description="Lista de agentes que devem responder a pergunta"
    )


parser = JsonOutputParser(pydantic_object=RouterOutput)


def classifique_intencao_usuario(query: str) -> list[dict]:
    """
    Classifica a pergunta e retorna quais agentes devem ser chamados.
    """

    prompt = f"""
Você é um roteador de agentes de um banco.

Agentes disponíveis:

cartao_credito
abrir_conta

Uma pergunta pode exigir mais de um agente.

Responda apenas em JSON.

Pergunta:
{query}

{parser.get_format_instructions()}
"""

    resposta = __llm.invoke(prompt)

    resultado = parser.parse(str(resposta.content))

    agentes = resultado["agents"]

    logger.info(f"Agentes selecionados: {agentes}")

    return [{"query": query, "agent": agente} for agente in agentes]
