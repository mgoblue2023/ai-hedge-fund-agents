from fastapi import APIRouter
from app.backend.agents.llm_client import chat as llm_chat

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/llm-ping")
async def llm_ping(model: str | None = None):
    txt = await llm_chat("Reply with exactly: PONG", model=model)
    return {"ok": True, "model": model, "text": txt}
