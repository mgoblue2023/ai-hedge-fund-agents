# app/backend/agents/llm_client.py
import os
import httpx
from typing import Optional, Dict, Any

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Dev flags
MOCK = os.getenv("LLM_MOCK", "0") == "1"
FALLBACK_ON_QUOTA = os.getenv("LLM_FALLBACK_TO_MOCK_ON_QUOTA", "1") == "1"

print(f"llm_client: loaded (robust extractor) mock={MOCK} fallback={FALLBACK_ON_QUOTA} model={LLM_MODEL}")

def _openai_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

def _headers() -> Dict[str, str]:
    if LLM_PROVIDER == "openai":
        return {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
    return {"Content-Type": "application/json"}

def _extract_text(data: Dict[str, Any]) -> str:
    if "choices" in data and data["choices"]:
        c = data["choices"][0]
        if isinstance(c, dict) and "message" in c:
            return (c["message"].get("content") or "").strip()
        if "text" in c:
            return (c.get("text") or "").strip()
    for k in ("output_text", "content", "output"):
        if k in data and isinstance(data[k], str):
            return data[k].strip()
    if "error" in data:
        err = data["error"]
        raise RuntimeError(f"LLM error: {err.get('message') or err}")
    raise RuntimeError(f"Unexpected LLM response shape: {list(data.keys())}")

def _mock_reply(prompt: str) -> str:
    if "exactly: PONG" in prompt:
        return "PONG"
    return (
        "Rationale: Mock analysis indicating neutral outlook over 1–3 months. "
        "Valuation and momentum do not suggest a strong edge.\n"
        "Final action: hold"
    )

async def chat(prompt: str, model: Optional[str] = None, temperature: float = 0.2, timeout_s: float = 30.0) -> str:
    if MOCK:
        return _mock_reply(prompt)

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
        if resp.status_code // 100 != 2:
            # Try to parse JSON; fall back to mock if quota
            try:
                body = resp.json()
            except Exception:
                body = {"text": resp.text}

            if resp.status_code == 429:
                err = (body.get("error") if isinstance(body, dict) else {}) or {}
                code = str(err.get("code") or err.get("type") or "").lower()
                if FALLBACK_ON_QUOTA and code in ("insufficient_quota", "billing_hard_limit_reached"):
                    return _mock_reply(prompt)

            raise RuntimeError(f"LLM HTTP {resp.status_code}: {body}")

        data = resp.json()
        return _extract_text(data)
