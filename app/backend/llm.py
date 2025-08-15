# app/backend/llm.py
import os
import httpx
from typing import Optional

def have_llm() -> bool:
    return os.environ.get("LLM_PROVIDER","").lower() in {"openai"} and bool(os.environ.get("OPENAI_API_KEY"))

async def call_openai(prompt: str, model: Optional[str]=None, system: Optional[str]=None, temperature: float=0.3) -> str:
    api_key = os.environ["OPENAI_API_KEY"]
    model = model or os.environ.get("OPENAI_MODEL","gpt-4o-mini")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role":"system","content": system or "You are a concise investment analyst. Avoid disclaimers."},
            {"role":"user","content": prompt}
        ],
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
