import os

import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-nano-9b-v2:free")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def build_payload(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }


def build_headers() -> dict:
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to your environment or .env file."
        )
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def send_request(payload: dict) -> dict:
    headers = build_headers()
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BASE_URL, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


def extract_text(response_json: dict) -> str:
    return response_json["choices"][0]["message"]["content"]


async def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    payload = build_payload(system_prompt, user_prompt, temperature)
    response_json = await send_request(payload)
    return extract_text(response_json)
