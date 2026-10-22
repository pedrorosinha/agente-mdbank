from fastapi import FastAPI, Request, HTTPException
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from pydantic import BaseModel
import os

load_dotenv()

__llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7,
    reasoning_format="hidden"
)

app = FastAPI()

agente_abertura_conta = create_agent(
    __llm,
    tools=[],
    system_prompt=(
        "Você é um especialista em abertura de conta do banco MDBank. "
        "Ajude o cliente a abrir uma conta e explique os tipos de conta disponíveis que são "
        "contas simples e conta completa."
    )
)

class AbrirContaRequest(BaseModel):
    message: str
    
@app.post("/send")
async def consultar(request: AbrirContaRequest):
    mensagem = request.message
    if not mensagem:
        raise HTTPException(
            status_code=400, detail="Campo 'message' é obrigatório.")
    
    try:
        resultado = agente_abertura_conta.invoke(
            {"messages": [HumanMessage(content=mensagem)]}
        )
        mensagem_ia = resultado["messages"][-1]
        return {"resposta": mensagem_ia.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/")
async def health():
    return {"status": "ok"}