from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any
from urllib.request import Request, urlopen

from src.pipeline import UserQuery


PROMPT = """你是租房需求结构化助手。请从用户文本中提取字段并只返回 JSON。
字段：budget_max, bedrooms, rent_type, district, subdistrict, urgency, must_have, avoid。
要求：
1) 仅返回 JSON，不要解释
2) 未提及字段用 null
3) must_have/avoid 始终返回数组
"""


def _build_payload(model: str, raw_text: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": raw_text},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }


def parse_query_with_llm(raw_text: str) -> UserQuery | None:
    """使用 OpenAI 兼容接口解析需求。失败返回 None（由规则解析兜底）。"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    payload = _build_payload(model, raw_text)
    req = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="ignore"))

        content = body["choices"][0]["message"]["content"]
        data = json.loads(content)

        return UserQuery(
            raw_text=raw_text,
            budget_max=data.get("budget_max"),
            bedrooms=data.get("bedrooms"),
            rent_type=data.get("rent_type"),
            district=data.get("district"),
            subdistrict=data.get("subdistrict"),
            urgency=data.get("urgency"),
            must_have=data.get("must_have") or None,
            avoid=data.get("avoid") or None,
        )
    except Exception:
        return None


def dump_query(query: UserQuery) -> dict[str, Any]:
    return asdict(query)
