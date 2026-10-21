
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os

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
        "Você é um especialista em cartão de crédito do banco MDBank. "
        "Ajude o cliente com dúvidas, solicitação e limites."
    )
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

async def classificar_pergunta(pergunta: str) -> str:
    prompt = f"""
    Classifique a intenção do usuário.

    Possíveis agentes:
    cartao_credito
    abrir_conta

    Pergunta: {pergunta}

    Responda apenas com o nome do agente.
    """

    resposta = await __llm.ainvoke(prompt)
    return str(resposta.content).strip().lower()


async def executar_supervisor(texto_usuario: str) -> str:
    agente = await classificar_pergunta(texto_usuario)

    if agente == "cartao_credito":
        resultado = await agente_cartao_credito.ainvoke(
            {"messages": [HumanMessage(content=texto_usuario)]}
        )

    elif agente == "abrir_conta":
        resultado = await agente_abertura_conta.ainvoke(
            {"messages": [HumanMessage(content=texto_usuario)]}
        )

    else:
        return (
            "Não consegui entender a sua solicitação. "
            "Por favor, reformule a pergunta."
        )

    mensagem_ia = resultado["messages"][-1]

    return str(mensagem_ia.content)
