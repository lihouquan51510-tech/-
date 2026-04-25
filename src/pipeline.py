from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

JN_BEIKE_URL = "https://jn.ke.com/zufang/"
SAMPLE_FILE = Path("data/sample_listings_jn.json")


@dataclass
class UserQuery:
    raw_text: str
    budget_max: int | None = None
    bedrooms: int | None = None
    rent_type: str | None = None
    district: str | None = None
    must_have: list[str] | None = None


def parse_user_query(raw_text: str) -> UserQuery:
    budget = None
    bedrooms = None
    rent_type = None
    district = None
    must_have: list[str] = []

    budget_match = re.search(r"预算\s*(\d{3,5})", raw_text)
    if budget_match:
        budget = int(budget_match.group(1))

    bed_match = re.search(r"([一二三四1234])居|([一二三四1234])室", raw_text)
    if bed_match:
        token = bed_match.group(1) or bed_match.group(2)
        map_cn = {"一": 1, "二": 2, "三": 3, "四": 4}
        bedrooms = map_cn.get(token, int(token)) if token else None

    if "整租" in raw_text:
        rent_type = "整租"
    elif "合租" in raw_text:
        rent_type = "合租"

    for d in ["历下", "历城", "槐荫", "市中", "高新", "天桥", "长清", "章丘", "济阳"]:
        if d in raw_text:
            district = d
            break

    rules = {
        "养猫": "可养猫",
        "养宠": "可养宠",
        "电梯": "电梯",
        "车位": "车位",
        "地铁": "近地铁",
        "拎包入住": "拎包入住",
        "独卫": "独卫",
        "开间": "开间",
        "采光": "采光好",
    }
    for k, v in rules.items():
        if k in raw_text:
            must_have.append(v)

    return UserQuery(
        raw_text=raw_text,
        budget_max=budget,
        bedrooms=bedrooms,
        rent_type=rent_type,
        district=district,
        must_have=must_have or None,
    )


def _parse_layout_bedrooms(layout: str) -> int | None:
    m = re.search(r"(\d)室", layout)
    return int(m.group(1)) if m else None


def crawl_beike_jinan(max_items: int = 30, timeout: int = 10) -> list[dict[str, Any]]:
    """抓取贝壳济南租房列表页。

    若线上抓取失败（反爬、网络限制），回退到本地样例数据，保证闭环可跑通。
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
        resp = requests.get(JN_BEIKE_URL, headers=headers, timeout=timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".content__list--item")
        listings: list[dict[str, Any]] = []

        for card in cards[:max_items]:
            title_el = card.select_one("p.content__list--item--title a")
            price_el = card.select_one("span.content__list--item-price em")
            desc_el = card.select_one("p.content__list--item--des")
            brand_el = card.select_one("span.brand")

            if not title_el or not price_el:
                continue

            title = title_el.get_text(strip=True)
            url = title_el.get("href", "")
            if url.startswith("/"):
                url = "https://jn.ke.com" + url

            price_text = price_el.get_text(strip=True)
            price = int(re.sub(r"\D", "", price_text) or 0)

            desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""
            layout_match = re.search(r"\d室\d厅", desc_text)
            layout = layout_match.group(0) if layout_match else "未知"

            district = None
            for d in ["历下", "历城", "槐荫", "市中", "高新", "天桥", "长清", "章丘", "济阳"]:
                if d in desc_text or d in title:
                    district = d
                    break

            listings.append(
                {
                    "title": title,
                    "price": price,
                    "layout": layout,
                    "area_sqm": None,
                    "district": district,
                    "subdistrict": None,
                    "tags": [brand_el.get_text(strip=True)] if brand_el else [],
                    "url": url,
                    "description": desc_text,
                }
            )

        if listings:
            return listings
    except Exception:
        pass

    return json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))


def score_listing(query: UserQuery, listing: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    price = listing.get("price") or 0
    if query.budget_max:
        if price <= query.budget_max:
            score += 35
            reasons.append(f"价格 {price} ≤ 预算 {query.budget_max}")
        else:
            overshoot = price - query.budget_max
            penalty = min(30, overshoot / max(query.budget_max, 1) * 40)
            score -= penalty
            reasons.append(f"超预算 {overshoot} 元")

    q_bed = query.bedrooms
    l_bed = _parse_layout_bedrooms(listing.get("layout", ""))
    if q_bed is not None and l_bed is not None:
        if l_bed >= q_bed:
            score += 20
            reasons.append(f"户型匹配：{listing.get('layout')}")
        else:
            score -= 15
            reasons.append(f"户型偏小：{listing.get('layout')}")

    if query.rent_type:
        if query.rent_type in (listing.get("description", "") + " " + listing.get("title", "")):
            score += 15
            reasons.append(f"包含{query.rent_type}信息")

    if query.district:
        if query.district == listing.get("district"):
            score += 20
            reasons.append(f"区域匹配：{query.district}")
        else:
            score -= 8

    must = query.must_have or []
    haystack = " ".join([listing.get("title", ""), listing.get("description", ""), " ".join(listing.get("tags", []))])
    match_count = 0
    for feature in must:
        if feature in haystack:
            match_count += 1
            reasons.append(f"命中需求：{feature}")
    if must:
        score += 5 * match_count

    return round(score, 2), reasons


def recommend(raw_text: str, top_k: int = 5) -> dict[str, Any]:
    query = parse_user_query(raw_text)
    listings = crawl_beike_jinan()

    scored = []
    for item in listings:
        s, reasons = score_listing(query, item)
        scored.append({**item, "score": s, "reasons": reasons})

    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
    return {
        "query": query,
        "total_candidates": len(scored),
        "recommendations": ranked[:top_k],
    }
