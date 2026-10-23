import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

load_dotenv()

__llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7,
    reasoning_format="hidden"
)

agente_cartao_credito = create_agent(
    __llm,
    tools=[],
    system_prompt=(
        "Você é um especialista em cartão de crédito do banco MDBank e sempre avise que você é um agente de ia no final da resposta. "
        "Os cartões que existem no MDBank são: [platinum, gold, silver, md_card e cartao_bronze]."
        "Ajude o cliente com dúvidas, solicitações e limites."
    )
)

async def run_agent(mensagem: str) -> str:
    resultado = agente_cartao_credito.invoke(
        {"messages": [HumanMessage(content=mensagem)]}
    )
    return resultado["messages"][-1].content
