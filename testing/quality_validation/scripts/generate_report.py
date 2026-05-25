import json

PATH = r"E:\code\project\Software Engineering Management and Economics_project\POGCC\testing\quality_validation\outputs\quality_validation_results.json"
OUT = r"E:\code\project\Software Engineering Management and Economics_project\POGCC\testing\quality_validation\docs\quality_validation_report.md"


def main():
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    lines.append("# 质量验证测试报告")
    lines.append("")
    lines.append("**数据来源：** quality_validation_results.json")
    lines.append("")
    lines.append("## 一、总体概览")
    lines.append("")
    lines.append(f"- 生成时间：{data.get('generated_at','')}")
    lines.append(f"- 主题数量：{data.get('topic_count','')}")
    lines.append(f"- 搜索深度：{data.get('search_depth','')}")
    lines.append(f"- 每主题结果数：{data.get('max_results','')}")
    lines.append(f"- LLM 提供方：{data.get('llm_provider','')}")
    lines.append("")
    lines.append("评分区间：0-5 分（0=无效，5=优秀）。")
    lines.append("")
    lines.append("## 二、分主题结果")
    lines.append("")

    for rec in data.get("records", []):
        topic = rec.get("topic", "")
        scores = rec.get("scores", {})
        fc = rec.get("fact_check", {})
        cov = rec.get("coverage_checklist", [])

        lines.append(f"### {topic}")
        lines.append("")
        lines.append("**搜索质量评分**")
        lines.append("")
        lines.append(f"- 相关性：{scores.get('relevance')} / 5")
        lines.append(f"- 权威性：{scores.get('authority')} / 5")
        lines.append(f"- 覆盖度：{scores.get('coverage')} / 5")
        lines.append(f"- 多样性：{scores.get('diversity')} / 5")
        lines.append(f"- 去重率：{scores.get('redundancy')} / 5")
        lines.append("")
        lines.append("**问答质量评分**")
        lines.append("")
        lines.append(f"- 完整性：{scores.get('answer_completeness')} / 5")
        lines.append(f"- 结构化：{scores.get('answer_structure')} / 5")
        lines.append(f"- 证据一致性：{scores.get('answer_alignment')} / 5")
        lines.append(f"- 不确定性标注：{scores.get('answer_uncertainty')} / 5")
        lines.append("")
        lines.append("**关键点覆盖情况**")
        lines.append("")
        for item in cov:
            point = item.get("point", "")
            covered = item.get("covered")
            ev = item.get("evidence", "")
            flag = "是" if covered else "否"
            lines.append(f"- {point}：{flag}（证据：{ev}）")
        lines.append("")
        lines.append("**事实一致性统计**")
        lines.append("")
        lines.append(f"- Supported：{fc.get('supported',0)}")
        lines.append(f"- Insufficient：{fc.get('insufficient',0)}")
        lines.append(f"- Contradicted：{fc.get('contradicted',0)}")
        lines.append(f"- No Evidence：{fc.get('no_evidence',0)}")
        lines.append("")
        claims = fc.get("claims", [])
        if claims:
            lines.append("**事实声明与判定（摘录）**")
            lines.append("")
            for c in claims:
                lines.append(f"- {c.get('claim')} → {c.get('verdict')}（{c.get('evidence','')}）")
            lines.append("")
        note = rec.get("notes", "")
        if note:
            lines.append("**备注**")
            lines.append("")
            lines.append(f"- {note}")
            lines.append("")

    lines.append("## 三、总体结论与建议")
    lines.append("")
    lines.append("- 搜索结果整体相关性与覆盖度较高，多来源覆盖较充分。")
    lines.append("- 问答质量在多数主题上表现良好，但部分主题包含未在摘要中出现的具体数据。")
    lines.append("- 建议在生成端加强对数值型结论的来源校验，或显式标注“不确定/需核验”。")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("Saved report:", OUT)


if __name__ == "__main__":
    main()
