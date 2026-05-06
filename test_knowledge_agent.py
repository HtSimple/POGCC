from app.core.knowledge_agent import KnowledgeAgent
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService

if __name__ == "__main__":
    print("=== 测试知识 Agent（查询处理 + 网络搜索 + 生成回答） ===")

    llm_service = LLMService()
    web_search_service = WebSearchService()

    test_steps = [
        ("qwen", "Qwen"),
        ("deepseek", "DeepSeek"),
        ("qwen", "Qwen（切换回）"),
    ]

    test_query = "人工智能在医疗领域的应用"

    for i, (provider, label) in enumerate(test_steps):
        print(f"\n{'='*60}")
        print(f"测试 {i+1}: 使用 {label} 模型")
        print(f"{'='*60}")

        llm_service.switch_provider(provider)
        print(f"当前模型: {llm_service.provider_name}")

        agent = KnowledgeAgent(
            llm_service=llm_service,
            web_search_service=web_search_service,
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
