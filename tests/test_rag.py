import pytest
import os
from app.core.rag_agent.agent import RAGAgent
from app.core.faiss_db import FAISSDB
from app.core.document_parser import DocumentParser
from app.services.llm_service import LLMService

class TestRAG:
    
    def setup_method(self):
        print("\n=== 设置测试环境 ===")
        self.vector_db = FAISSDB()
        self.document_parser = DocumentParser()
        self.llm_service = LLMService()
        self.rag_agent = RAGAgent(
            document_parser=self.document_parser,
            vector_db=self.vector_db,
            llm_service=self.llm_service
        )
        self._load_test_documents()
    
    def _load_test_documents(self):
        """加载测试文档"""
        print("\n1. 解析文档并添加到向量数据库")
        
        # 测试文档路径
        test_documents = [
            "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT 大纲智能生成与内容补全系统-项目章程-夏弘泰.docx",
            "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT大纲智能生成与内容补全系统-POS-夏弘泰.pdf",
            "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT大纲智能生成与内容补全系统-夏弘泰.pdf"
        ]
        
        for doc_path in test_documents:
            if os.path.exists(doc_path):
                try:
                    print(f"\n解析文档: {os.path.basename(doc_path)}")
                    # 解析文档
                    doc_content = self.document_parser.parse(doc_path)
                    print(f"文档长度: {len(doc_content)} 字符")
                    
                    # 添加到向量数据库
                    doc_id = self.vector_db.add_document(doc_content)
                    print(f"添加到向量数据库，文档ID: {doc_id}")
                except Exception as e:
                    print(f"处理文档失败: {str(e)}")
            else:
                print(f"文档不存在: {doc_path}")
    
    def test_process_query(self):
        """测试查询处理"""
        print("\n2. 测试RAG agent查询处理")
        test_queries = [
            "什么是PPT大纲智能生成与内容补全系统？",
            "系统支持哪些文档格式？"
        ]
        
        for i, query in enumerate(test_queries):
            print(f"\n测试查询 {i + 1}: {query}")
            
            # 处理查询
            result = self.rag_agent.process_query(query)
            print(f"\n生成的回答: {result}")
            
            # 验证结果
            assert isinstance(result, str)
            assert len(result) > 0
    
    def test_document_upload(self):
        """测试文档上传"""
        print("\n3. 测试文档上传功能")
        # 测试文档上传功能
        test_doc_path = "d:\\NewStudy\\universityGrade3-2\\SEME\\POGCC\\documents\\PPT 大纲智能生成与内容补全系统-项目章程-夏弘泰.docx"
        
        if os.path.exists(test_doc_path):
            try:
                # 解析文档
                doc_content = self.document_parser.parse(test_doc_path)
                # 添加到向量数据库
                doc_id = self.vector_db.add_document(doc_content)
                print(f"文档上传成功，文档ID: {doc_id}")
                assert doc_id >= 0
            except Exception as e:
                print(f"文档上传失败: {str(e)}")
                pytest.fail(f"文档上传失败: {str(e)}")
        else:
            print("测试文档不存在，跳过测试")
            pytest.skip("测试文档不存在")

if __name__ == "__main__":
    # 直接运行测试
    test = TestRAG()
    test.setup_method()
    test.test_process_query()
    test.test_document_upload()
    print("\n=== RAG agent测试完成！ ===")