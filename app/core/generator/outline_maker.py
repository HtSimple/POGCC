import re

from app.prompts.templates import OUTLINE_TEMPLATE

_SECTION_RE = re.compile(r"^(\d+)\.\s+(.+)$")
_SUBSECTION_RE = re.compile(r"^([a-zA-Z])\.\s+(.+)$")
_GOAL_RE = re.compile(r"^核心目标[：:]\s*(.+)$")
_BULLETS_RE = re.compile(r"^要点[：:]\s*(.+)$")
_BULLET_ITEM_RE = re.compile(r"^[-•]\s+(.+)$")


def _split_bullets(text: str) -> list[str]:
    parts = re.split(r"[；;，,|]", text)
    return [p.strip() for p in parts if p.strip()]


def _default_page(title: str) -> dict:
    title = title.strip()
    return {
        "title": title,
        "goal": f"围绕「{title}」说明核心信息",
        "bullets": [title] if title else [],
    }


class OutlineMaker:

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    def generate_outline(self, topic, requirements=None, max_tokens=4096):
        prompt = self._build_prompt(topic, requirements)
        outline_text = self.llm_service.generate(prompt, max_tokens=max_tokens)
        print(f"\n生成的大纲文本: {outline_text}")

        outline = self._parse_outline(outline_text)

        if len(outline["sections"]) == 0:
            print("解析失败，返回默认大纲结构")
            outline = {
                "title": f"{topic}",
                "sections": [
                    {
                        "title": "1. 概述",
                        "subsections": [
                            _default_page("背景介绍"),
                            _default_page("研究意义"),
                        ],
                    },
                    {
                        "title": "2. 主要内容",
                        "subsections": [
                            _default_page("核心概念"),
                            _default_page("应用案例"),
                        ],
                    },
                    {
                        "title": "3. 总结展望",
                        "subsections": [
                            _default_page("总结"),
                            _default_page("未来发展"),
                        ],
                    },
                ],
            }

        return outline

    def _build_prompt(self, topic, requirements):
        prompt = OUTLINE_TEMPLATE
        prompt = prompt.replace("{topic}", topic)
        if requirements:
            prompt = prompt.replace("{requirements}", f"额外需求：{requirements}")
        else:
            prompt = prompt.replace("{requirements}", "")
        return prompt

    @staticmethod
    def _normalize_outline_line(line: str) -> str:
        text = line.strip()
        if text.startswith("- "):
            text = text[2:].strip()
        elif text.startswith("• "):
            text = text[2:].strip()
        elif text.startswith("-") and len(text) > 1 and not text.startswith("- "):
            text = text[1:].strip()
        return text

    def _parse_outline(self, outline_text):
        outline = {"title": "", "sections": []}
        lines = [ln for ln in outline_text.strip().split("\n") if ln.strip()]
        if not lines:
            return outline

        outline["title"] = self._normalize_outline_line(lines[0])
        current_section = None
        current_page = None

        def flush_page():
            nonlocal current_page
            if current_section is not None and current_page is not None:
                title = (current_page.get("title") or "").strip()
                if not current_page.get("goal"):
                    current_page["goal"] = f"围绕「{title}」说明核心信息"
                if not current_page.get("bullets"):
                    current_page["bullets"] = [title] if title else []
                current_section["subsections"].append(current_page)
            current_page = None

        for raw in lines[1:]:
            line = self._normalize_outline_line(raw)
            if not line:
                continue

            section_match = _SECTION_RE.match(line)
            if section_match:
                flush_page()
                if current_section:
                    outline["sections"].append(current_section)
                current_section = {
                    "title": section_match.group(2).strip(),
                    "subsections": [],
                }
                continue

            subsection_match = _SUBSECTION_RE.match(line)
            if subsection_match:
                flush_page()
                if current_section is None:
                    current_section = {"title": "未分组", "subsections": []}
                current_page = {
                    "title": subsection_match.group(2).strip(),
                    "goal": "",
                    "bullets": [],
                }
                continue

            if current_page is not None:
                goal_match = _GOAL_RE.match(line)
                if goal_match:
                    current_page["goal"] = goal_match.group(1).strip()
                    continue

                bullets_match = _BULLETS_RE.match(line)
                if bullets_match:
                    current_page["bullets"] = _split_bullets(bullets_match.group(1))
                    continue

                item_match = _BULLET_ITEM_RE.match(line)
                if item_match:
                    current_page.setdefault("bullets", []).append(item_match.group(1).strip())
                    continue

                # 兼容：缩进行「- 要点」未去前缀时
                raw_stripped = raw.strip()
                raw_bullet = re.match(r"^[-•]\s+(.+)$", raw_stripped)
                if raw_bullet and not _SECTION_RE.match(line) and not _SUBSECTION_RE.match(line):
                    current_page.setdefault("bullets", []).append(raw_bullet.group(1).strip())

        flush_page()
        if current_section:
            outline["sections"].append(current_section)

        # 兼容旧格式：subsections 仅为标题字符串
        for section in outline["sections"]:
            normalized = []
            for sub in section.get("subsections", []):
                if isinstance(sub, str):
                    normalized.append(_default_page(sub))
                elif isinstance(sub, dict):
                    title = str(sub.get("title", "") or "").strip()
                    goal = str(sub.get("goal", "") or "").strip()
                    bullets = sub.get("bullets") or []
                    if isinstance(bullets, str):
                        bullets = _split_bullets(bullets)
                    bullets = [str(b).strip() for b in bullets if str(b).strip()]
                    normalized.append({
                        "title": title,
                        "goal": goal or f"围绕「{title}」说明核心信息",
                        "bullets": bullets or ([title] if title else []),
                    })
            section["subsections"] = normalized

        return outline
