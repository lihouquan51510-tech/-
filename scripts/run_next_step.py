"""下一步工作：基于 20 条样本做解析与推荐闭环验证。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import load_test_cases, parse_user_query, recommend

REPORT_PATH = Path("data/next_step_report.json")


def main() -> None:
    test_cases = load_test_cases()
    rows = []
    for tc in test_cases:
        raw = tc["raw_text"]
        target = tc.get("target_params", {})
        parsed = parse_user_query(raw)
        rec = recommend(raw, top_k=3)

        hit_budget = True
        if target.get("budget_max") is not None:
            hit_budget = parsed.budget_max == target.get("budget_max")

        hit_bedrooms = True
        if target.get("bedrooms") is not None:
            hit_bedrooms = parsed.bedrooms == target.get("bedrooms")

        rows.append(
            {
                "id": tc["id"],
                "category": tc.get("category"),
                "raw_text": raw,
                "parse_hit_budget": hit_budget,
                "parse_hit_bedrooms": hit_bedrooms,
                "top1_title": rec["recommendations"][0]["title"] if rec["recommendations"] else None,
                "top1_score": rec["recommendations"][0]["score"] if rec["recommendations"] else None,
                "candidate_count": rec["total_candidates"],
                "filtered_count": rec["filtered_candidates"],
            }
        )

    summary = {
        "total_cases": len(rows),
        "budget_match_count": sum(1 for r in rows if r["parse_hit_budget"]),
        "bedrooms_match_count": sum(1 for r in rows if r["parse_hit_bedrooms"]),
        "rows": rows,
    }

    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report written: {REPORT_PATH}")
    print(
        f"budget_match={summary['budget_match_count']}/{summary['total_cases']}, "
        f"bedrooms_match={summary['bedrooms_match_count']}/{summary['total_cases']}"
    )


if __name__ == "__main__":
    main()
