from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[2]
QV_ROOT = CURRENT.parents[1]
OUTPUT_DIR = QV_ROOT / "outputs"
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import load_json


def pick_summary(path: str | None, key: str) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json(p)
    return data.get(key, {})


def render_markdown(search_summary: dict, fact_summary: dict, density_summary: dict, output: str) -> str:
    lines = []
    lines.append("# POGCC 质量验证报告")
    lines.append("")
    lines.append(f"生成时间：{dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## 1. 网络搜索质量")
    if search_summary:
        for k, v in search_summary.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- 未提供搜索质量报告。")
    lines.append("")
    lines.append("## 2. 事实准确率")
    if fact_summary:
        for k, v in fact_summary.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- 未提供事实准确率报告。")
    lines.append("")
    lines.append("## 3. 信息密度")
    if density_summary:
        for k, v in density_summary.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- 未提供信息密度报告。")
    lines.append("")
    lines.append("## 4. 结论建议")
    lines.append("- 若事实准确率未达到预期，应增强页面级 evidence 召回和事实校验。")
    lines.append("- 若信息密度不足，应增加数据、案例、关键概念和可讲述备注。")
    lines.append("- 若搜索质量不足，应提升权威来源优先级和去重策略。")
    text = "\n".join(lines)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return text


def main():
    parser = argparse.ArgumentParser(description="Generate markdown validation report from JSON summaries.")
    parser.add_argument("--search-report", default=str(OUTPUT_DIR / "search_quality_report.json"))
    parser.add_argument("--fact-report", default=str(OUTPUT_DIR / "fact_precision_report.json"))
    parser.add_argument("--density-report", default=str(OUTPUT_DIR / "information_density_report.json"))
    parser.add_argument("--output", default=str(OUTPUT_DIR / "validation_report.md"))
    args = parser.parse_args()

    text = render_markdown(
        pick_summary(args.search_report, "search_quality_summary"),
        pick_summary(args.fact_report, "fact_precision_summary"),
        pick_summary(args.density_report, "information_density_summary"),
        args.output,
    )
    print(f"Saved validation report: {args.output}")


if __name__ == "__main__":
    main()
