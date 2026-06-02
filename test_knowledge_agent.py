"""手动端到端测试：依次切换模型，验证 KnowledgeAgent 的检索与回答流程。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.knowledge_agent import KnowledgeAgent
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService

if __name__ == "__main__":
    print("=== 测试知识 Agent（查询处理 + 网络搜索 + 生成回答） ===")

    llm_service = LLMService()
    web_search_service = WebSearchService()

    try:
        from app.rag.service import RetrievalService
        from app.utils.config import config

        # 本地 RAG 是可选增强；初始化失败时脚本仍可退化为网络检索测试。
        retrieval_service = RetrievalService(
            persist_dir="app/rag/data_index",
            embedding_model="app/rag/bge-small-en-v1.5",
        )
    except Exception:
        retrieval_service = None

    SAMPLE_PDF = Path(r"D:\杂物\大三下\软件经济\project\POGCC\app\rag\test_text.pdf")
    if retrieval_service is not None:
        pdf_path = SAMPLE_PDF if SAMPLE_PDF.is_file() else _ROOT / "app" / "rag" / "test_text.pdf"
        if pdf_path.is_file():
            ing = retrieval_service.batch_ingest([str(pdf_path.resolve())])[0]
            print(f"上传/入库: {ing}")
        else:
            print(f"未找到 PDF，跳过入库: {SAMPLE_PDF}")

    test_steps = [
        ("qwen", "Qwen"),
        ("deepseek", "DeepSeek"),
        ("qwen", "Qwen（切换回）"),
    ]

    test_query = "分点介绍流水线技术"

    # 复用同一个 LLMService，验证运行时模型切换是否能影响后续 Agent 调用。
    for i, (provider, label) in enumerate(test_steps):
        print(f"\n{'='*60}")
        print(f"测试 {i+1}: 使用 {label} 模型")
        print(f"{'='*60}")

        llm_service.switch_provider(provider)
        print(f"当前模型: {llm_service.provider_name}")

        agent = KnowledgeAgent(
            llm_service=llm_service,
            web_search_service=web_search_service,
            retrieval_service=retrieval_service,
        )

        print(f"\n查询: {test_query}")
        result = agent.process_query(test_query)

        is_error = result.startswith("[") and "]" in result[:30]
        status = "❌ 失败" if is_error else "✅ 成功"
        print(f"\n状态: {status}")
        print(f"回答长度: {len(result)} 字符")
        print(f"回答:\n{result}")

    print(f"\n{'='*60}")
    print("=== 知识 Agent 测试完成！ ===")
    print(f"{'='*60}")
