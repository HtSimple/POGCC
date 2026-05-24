from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean


SCORE_FIELDS = [
    "structure_score",
    "logic_score",
    "content_depth_score",
    "fact_trust_score",
    "ppt_usability_score",
]


def read_rows(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{path} not found. Create a CSV with columns: "
            "case_id,user_id,structure_score,logic_score,content_depth_score,"
            "fact_trust_score,ppt_usability_score,needs_major_rewrite,comment"
        )
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def analyze(rows: list[dict]) -> dict:
    result = {"sample_count": len(rows), "averages": {}, "pass_flags": {}}

    for field in SCORE_FIELDS:
        vals = [to_float(r.get(field)) for r in rows]
        vals = [v for v in vals if v is not None]
        avg = mean(vals) if vals else 0.0
        result["averages"][field] = round(avg, 3)
        result["pass_flags"][field + "_gte_4"] = avg >= 4.0

    rewrite_values = [
        str(r.get("needs_major_rewrite", "")).strip().lower()
        for r in rows
        if str(r.get("needs_major_rewrite", "")).strip()
    ]
    yes_values = {"yes", "y", "true", "1", "是", "需要"}
    rewrite_count = sum(1 for x in rewrite_values if x in yes_values)
    result["major_rewrite_count"] = rewrite_count
    result["major_rewrite_rate"] = round(rewrite_count / max(1, len(rows)), 4)

    comments = [r.get("comment", "").strip() for r in rows if r.get("comment", "").strip()]
    result["comments"] = comments[:20]
    return result


def write_json(path: str, data: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Analyze UAT score CSV.")
    parser.add_argument("--input", default="testing/uat/uat_results.csv")
    parser.add_argument("--output", default="testing/uat/uat_summary.json")
    args = parser.parse_args()

    rows = read_rows(args.input)
    result = analyze(rows)
    write_json(args.output, result)
    print(f"Saved UAT summary: {args.output}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
