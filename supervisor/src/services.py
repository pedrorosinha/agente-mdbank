import logging
from operator import add
from typing import Annotated, TypedDict

import requests
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from src.agents import classifique_intencao_usuario

logger = logging.getLogger(__name__)


class State(TypedDict):
    query: str
    responses: Annotated[list[str], add]


def request_agent(message: str, agent: str) -> str:
    url = f"http://{agent}:8000/send"
    payload = {"message": message}

    try:
        logger.info(
            f"Enviando solicitação para o agente {agent} em {url} com payload: {payload}"
        )

        response = requests.post(url, json=payload)
        response.raise_for_status()

        data = response.json()

        logger.info(f"Resposta recebida do {agent}: {data}")

        return data.get("resposta", "Resposta não encontrada.")

    except Exception as e:
        logger.exception(f"Erro ao enviar requisição para {agent}")
        return f"Erro ao consultar {agent}: {str(e)}"


def no_de_roteamento(state: State):
    query = state.get("query", "")
    classifications = classifique_intencao_usuario(query)

    return [Send(c["agent"], {"query": c["query"]}) for c in classifications]


def cartao_credito_node(state: State):
    query = state.get("query", "")

    logger.info("Executando agente CARTAO_CREDITO")

    resposta = request_agent(query, "cartao_credito_agent")

    return {"responses": [resposta]}



def abrir_conta_node(state: State):
    query = state.get("query", "")
    logger.info("Executando agente ABRIR_CONTA")
    resposta = request_agent(query, "abrir_conta_agent")
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
    result = graph.invoke(input_state)
    return "\n\n".join(result["responses"])
