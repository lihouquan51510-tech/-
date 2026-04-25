from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import recommend


def main() -> None:
    query = "预算 6000，两室，历下区，地铁近。"
    result = recommend(query, top_k=3, use_llm_parser=True)
    stage_logs = result.get("stage_logs", [])
    print(json.dumps(stage_logs, ensure_ascii=False, indent=2))
    print("recommendation_count=", len(result.get("recommendations", [])))


if __name__ == "__main__":
    main()
