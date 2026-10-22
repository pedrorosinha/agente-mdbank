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

agente_cartao_credito = create_agent(
    __llm,
    tools=[],
    system_prompt=(
        "Você é um especialista em cartão de crédito do banco MDBank. "
        "Os cartões que existem no MDBank são: [platinum, gold, silver e mdzao]."
        "Ajude o cliente com dúvidas, solicitações e limites."
    )
)

class CartaoCreditoRequest(BaseModel):
    message: str
    
@app.post("/send")
async def consultar(request: CartaoCreditoRequest):
    mensagem = request.message
    if not mensagem:
        raise HTTPException(
            status_code=400, detail="Campo 'message' é obrigatório.")
    
    try:
        resultado = agente_cartao_credito.invoke(
            {"messages": [HumanMessage(content=mensagem)]}
        )
        mensagem_ia = resultado["messages"][-1]
        return {"resposta": mensagem_ia.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/")
async def health():
    return {"status": "ok"}