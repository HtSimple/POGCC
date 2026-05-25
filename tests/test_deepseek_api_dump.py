"""
测试同济 DeepSeek 网关，打印完整 HTTP 响应（含 reasoning / content 等所有字段）。

在项目根目录执行：
    python tests/test_deepseek_api_dump.py
    python tests/test_deepseek_api_dump.py "用三句话介绍计算机原理中的Cache"
    python tests/test_deepseek_api_dump.py --model DeepSeek-R1 --max-tokens 2048
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.config import Config

DEFAULT_URL = "https://llmapi.tongji.edu.cn/v1/chat/completions"
DEFAULT_PROMPT = "1+1等于几？请简短回答，并说明你是如何得出答案的。"


def dump_json(title: str, data: object) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_message_fields(message: dict) -> None:
    print("\n" + "-" * 72)
    print("message 字段明细")
    print("-" * 72)
    for key, value in message.items():
        print(f"\n>>> [{key}]")
        if isinstance(value, str):
            print(value if value else "(empty)")
        else:
            print(json.dumps(value, ensure_ascii=False, indent=2))


def call_deepseek(
    prompt: str,
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    api_key: str,
    url: str,
) -> None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    dump_json("请求 payload", payload)

    print("\n正在请求 API ...")
    resp = requests.post(url, headers=headers, json=payload, timeout=300)

    print(f"\nHTTP status: {resp.status_code}")
    print(f"Response headers: {dict(resp.headers)}")

    if resp.status_code != 200:
        print("\n[错误] 响应 body:")
        print(resp.text[:8000])
        return

    try:
        result = resp.json()
    except json.JSONDecodeError:
        print("\n[错误] 响应不是 JSON:")
        print(resp.text[:8000])
        return

    dump_json("完整响应 JSON", result)

    choices = result.get("choices") or []
    if not choices:
        print("\n[警告] choices 为空")
        return

    choice0 = choices[0]
    dump_json("choices[0]", choice0)

    message = choice0.get("message") or {}
    print_message_fields(message)

    reasoning = message.get("reasoning") or ""
    content = message.get("content") or ""
    finish_reason = choice0.get("finish_reason", "")

    print("\n" + "=" * 72)
    print("汇总")
    print("=" * 72)
    print(f"finish_reason : {finish_reason}")
    print(f"reasoning 长度: {len(reasoning)} 字符")
    print(f"content 长度  : {len(content)} 字符")
    if reasoning:
        print("\n【思考过程 reasoning】\n")
        print(reasoning)
    else:
        print("\n（无 reasoning 字段或为空）")

    print("\n【最终回答 content】\n")
    print(content if content else "(empty)")

    usage = result.get("usage")
    if usage:
        dump_json("token usage", usage)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump full DeepSeek API response from Tongji gateway")
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT, help="User prompt")
    parser.add_argument("--model", default="DeepSeek-R1", help="Model name")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    cfg = Config(str(ROOT / "config.json"))
    api_key = cfg.get("deepseek_api_key")
    if not api_key:
        print("[error] config.json 中未配置 deepseek_api_key")
        return 1

    call_deepseek(
        args.prompt,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        api_key=api_key,
        url=args.url,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
