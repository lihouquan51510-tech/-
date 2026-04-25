from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from urllib.error import URLError
from urllib.request import Request, urlopen

JN_BEIKE_URL = "https://jn.ke.com/zufang/"
SAMPLE_FILE = Path("data/sample_listings_jn.json")
TEST_CASE_FILE = Path("data/test_cases_jinan_beike.json")


@dataclass
class UserQuery:
    raw_text: str
    budget_max: int | None = None
    bedrooms: int | None = None
    rent_type: str | None = None
    district: str | None = None
    subdistrict: str | None = None
    urgency: str | None = None
    must_have: list[str] | None = None
    avoid: list[str] | None = None


@dataclass
class AgentStageLog:
    stage: str
    message: str


def _cn_num_to_int(token: str) -> int | None:
    token = token.strip()
    digit_map = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if token.isdigit():
        return int(token)
    if token in digit_map:
        return digit_map[token]
    if token == "十":
        return 10
    if token.startswith("十") and len(token) == 2 and token[1] in digit_map:
        return 10 + digit_map[token[1]]
    if token.endswith("十") and len(token) == 2 and token[0] in digit_map:
        return digit_map[token[0]] * 10
    if "十" in token and len(token) == 3 and token[0] in digit_map and token[2] in digit_map:
        return digit_map[token[0]] * 10 + digit_map[token[2]]
    return None


def parse_user_query(raw_text: str) -> UserQuery:
    """规则解析器（MVP）。

    后续可替换为 LLM JSON schema parsing。
    """
    budget = None
    bedrooms = None
    rent_type = None
    district = None
    subdistrict = None
    urgency = None
    must_have: list[str] = []
    avoid: list[str] = []

    budget_match = re.search(r"预算\s*([0-9]{3,6})", raw_text)
    if budget_match:
        budget = int(budget_match.group(1))

    bed_patterns = [
        r"([零一二两三四五六七八九十\d]+)室",
        r"([零一二两三四五六七八九十\d]+)居",
    ]
    for pattern in bed_patterns:
        bed_match = re.search(pattern, raw_text)
        if bed_match:
            value = _cn_num_to_int(bed_match.group(1))
            if value is not None and 0 < value <= 10:
                bedrooms = value
                break

    if "整租" in raw_text:
        rent_type = "整租"
    elif "合租" in raw_text:
        rent_type = "合租"

    districts = ["历下", "历城", "槐荫", "市中", "高新", "天桥", "长清", "章丘", "济阳"]
    for d in districts:
        if d in raw_text:
            district = d
            break

    hotspots = ["奥体", "西客站", "会展中心", "王舍人", "英雄山", "CBD"]
    for h in hotspots:
        if h in raw_text:
            subdistrict = h
            break

    if any(token in raw_text for token in ["这周末", "下周一", "马上", "尽快", "急"]):
        urgency = "high"

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
        "安静": "安静",
    }
    for k, v in rules.items():
        if k in raw_text:
            must_have.append(v)

    avoid_rules = ["临街", "顶楼", "一楼", "施工噪音", "隔断间"]
    for item in avoid_rules:
        if item in raw_text:
            avoid.append(item)

    return UserQuery(
        raw_text=raw_text,
        budget_max=budget,
        bedrooms=bedrooms,
        rent_type=rent_type,
        district=district,
        subdistrict=subdistrict,
        urgency=urgency,
        must_have=must_have or None,
        avoid=avoid or None,
    )


def _merge_queries(rule_query: UserQuery, llm_query: UserQuery | None) -> tuple[UserQuery, dict[str, Any]]:
    """LLM + Rule 融合投票：优先一致性，冲突时按稳定性启发式选择。"""
    if llm_query is None:
        return rule_query, {"mode": "rule_only", "conflicts": [], "agreements": []}

    merged = UserQuery(raw_text=rule_query.raw_text)
    conflicts: list[str] = []
    agreements: list[str] = []

    # budget: 若冲突较大，优先规则；冲突较小取较保守值（较小预算）
    rb, lb = rule_query.budget_max, llm_query.budget_max
    if rb is None and lb is None:
        merged.budget_max = None
    elif rb is None:
        merged.budget_max = lb
    elif lb is None:
        merged.budget_max = rb
    elif rb == lb:
        merged.budget_max = rb
        agreements.append("budget_max")
    else:
        conflicts.append(f"budget_max(rule={rb},llm={lb})")
        gap = abs(rb - lb) / max(rb, 1)
        merged.budget_max = rb if gap > 0.4 else min(rb, lb)

    # bedrooms: 取合法范围且更保守（较大卧室需求）
    rr, lr = rule_query.bedrooms, llm_query.bedrooms
    valid = [x for x in [rr, lr] if isinstance(x, int) and 0 < x <= 10]
    if rr is not None and lr is not None and rr == lr:
        agreements.append("bedrooms")
    elif rr is not None and lr is not None and rr != lr:
        conflicts.append(f"bedrooms(rule={rr},llm={lr})")
    merged.bedrooms = max(valid) if valid else (rr if rr is not None else lr)

    # 其余字段：一致优先；冲突默认规则优先（稳定）
    for field in ["rent_type", "district", "subdistrict", "urgency"]:
        rv = getattr(rule_query, field)
        lv = getattr(llm_query, field)
        if rv is None and lv is None:
            val = None
        elif rv is None:
            val = lv
        elif lv is None:
            val = rv
        elif rv == lv:
            agreements.append(field)
            val = rv
        else:
            conflicts.append(f"{field}(rule={rv},llm={lv})")
            val = rv
        setattr(merged, field, val)

    # list 字段合并去重，既保留规则稳定性也吸收 LLM 补充
    must = list(dict.fromkeys((rule_query.must_have or []) + (llm_query.must_have or [])))
    avoid = list(dict.fromkeys((rule_query.avoid or []) + (llm_query.avoid or [])))
    merged.must_have = must or None
    merged.avoid = avoid or None

    return merged, {"mode": "fusion", "conflicts": conflicts, "agreements": agreements}


def _parse_layout_bedrooms(layout: str) -> int | None:
    m = re.search(r"(\d)室", layout)
    return int(m.group(1)) if m else None


def _safe_text(element: Any) -> str:
    return element.get_text(" ", strip=True) if element else ""


def crawl_beike_jinan(max_items: int = 30, timeout: int = 10) -> list[dict[str, Any]]:
    """抓取贝壳济南租房列表页。

    若线上抓取失败（反爬、网络限制），回退到本地样例数据，保证闭环可跑通。
    """
    try:
        req = Request(
            JN_BEIKE_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )
        with urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 轻量正则解析（页面结构变动时可能失效，失效则回退本地样例）
        blocks = re.findall(r'<div class="content__list--item.*?</div>\s*</div>', html, flags=re.S)
        listings: list[dict[str, Any]] = []

        districts = ["历下", "历城", "槐荫", "市中", "高新", "天桥", "长清", "章丘", "济阳"]
        for block in blocks[:max_items]:
            t = re.search(r'title="([^"]+)"', block)
            u = re.search(r'href="([^"]+)"', block)
            p = re.search(r'content__list--item-price[^>]*>\s*<em>(\d+)</em>', block)
            d = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", block)).strip()

            if not (t and u and p):
                continue

            title = t.group(1).strip()
            url = u.group(1).strip()
            if url.startswith("/"):
                url = "https://jn.ke.com" + url
            price = int(p.group(1))

            layout_match = re.search(r"\d室\d厅", d)
            layout = layout_match.group(0) if layout_match else "未知"

            district = None
            for dc in districts:
                if dc in d or dc in title:
                    district = dc
                    break

            listings.append(
                {
                    "title": title,
                    "price": price,
                    "layout": layout,
                    "area_sqm": None,
                    "district": district,
                    "subdistrict": None,
                    "tags": [],
                    "url": url,
                    "description": d,
                }
            )

        if listings:
            return listings
    except (URLError, TimeoutError, ValueError):
        pass
    except Exception:
        pass

    return json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))


def hard_filter(query: UserQuery, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for listing in listings:
        price = listing.get("price") or 0
        if query.budget_max is not None and price > query.budget_max * 1.35:
            continue

        l_bed = _parse_layout_bedrooms(listing.get("layout", ""))
        if query.bedrooms is not None and l_bed is not None and l_bed < query.bedrooms:
            continue

        if query.district and listing.get("district") and query.district != listing.get("district"):
            continue

        result.append(listing)
    return result


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
            reasons.append(f"略超预算 {overshoot} 元")

    q_bed = query.bedrooms
    l_bed = _parse_layout_bedrooms(listing.get("layout", ""))
    if q_bed is not None and l_bed is not None:
        if l_bed >= q_bed:
            score += 20
            reasons.append(f"户型匹配：{listing.get('layout')}")
        else:
            score -= 15
            reasons.append(f"户型偏小：{listing.get('layout')}")

    if query.rent_type and query.rent_type in (listing.get("description", "") + " " + listing.get("title", "")):
        score += 15
        reasons.append(f"包含{query.rent_type}信息")

    if query.district:
        if query.district == listing.get("district"):
            score += 20
            reasons.append(f"区域匹配：{query.district}")
        else:
            score -= 8

    if query.subdistrict and query.subdistrict in (
        (listing.get("title", "") + " " + listing.get("description", "") + " " + (listing.get("subdistrict") or ""))
    ):
        score += 8
        reasons.append(f"板块命中：{query.subdistrict}")

    must = query.must_have or []
    haystack = " ".join([listing.get("title", ""), listing.get("description", ""), " ".join(listing.get("tags", []))])
    match_count = 0
    for feature in must:
        if feature in haystack:
            match_count += 1
            reasons.append(f"命中需求：{feature}")
    if must:
        score += 5 * match_count

    for block in query.avoid or []:
        if block in haystack:
            score -= 15
            reasons.append(f"命中避让项：{block}")

    if query.urgency == "high" and any(k in haystack for k in ["随时看房", "拎包入住"]):
        score += 10
        reasons.append("满足紧急入住偏好")

    return round(score, 2), reasons


def recommend(raw_text: str, top_k: int = 5, use_llm_parser: bool = False, use_semantic_recall: bool = False) -> dict[str, Any]:
    logs: list[AgentStageLog] = []

    rule_query = parse_user_query(raw_text)
    llm_query = None
    parse_meta: dict[str, Any] = {"mode": "rule_only", "conflicts": [], "agreements": []}

    if use_llm_parser:
        try:
            from src.llm_parser import parse_query_with_llm
            llm_query = parse_query_with_llm(raw_text)
        except Exception:
            llm_query = None

    if use_llm_parser:
        query, parse_meta = _merge_queries(rule_query, llm_query)
        if parse_meta.get("mode") == "fusion":
            logs.append(AgentStageLog(stage="parse", message="已完成融合解析（LLM + Rule Voting）"))
        else:
            logs.append(AgentStageLog(stage="parse", message="LLM 不可用，已回退规则解析（Rule Parser）"))
    else:
        query = rule_query
        logs.append(AgentStageLog(stage="parse", message="已完成规则解析（Rule Parser）"))

    listings = crawl_beike_jinan()
    logs.append(AgentStageLog(stage="crawl", message=f"候选房源抓取完成，共 {len(listings)} 条"))

    filtered = hard_filter(query, listings)
    logs.append(AgentStageLog(stage="filter", message=f"硬筛选后剩余 {len(filtered)} 条"))

    pool = filtered if filtered else listings
    if use_semantic_recall:
        try:
            from src.semantic_recall import semantic_recall
            pool = semantic_recall(raw_text, pool, top_n=max(top_k * 4, top_k))
            logs.append(AgentStageLog(stage="recall", message=f"语义召回完成，候选收敛至 {len(pool)} 条"))
        except Exception:
            logs.append(AgentStageLog(stage="recall", message="语义召回失败，已跳过"))

    scored = []
    for item in pool:
        s, reasons = score_listing(query, item)
        if item.get("semantic_score") is not None:
            s += float(item["semantic_score"]) * 10
            reasons.append(f"语义相关度加分：{item['semantic_score']}")
        scored.append({**item, "score": round(s, 2), "reasons": reasons})

    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
    logs.append(AgentStageLog(stage="rank", message=f"排序完成，返回 Top {top_k}"))

    return {
        "query": query,
        "parse_meta": parse_meta,
        "stage_logs": [asdict(x) for x in logs],
        "total_candidates": len(listings),
        "filtered_candidates": len(filtered),
        "recommendations": ranked[:top_k],
    }


def load_test_cases() -> list[dict[str, Any]]:
    payload = json.loads(TEST_CASE_FILE.read_text(encoding="utf-8"))
    return payload.get("test_cases", [])
