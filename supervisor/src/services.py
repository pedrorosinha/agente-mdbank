import logging
import uuid
from operator import add
from typing import Annotated, TypedDict

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from src.agents import classifique_intencao_usuario

logger = logging.getLogger(__name__)

HTTPX_CLIENT = httpx.AsyncClient(timeout=30)

AGENTS = {
    "cartao_credito": "http://cartao_credito_agent:8000",
    "abrir_conta": "http://abrir_conta_agent:8000",
}

CLIENT_CACHE = {}


class State(TypedDict):
    query: str
    responses: Annotated[list[str], add]


async def request_agent(message: str, agent_url: str) -> str:
    if agent_url not in CLIENT_CACHE:
        logger.info("Descobrindo AgentCard em %s", agent_url)

        resolver = A2ACardResolver(
            httpx_client=HTTPX_CLIENT,
            base_url=agent_url,
        )

        agent_card = await resolver.get_agent_card()
        logger.info("Agent encontrado: %s", agent_card.name)

        config = ClientConfig(
            httpx_client=HTTPX_CLIENT,
            streaming=False,
        )

        factory = ClientFactory(config)
        CLIENT_CACHE[agent_url] = factory.create(agent_card)

    client = CLIENT_CACHE[agent_url]

    msg = Message(
        role=Role.ROLE_USER,
        message_id=str(uuid.uuid4()),
        parts=[Part(text=message)],
    )

    request = SendMessageRequest(message=msg)

    logger.info("Enviando mensagem para %s", agent_url)

    async for event in client.send_message(request):
        if event.HasField("message"):
            resposta = get_message_text(event.message)

            if resposta:
                return resposta

        if event.HasField("task"):
            task = event.task

            for artifact in task.artifacts:
                resposta = get_artifact_text(artifact)

                if resposta:
                    return resposta

            if task.status.HasField("message"):
                resposta = get_message_text(task.status.message)

                if resposta:
                    return resposta

    return "Sem resposta do agente."


def no_de_roteamento(state: State):
    query = state.get("query", "")
    classifications = classifique_intencao_usuario(query)
    logger.info(f"Classificação: {classifications}")
    return [Send(c["agent"], {"query": c["query"]}) for c in classifications]


async def cartao_credito_node(state: State):
    query = state.get("query", "")
    logger.info("Executando agente CARTAO_CREDITO")
    resposta = await request_agent(query, AGENTS["cartao_credito"])
    return {"responses": [resposta]}


async def abrir_conta_node(state: State):
    query = state.get("query", "")
    logger.info("Executando agente ABRIR_CONTA")
    resposta = await request_agent(query, AGENTS["abrir_conta"])
    return {"responses": [resposta]}


builder = StateGraph(State)
builder.add_node("cartao_credito", cartao_credito_node)
builder.add_node("abrir_conta", abrir_conta_node)
builder.add_conditional_edges(START, no_de_roteamento)
builder.add_edge("cartao_credito", END)
builder.add_edge("abrir_conta", END)
graph = builder.compile()


async def executar_supervisor(texto_usuario: str):
    input_state: State = {"query": texto_usuario, "responses": []}
    result = await graph.ainvoke(input_state)
    return "\n\n".join(result["responses"])
