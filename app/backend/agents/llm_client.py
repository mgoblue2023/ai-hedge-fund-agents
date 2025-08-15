# app/backend/agents/llm_client.py
import os
import httpx
from typing import Optional, Dict, Any

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")  # default; can be overridden per request

def _openai_base_url() -> str:
    # Standard OpenAI; if you proxy, set OPENAI_BASE_URL
    return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

def _headers() -> Dict[str, str]:
    if LLM_PROVIDER == "openai":
        return {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
    return {"Content-Type": "application/json"}

def _extract_text(data: Dict[str, Any]) -> str:
    """
    Be liberal in what we accept:
    - OpenAI chat.completions: data["choices"][0]["message"]["content"]
    - OpenAI legacy completions: data["choices"][0]["text"]
    - Some providers: data["output_text"] or data["content"]
    - Error payloads: raise with helpful message
    """
    if "choices" in data and data["choices"]:
        choice = data["choices"][0]
        # chat
        if isinstance(choice, dict) and "message" in choice:
            msg = choice["message"] or {}
            return (msg.get("content") or "").strip()
        # legacy text
        if "text" in choice:
            return (choice.get("text") or "").strip()

    # alternative fields some gateways use
    for k in ("output_text", "content", "output"):
        if k in data and isinstance(data[k], str):
            return data[k].strip()

    # If the server returned an error structure, surface it
    if "error" in data:
        err = data["error"]
        raise RuntimeError(f"LLM error: {err.get('message') or err}")

    raise RuntimeError(f"Unexpected LLM response shape: {list(data.keys())}")

async def chat(prompt: str, model: Optional[str] = None, temperature: float = 0.2, timeout_s: float = 30.0) -> str:
    if LLM_PROVIDER != "openai":
        raise NotImplementedError(f"Provider {LLM_PROVIDER} not wired yet")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    url = f"{_openai_base_url()}/chat/completions"
    payload = {
        "model": model or LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are an investing co-pilot. Be concise and practical."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
        # If not 2xx, raise with the body to aid debugging
        if resp.status_code // 100 != 2:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise RuntimeError(f"LLM HTTP {resp.status_code}: {body}")
        data = resp.json()
        return _extract_text(data)
