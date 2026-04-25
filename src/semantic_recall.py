from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable


def _tokenize(text: str) -> list[str]:
    """轻量 tokenizer：中文按字+英文按词，适配无依赖环境。"""
    text = text.lower()
    zh_chars = re.findall(r"[\u4e00-\u9fff]", text)
    en_words = re.findall(r"[a-z0-9]+", text)
    return zh_chars + en_words


def _tf(tokens: Iterable[str]) -> Counter:
    return Counter(tokens)


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def semantic_score(query: str, doc: str) -> float:
    q = _tf(_tokenize(query))
    d = _tf(_tokenize(doc))
    return round(_cosine(q, d), 4)


def semantic_recall(query: str, listings: list[dict], top_n: int = 20) -> list[dict]:
    scored = []
    for it in listings:
        text = " ".join([
            str(it.get("title", "")),
            str(it.get("description", "")),
            " ".join(it.get("tags", []) if isinstance(it.get("tags"), list) else []),
        ])
        s = semantic_score(query, text)
        scored.append({**it, "semantic_score": s})

    ranked = sorted(scored, key=lambda x: x.get("semantic_score", 0), reverse=True)
    return ranked[:top_n]
