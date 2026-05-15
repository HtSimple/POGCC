"""
与 tests/test_generator.py 相同流程：大纲生成 + 内容补全，并把大模型返回打印到终端便于查看。

在项目根目录执行：
    python tests/test_generator_output.py

若用 pytest 看打印，需加 -s（否则输出会被捕获）：
    pytest tests/test_generator_output.py -v -s
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.generator.content_expander import ContentExpander
from app.core.generator.outline_maker import OutlineMaker
from app.services.llm_service import LLMService


def main() -> None:
    llm_service = LLMService()
    outline_maker = OutlineMaker(llm_service=llm_service)
    content_expander = ContentExpander(llm_service=llm_service)

    topic = "人工智能在教育中的应用"
    print(f"当前 LLM 提供者: {llm_service.provider_name}")
    print(f"\n{'='*60}\n【1】大纲生成 — 主题: {topic}\n{'='*60}")

    outline = outline_maker.generate_outline(topic)
    print(json.dumps(outline, ensure_ascii=False, indent=2))

    outline_node = {"title": "人工智能在教育中的应用现状"}
    print(f"\n{'='*60}\n【2】内容补全 — 节点: {outline_node}\n{'='*60}")

    expanded = content_expander.expand_content(outline_node)
    print(expanded)


if __name__ == "__main__":
    main()
