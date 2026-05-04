from app.core.rag_agent.agent import RAGAgent
from app.core.document_parser import DocumentParser
from app.core.faiss_db import FAISSDB
from app.services.llm_service import LLMService
import os

if __name__ == "__main__":
    print("=== 测试双模型 RAG Agent 完整流程 ===")

    document_parser = DocumentParser()
    vector_db = FAISSDB()
    llm_service = LLMService()

    print("\n1. 解析文档并添加到向量数据库")
    test_documents = [
        "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT 大纲智能生成与内容补全系统-项目章程-夏弘泰.docx",
        "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT大纲智能生成与内容补全系统-POS-夏弘泰.pdf",
        "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT大纲智能生成与内容补全系统-夏弘泰.pdf"
    ]

    for doc_path in test_documents:
        if os.path.exists(doc_path):
            try:
                print(f"\n解析文档: {os.path.basename(doc_path)}")
                doc_content = document_parser.parse(doc_path)
                print(f"文档长度: {len(doc_content)} 字符")
                doc_id = vector_db.add_document(doc_content)
                print(f"添加到向量数据库，文档ID: {doc_id}")
            except Exception as e:
                print(f"处理文档失败: {str(e)}")
        else:
            print(f"文档不存在: {doc_path}")

    test_query = "什么是PPT大纲智能生成与内容补全系统？"

    test_steps = [
        ("qwen", "Qwen"),
        ("deepseek", "DeepSeek"),
        ("qwen", "Qwen（切换回）"),
    ]

    for i, (provider, label) in enumerate(test_steps):
        print(f"\n{'='*60}")
        print(f"测试 {i+1}: 使用 {label} 模型")
        print(f"{'='*60}")

        llm_service.switch_provider(provider)
        print(f"当前模型: {llm_service.provider_name}")

        rag_agent = RAGAgent(
            document_parser=document_parser,
            vector_db=vector_db,
            llm_service=llm_service
        )

        print(f"\n查询: {test_query}")
        result = rag_agent.process_query(test_query)

        is_error = result.startswith("[") and "]" in result[:30]
        status = "❌ 失败" if is_error else "✅ 成功"
        print(f"\n状态: {status}")
        print(f"回答长度: {len(result)} 字符")
        print(f"回答:\n{result}")

    print(f"\n{'='*60}")
    print("=== 双模型 RAG Agent 测试完成！ ===")
    print(f"{'='*60}")
