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

agente_abertura_conta = create_agent(
    __llm,
    tools=[],
    system_prompt=(
        "Você é um especialista em abertura de conta do banco MDBank. "
        "Ajude o cliente a abrir uma conta e explique os tipos de conta disponíveis que são "
        "contas simples e conta completa."
    )
)

async def run_agent(mensagem: str) -> str:
    resultado = agente_abertura_conta.invoke(
        {"messages": [HumanMessage(content=mensagem)]}
    )
    return resultado["messages"][-1].content
