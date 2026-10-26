import inspect
import logging
import uuid
from operator import add
from typing import Annotated, TypedDict

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers import (
    get_stream_response_text,
    new_text_message,
)
from a2a.types import Message, Role, SendMessageRequest, Task
from ag_ui.core import (
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from src.agents import classifique_intencao_do_usuario

logger = logging.getLogger(__name__)

HTTPX_CLIENT = httpx.AsyncClient(timeout=60)

AGENTS = {
    "cartao_credito": "http://cartao_credito_agent:8000",
    "abrir_conta": "http://abrir_conta_agent:8000",
}

CLIENT_CACHE = {}


# ==========================================================
# LANGGRAPH STATE
# ==========================================================

class State(TypedDict):
    query: str
    responses: Annotated[list[str], add]


# ==========================================================
# CLASSIFICADOR
# ==========================================================

async def classificar(query: str) -> list[dict]:
    """
    Compatível com classificadores síncronos e assíncronos.
    """

    resultado = classifique_intencao_do_usuario(query)

    if inspect.isawaitable(resultado):
        resultado = await resultado

    logger.info("Classificação: %s", resultado)

    return resultado


# ==========================================================
# CLIENTE A2A
# ==========================================================

async def get_a2a_client(agent_url: str):

    if agent_url not in CLIENT_CACHE:

        logger.info(
            "Descobrindo AgentCard em %s",
            agent_url,
        )

        resolver = A2ACardResolver(
            httpx_client=HTTPX_CLIENT,
            base_url=agent_url,
        )

        agent_card = await resolver.get_agent_card()

        logger.info(
            "Agente encontrado: %s",
            agent_card.name,
        )

        config = ClientConfig(
            httpx_client=HTTPX_CLIENT,
            streaming=False,
        )

        factory = ClientFactory(config)

        CLIENT_CACHE[agent_url] = factory.create(
            agent_card
        )

    return CLIENT_CACHE[agent_url]


# ==========================================================
# EXECUÇÃO A2A
# ==========================================================

async def request_agent(
    message: str,
    agent_url: str,
) -> str:

    client = await get_a2a_client(agent_url)

    msg = new_text_message(
        message,
        role=Role.ROLE_USER,
    )

    request = SendMessageRequest(
        message=msg
    )

    logger.info(
        "Enviando mensagem para %s",
        agent_url,
    )

    async for response in client.send_message(request):

        logger.info(
            "Tipo de resposta A2A: %s",
            type(response).__name__,
        )

        texto = get_stream_response_text(response)

        if texto:
            logger.info(
                "Resposta recebida do agente %s",
                agent_url,
            )

            return texto

    logger.warning(
        "Agente %s não retornou texto",
        agent_url,
    )

    return "O agente não retornou uma resposta."


# ==========================================================
# ROUTER LANGGRAPH
# ==========================================================

async def no_de_roteamento(state: State):

    query = state.get("query", "")

    classifications = await classificar(query)

    if not classifications:

        logger.warning(
            "Nenhum agente selecionado para: %s",
            query,
        )

        return END

    destinos = []

    for classification in classifications:

        agent_name = classification["agent"]

        if agent_name not in AGENTS:

            logger.warning(
                "Agente desconhecido: %s",
                agent_name,
            )

            continue

        destinos.append(
            Send(
                agent_name,
                {
                    "query": classification["query"],
                    "responses": [],
                },
            )
        )

    return destinos or END


# ==========================================================
# NODES
# ==========================================================

async def cartao_credito_node(state: State):

    logger.info(
        "Executando agente CARTAO_CREDITO"
    )

    resposta = await request_agent(
        state["query"],
        AGENTS["cartao_credito"],
    )

    return {
        "responses": [resposta]
    }


async def abrir_conta_node(state: State):

    logger.info(
        "Executando agente ABRIR_CONTA"
    )

    resposta = await request_agent(
        state["query"],
        AGENTS["abrir_conta"],
    )

    return {
        "responses": [resposta]
    }


# ==========================================================
# BUILD DO LANGGRAPH
# ==========================================================

builder = StateGraph(State)

builder.add_node(
    "cartao_credito",
    cartao_credito_node,
)

builder.add_node(
    "abrir_conta",
    abrir_conta_node,
)

builder.add_conditional_edges(
    START,
    no_de_roteamento,
)

builder.add_edge(
    "cartao_credito",
    END,
)

builder.add_edge(
    "abrir_conta",
    END,
)

graph = builder.compile()


# ==========================================================
# SUPERVISOR NORMAL
# ==========================================================

async def executar_supervisor(
    texto_usuario: str,
) -> str:

    input_state: State = {
        "query": texto_usuario,
        "responses": [],
    }

    result = await graph.ainvoke(
        input_state
    )

    responses = result.get(
        "responses", []
    )

    if not responses:
        return (
            "Não consegui identificar um agente "
            "para atender sua solicitação."
        )

    return "\n\n".join(responses)


# ==========================================================
# SUPERVISOR AG-UI
# ==========================================================

def extrair_texto_usuario(input_data) -> str:

    messages = input_data.messages

    if not messages:
        return ""

    for message in reversed(messages):

        if message.role != "user":
            continue

        content = message.content

        if isinstance(content, str):
            return content

        if isinstance(content, list):

            textos = []

            for part in content:

                if isinstance(part, dict):
                    texto = part.get("text", "")

                else:
                    texto = getattr(
                        part, "text", ""
                    )

                if texto:
                    textos.append(texto)

            return "\n".join(textos)

    return ""


async def executar_supervisor_stream(input_data):
    """
    Gera eventos AG-UI.

    Mantém o estado compartilhado atualizado
    enquanto os agentes A2A são executados.
    """

    thread_id = str(
        getattr(input_data, "thread_id", None)
        or uuid.uuid4()
    )

    run_id = str(
        getattr(input_data, "run_id", None)
        or uuid.uuid4()
    )

    assistant_id = str(uuid.uuid4())

    user_message = extrair_texto_usuario(
        input_data
    )

    state = {
        "user_query": user_message,
        "agents": [],
        "responses": [],
    }

    # ------------------------------------------------------
    # RUN STARTED
    # ------------------------------------------------------

    yield RunStartedEvent(
        type=EventType.RUN_STARTED,
        thread_id=thread_id,
        run_id=run_id,
    )

    yield StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=state.copy(),
    )

    # ------------------------------------------------------
    # MESSAGE START
    # ------------------------------------------------------

    yield TextMessageStartEvent(
        type=EventType.TEXT_MESSAGE_START,
        message_id=assistant_id,
        role="assistant",
    )

    try:

        if not user_message.strip():

            yield TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id=assistant_id,
                delta="Não recebi uma mensagem para processar.",
            )

        else:

            # --------------------------------------------------
            # CLASSIFICAÇÃO
            # --------------------------------------------------

            classifications = await classificar(
                user_message
            )

            classifications = [
                c
                for c in classifications
                if c.get("agent") in AGENTS
            ]

            agentes = list(
                dict.fromkeys(
                    c["agent"]
                    for c in classifications
                )
            )

            state["agents"] = agentes

            yield StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot=state.copy(),
            )

            # --------------------------------------------------
            # EXECUÇÃO DOS AGENTES
            # --------------------------------------------------

            respostas = []

            for classification in classifications:

                agent_name = classification["agent"]

                logger.info(
                    "Chamando agente %s",
                    agent_name,
                )

                resposta = await request_agent(
                    classification.get(
                        "query",
                        user_message,
                    ),
                    AGENTS[agent_name],
                )

                respostas.append(resposta)

                state["responses"].append(
                    {
                        "agent": agent_name,
                        "response": resposta,
                    }
                )

                yield StateSnapshotEvent(
                    type=EventType.STATE_SNAPSHOT,
                    snapshot={
                        **state,
                        "responses": [
                            item.copy()
                            for item in state["responses"]
                        ],
                    },
                )

            # --------------------------------------------------
            # RESPOSTA FINAL
            # --------------------------------------------------

            resposta_final = (
                "\n\n".join(respostas)
                if respostas
                else (
                    "Não consegui identificar um agente "
                    "para atender sua solicitação."
                )
            )

            yield TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id=assistant_id,
                delta=resposta_final,
            )

    except Exception:

        logger.exception(
            "Erro durante execução AG-UI"
        )

        yield TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT,
            message_id=assistant_id,
            delta=(
                "Ocorreu um erro ao processar "
                "sua solicitação."
            ),
        )

        yield TextMessageEndEvent(
            type=EventType.TEXT_MESSAGE_END,
            message_id=assistant_id,
        )

        yield RunErrorEvent(
            type=EventType.RUN_ERROR,
            message="Falha ao executar o supervisor.",
        )

        return

    # ------------------------------------------------------
    # MESSAGE END
    # ------------------------------------------------------

    yield TextMessageEndEvent(
        type=EventType.TEXT_MESSAGE_END,
        message_id=assistant_id,
    )

    # ------------------------------------------------------
    # RUN FINISHED
    # ------------------------------------------------------

    yield RunFinishedEvent(
        type=EventType.RUN_FINISHED,
        thread_id=thread_id,
        run_id=run_id,
    )
