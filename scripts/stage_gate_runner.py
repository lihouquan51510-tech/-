"""阶段闸门执行器：每阶段完成后执行样例测试并输出 Gate 报告。"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import crawl_beike_jinan, load_test_cases, parse_user_query, recommend

REPORT_PATH = Path("data/stage_gate_report.json")


def _stage_result(stage_id: str, stage_name: str, passed: bool, metrics: dict[str, Any], next_stage_hint: str) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_name": stage_name,
        "passed": passed,
        "metrics": metrics,
        "next_stage_hint": next_stage_hint,
    }


def run_stage_0_scope() -> dict[str, Any]:
    cases = load_test_cases()
    has_20 = len(cases) == 20
    required_fields_ok = all("raw_text" in c and "target_params" in c for c in cases)
    passed = has_20 and required_fields_ok
    return _stage_result(
        "stage_0",
        "范围冻结",
        passed,
        {"case_count": len(cases), "required_fields_ok": required_fields_ok},
        "是否进入 Stage 1（数据采集）？",
    )


def run_stage_1_crawl() -> dict[str, Any]:
    listings = crawl_beike_jinan()
    passed = len(listings) > 0
    return _stage_result(
        "stage_1",
        "数据采集",
        passed,
        {"listing_count": len(listings), "top_title": listings[0]["title"] if listings else None},
        "是否进入 Stage 2（需求解析）？",
    )


def run_stage_2_parse() -> dict[str, Any]:
    cases = load_test_cases()
    budget_hit = 0
    bedroom_hit = 0
    budget_total = 0
    bedroom_total = 0

    for c in cases:
        parsed = parse_user_query(c["raw_text"])
        target = c.get("target_params", {})

        if target.get("budget_max") is not None:
            budget_total += 1
            if parsed.budget_max == target.get("budget_max"):
                budget_hit += 1

        if target.get("bedrooms") is not None:
            bedroom_total += 1
            if parsed.bedrooms == target.get("bedrooms"):
                bedroom_hit += 1

    budget_acc = budget_hit / budget_total if budget_total else 1.0
    bedroom_acc = bedroom_hit / bedroom_total if bedroom_total else 1.0
    passed = budget_acc >= 0.8 and bedroom_acc >= 0.6

    return _stage_result(
        "stage_2",
        "需求解析",
        passed,
        {
            "budget_hit": f"{budget_hit}/{budget_total}",
            "bedroom_hit": f"{bedroom_hit}/{bedroom_total}",
            "budget_acc": round(budget_acc, 4),
            "bedroom_acc": round(bedroom_acc, 4),
        },
        "是否进入 Stage 3（匹配推荐）？",
    )


def run_stage_3_recommend() -> dict[str, Any]:
    cases = load_test_cases()
    non_empty = 0
    for c in cases:
        rec = recommend(c["raw_text"], top_k=3)
        if rec["recommendations"]:
            non_empty += 1

    rate = non_empty / len(cases) if cases else 0
    passed = rate >= 1.0

    return _stage_result(
        "stage_3",
        "匹配推荐",
        passed,
        {"non_empty_reco": f"{non_empty}/{len(cases)}", "non_empty_rate": round(rate, 4)},
        "是否进入 Stage 4（UI 展示）？",
    )


def run_stage_4_ui() -> dict[str, Any]:
    # 在无浏览器环境中仅做静态检查：app.py 是否具备关键展示模块
    app_file = ROOT / "app.py"
    text = app_file.read_text(encoding="utf-8")
    has_stage_log = "智能体执行日志" in text
    has_reason = "推荐理由" in text
    has_json_debug = "原始结果 JSON" in text

    passed = has_stage_log and has_reason and has_json_debug
    return _stage_result(
        "stage_4",
        "交互展示",
        passed,
        {
            "has_stage_log": has_stage_log,
            "has_reason": has_reason,
            "has_json_debug": has_json_debug,
            "screenshot_required": True,
            "screenshot_status": "pending_or_blocked_by_environment",
        },
        "是否进入 Stage 5（验收迭代）？",
    )


def run_stage_5_evaluation() -> dict[str, Any]:
    # 复用现有报告，如果存在则判定已形成基线
    baseline = ROOT / "data/next_step_report.json"
    exists = baseline.exists()
    payload = json.loads(baseline.read_text(encoding="utf-8")) if exists else {}
    passed = exists and payload.get("total_cases") == 20

    return _stage_result(
        "stage_5",
        "验收与迭代",
        passed,
        {
            "has_baseline_report": exists,
            "baseline_total_cases": payload.get("total_cases") if exists else None,
            "budget_match_count": payload.get("budget_match_count") if exists else None,
            "bedrooms_match_count": payload.get("bedrooms_match_count") if exists else None,
        },
        "是否进入下一里程碑（LLM 解析 / 向量召回 / 多站点）？",
    )


def main() -> None:
    stages = [
        run_stage_0_scope(),
        run_stage_1_crawl(),
        run_stage_2_parse(),
        run_stage_3_recommend(),
        run_stage_4_ui(),
        run_stage_5_evaluation(),
    ]

    all_passed = all(s["passed"] for s in stages)
    output = {"all_passed": all_passed, "stages": stages}
    REPORT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"report written: {REPORT_PATH}")
    for s in stages:
        status = "PASS" if s["passed"] else "FAIL"
        print(f"[{status}] {s['stage_id']} {s['stage_name']} -> {s['next_stage_hint']}")


if __name__ == "__main__":
    main()
