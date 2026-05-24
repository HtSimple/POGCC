from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[2]
QV_ROOT = CURRENT.parents[1]
OUTPUT_DIR = QV_ROOT / "outputs"
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import count_information_units, load_json, save_json


def extract_slide_texts(record: dict) -> list[str]:
    texts: list[str] = []

    page_content = record.get("page_content") or {}
    if isinstance(page_content, dict):
        for slide in page_content.get("slides", []) or []:
            text = "\n".join(
                [
                    str(slide.get("slideTitle", "")),
                    str(slide.get("coreMessage", "")),
                    "\n".join(slide.get("displayBullets", []) or []),
                    str(slide.get("speakerNotes", "")),
                ]
            )
            if text.strip():
                texts.append(text)

    # fallback: split answer by rough slide markers or paragraphs
    if not texts:
        answer = record.get("answer") or record.get("generated_text") or record.get("content") or ""
        parts = [p for p in str(answer).split("\n\n") if p.strip()]
        texts.extend(parts if parts else ([answer] if answer.strip() else []))

    return texts


def baseline_units_from_csv(path: str | None) -> float | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    vals = []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in ("units", "information_units", "info_units"):
                if key in row and row[key]:
                    vals.append(float(row[key]))
                    break
    return sum(vals) / len(vals) if vals else None


def evaluate_record(record: dict, manual_baseline_per_slide: float | None = None) -> dict:
    slide_texts = extract_slide_texts(record)
    slide_units = [count_information_units(t) for t in slide_texts]
    avg_units = sum(slide_units) / len(slide_units) if slide_units else 0.0

    density_ratio = None
    meets_80 = None
    if manual_baseline_per_slide and manual_baseline_per_slide > 0:
        density_ratio = avg_units / manual_baseline_per_slide
        meets_80 = density_ratio >= 0.8

    out = dict(record)
    out["information_density"] = {
        "slide_count": len(slide_texts),
        "units_per_slide": slide_units,
        "avg_units_per_slide": round(avg_units, 3),
        "manual_baseline_per_slide": manual_baseline_per_slide,
        "density_ratio": round(density_ratio, 4) if density_ratio is not None else None,
        "meets_80_percent_baseline": meets_80,
    }
    return out


def summarize(records: list[dict]) -> dict:
    vals = [
        r["information_density"]["avg_units_per_slide"]
        for r in records
        if r.get("information_density")
    ]
    ratios = [
        r["information_density"]["density_ratio"]
        for r in records
        if r.get("information_density", {}).get("density_ratio") is not None
    ]
    return {
        "record_count": len(records),
        "avg_units_per_slide": round(sum(vals) / len(vals), 3) if vals else 0.0,
        "avg_density_ratio": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "meets_80_percent_baseline_count": sum(
            1 for r in records if r.get("information_density", {}).get("meets_80_percent_baseline") is True
        ),
    }


def run(input_path: str, output_path: str, baseline: float | None, baseline_csv: str | None) -> None:
    data = load_json(input_path)
    records = data.get("records", data if isinstance(data, list) else [])

    manual_baseline = baseline
    if manual_baseline is None and baseline_csv:
        manual_baseline = baseline_units_from_csv(baseline_csv)

    evaluated = [evaluate_record(r, manual_baseline_per_slide=manual_baseline) for r in records]
    out = dict(data) if isinstance(data, dict) else {}
    out["records"] = evaluated
    out["information_density_summary"] = summarize(evaluated)
    save_json(output_path, out)
    print(f"Saved information density report: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate information density against manual baseline.")
    parser.add_argument(
        "--input",
        default=str(OUTPUT_DIR / "quality_validation_results.json"),
        help="Input JSON with generated records.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "information_density_report.json"),
        help="Output report path.",
    )
    parser.add_argument(
        "--baseline",
        type=float,
        default=None,
        help="Manual baseline information units per slide, e.g. 8.0.",
    )
    parser.add_argument(
        "--baseline-csv",
        default=None,
        help="CSV with a column named units/information_units/info_units.",
    )
    args = parser.parse_args()
    run(args.input, args.output, args.baseline, args.baseline_csv)


if __name__ == "__main__":
    main()
