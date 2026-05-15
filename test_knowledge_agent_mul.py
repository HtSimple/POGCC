import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.knowledge_agent import KnowledgeAgent
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService


def _run_query(label: str, query: str, retrieval_service) -> tuple[str, str, str]:
    """单条查询：独立 LLM 实例固定 Qwen，避免多线程共用一个 LLMService。"""
    llm_service = LLMService()
    llm_service.switch_provider("qwen")
    web_search_service = WebSearchService()
    agent = KnowledgeAgent(
        llm_service=llm_service,
        web_search_service=web_search_service,
        retrieval_service=retrieval_service,
    )
    print(f"\n[并行] 开始: [{label}] {query!r}")
    result = agent.process_query(query)
    print(f"[并行] 结束: [{label}]")
    return label, query, result


if __name__ == "__main__":
    print("=== 测试知识 Agent：四条查询并行（仅 Qwen） ===")

    try:
        from app.rag.service import RetrievalService

        retrieval_service = RetrievalService(
            persist_dir="app/rag/data_index",
            embedding_model="app/rag/bge-small-en-v1.5",
        )
    except Exception:
        retrieval_service = None
    #这里改成自己路径
    SAMPLE_PDF = Path(r"D:\杂物\大三下\软件经济\project\POGCC\app\rag\test_text.pdf")
    if retrieval_service is not None:
        pdf_path = SAMPLE_PDF if SAMPLE_PDF.is_file() else _ROOT / "app" / "rag" / "test_text.pdf"
        if pdf_path.is_file():
            ing = retrieval_service.batch_ingest([str(pdf_path.resolve())])[0]
            print(f"上传/入库: {ing}")
        else:
            print(f"未找到 PDF，跳过入库: {SAMPLE_PDF}")

    tasks = [
        ("流水线", "分点介绍流水线技术"),
        ("指令级并行", "分点介绍指令级并行"),
        ("存储系统", "分点介绍存储系统"),
        ("输入输出系统", "分点介绍输入输出系统"),
    ]

    results: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(_run_query, label, query, retrieval_service): label
            for label, query in tasks
        }
        for fut in as_completed(future_map):
            label = future_map[fut]
            _, query, result = fut.result()
            results[label] = (query, result)

    for label, query in tasks:
        query, result = results[label]
        is_error = result.startswith("[") and "]" in result[:30]
        status = "❌ 失败" if is_error else "✅ 成功"
        print(f"\n{'='*60}")
        print(f"【{label}】{query}")
        print(f"状态: {status} | 回答长度: {len(result)} 字符")
        print(f"回答:\n{result}")

    print(f"\n{'='*60}")
    print("=== 并行知识 Agent 测试完成！ ===")
    print(f"{'='*60}")
