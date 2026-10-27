from contextlib import asynccontextmanager

from discovery import discover_agents
from fastapi import FastAPI
from mcp_discovery import discover_tools
from registry import AGENT_REGISTRY, build_index, resolve_agent, to_json_compatible


def prepare_response(result):
    return to_json_compatible(result)


@asynccontextmanager
async def lifespan(app: FastAPI):

    agents = await discover_agents()
    tools = await discover_tools()

    AGENT_REGISTRY.update(agents)
    AGENT_REGISTRY.update(tools)

    build_index()

    print("Unified registry:", AGENT_REGISTRY)

    yield


app = FastAPI(lifespan=lifespan)


@app.get("/skills")
def listar_skills():
    return AGENT_REGISTRY


@app.get("/resolve")
def resolve(query: str, top_k: int = 3, threshold: float = 0.3):
    result = resolve_agent(query, top_k=top_k, threshold=threshold)

    if not result:
        return {"error": "no match"}

    return prepare_response(result)


@app.get("/resolve/agents")
def resolve_agents(query: str, top_k: int = 3, threshold: float = 0.3):
    result = resolve_agent(query, top_k=top_k, threshold=threshold, filter_type="agent")

    if not result:
        return {"error": "no match"}

    return prepare_response(result)


@app.get("/resolve/tools")
def resolve_tools(query: str, top_k: int = 3, threshold: float = 0.3):
    result = resolve_agent(query, top_k=top_k, threshold=threshold, filter_type="tool")

    if not result:
        return {"error": "no match"}

    return prepare_response(result)


@app.get("/skills/agents")
def listar_agents():
    agents = {k: v for k, v in AGENT_REGISTRY.items() if v.get("type") == "agent"}

    return prepare_response(agents)


@app.get("/skills/tools")
def listar_tools():
    tools = {k: v for k, v in AGENT_REGISTRY.items() if v.get("type") == "tool"}

    return prepare_response(tools)


@app.get("/")
async def health():
    return {"status": "ok"}
