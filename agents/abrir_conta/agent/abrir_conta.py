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

SMITHERY_URL = "https://duckduckgo-mcp-server--nickclyde.run.tools"

client = MultiServerMCPClient(
    {
        "conta": {
            "transport": "http",
            "url": "http://recursos:8000/mcp_gateway",
        },
        "duckduckgo": {
            "transport": "http",
            "url": f"{SMITHERY_URL}/?api_key={os.getenv('SMITHERY_API_KEY')}",
        }
    }
)

memory = InMemorySaver()


async def build_agent():
    tools = await client.get_tools()

    agent = create_agent(
        model=__llm,
        tools=tools,
        system_prompt=(
            "Você é um assistente do MDBank.\n\n"
            "Você deve SEMPRE usar tools para decisões reais.\n\n"
            "Fluxo obrigatório:\n"
            "1. Se cliente pedir cartão:\n"
            "   - Use consultar_conta\n"
            "   - Se não existir:\n"
            "       → informe o problema\n"
            "       → ofereça abrir conta\n\n"
            "2. Para abrir conta:\n"
            "   - Use gerar_prompt_abertura\n"
            "   - Depois criar_ou_buscar_conta\n\n"
            "3. Após conta criada:\n"
            "   - Use solicitar_cartao\n\n"
            "Regras:\n"
            "- Nunca invente dados\n"
            "- Sempre use tools\n"
            "- Use mensagens claras para o cliente\n"
            "- Quando o cliente solicitar uma pesquisa na internet, "
            "use a ferramenta search do DuckDuckGo.\n"
            "- Utilize fetch_content quando precisar consultar detalhes de uma página.\n"
            "- Não utilize resultados de buscas públicas para confirmar identidade "
            "ou validar dados bancários de clientes.\n"
        ),
        checkpointer=memory,
    )

    return agent


async def run_agent(mensagem: str, thread_id: str = "1"):
    agent = await build_agent()

    resultado = await agent.ainvoke(
        {"messages": [HumanMessage(content=mensagem)]},
        {"configurable": {"thread_id": thread_id}},
    )

    return resultado["messages"][-1].content
