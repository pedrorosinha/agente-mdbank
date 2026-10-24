import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

__llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3,
    reasoning_format="hidden",
)

client = MultiServerMCPClient(
    {
        "conta": {
            "transport": "http",
            "url": "http://recursos:8000/mcp_gateway",
        }
    }
)

memory = InMemorySaver()

agent = None


async def build_cartao_agent():
    tools = await client.get_tools()

    agent_cartoes = create_agent(
        model=__llm,
        tools=tools,
        system_prompt=(
            "Você é especialista em cartões do MDBank.\n\n"
            "Tipos disponíveis: platinum, gold, silver, mdzao\n\n"
            "================================\n"
            "REGRAS OBRIGATÓRIAS (CRÍTICO)\n"
            "================================\n"
            "1. Você DEVE obrigatoriamente chamar a tool consultar_conta\n"
            "2. Você NÃO pode responder sem verificar no sistema\n"
            "3. Você NÃO pode assumir se o cliente tem conta\n\n"
            "================================\n"
            "FLUXO\n"
            "================================\n"
            "PASSO 1:\n"
            "-> Identificar CPF (usar memória se já tiver)\n"
            "-> Se não tiver CPF, pedir ao cliente\n\n"
            "PASSO 2:\n"
            "-> Chamar consultar_conta\n\n"
            "PASSO 3:\n"
            "-> Se existe = False:\n"
            "   - Informar que não possui conta\n"
            "   - Oferecer abrir conta\n"
            "   - NÃO solicitar cartão\n\n"
            "-> Se existe = True:\n"
            "   - Chamar solicitar_cartao\n\n"
            "================================\n"
            "REGRAS GERAIS\n"
            "================================\n"
            "- Sempre use tools\n"
            "- Nunca invente dados\n"
            "- Use memória para recuperar CPF\n"
            "- Nunca pule etapas\n\n"
            "================================\n"
            "ERROS\n"
            "================================\n"
            "- Use mensagem da tool\n"
            "- Explique claramente\n"
        ),
        checkpointer=memory,
    )

    return agent_cartoes


async def run_agent(mensagem: str, thread_id: str = "1"):
    global agent

    if not agent:
        agent = await build_cartao_agent()

    resultado = await agent.ainvoke(
        {"messages": [HumanMessage(content=mensagem)]},
        {"configurable": {"thread_id": thread_id}},
    )

    return resultado["messages"][-1].content
