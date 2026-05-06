import pytest
import os
from app.core.knowledge_agent import KnowledgeAgent
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService

class TestRAG:

    def setup_method(self):
        print("\n=== 设置测试环境 ===")
        self.llm_service = LLMService()
        self.web_search_service = WebSearchService()
        self.agent = KnowledgeAgent(
            llm_service=self.llm_service,
            web_search_service=self.web_search_service,
        )

    def test_process_query(self):
        print("\n1. 测试知识查询处理")
        test_queries = [
            "什么是PPT大纲智能生成与内容补全系统？",
        ]

        for i, query in enumerate(test_queries):
            print(f"\n测试查询 {i + 1}: {query}")
            result = self.agent.process_query(query)
            print(f"\n生成的回答: {result}")
            assert isinstance(result, str)
            assert len(result) > 0

    def test_document_upload(self):
        print("\n2. 测试文档上传功能")
        from app.core.faiss_db import FAISSDB
        from app.core.document_parser import DocumentParser

        vector_db = FAISSDB()
        document_parser = DocumentParser()
        test_doc_path = "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT 大纲智能生成与内容补全系统-项目章程-夏弘泰.docx"

        if os.path.exists(test_doc_path):
            try:
                doc_content = document_parser.parse(test_doc_path)
                doc_id = vector_db.add_document(doc_content)
                print(f"文档上传成功，文档ID: {doc_id}")
                assert doc_id >= 0
            except Exception as e:
                print(f"文档上传失败: {str(e)}")
                pytest.fail(f"文档上传失败: {str(e)}")
        else:
            print("测试文档不存在，跳过测试")
            pytest.skip("测试文档不存在")

if __name__ == "__main__":
    test = TestRAG()
    test.setup_method()
    test.test_process_query()
    test.test_document_upload()
    print("\n=== 知识 Agent 测试完成！ ===")
