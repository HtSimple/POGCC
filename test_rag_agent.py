from app.core.rag_agent.agent import RAGAgent
from app.core.document_parser import DocumentParser
from app.core.faiss_db import FAISSDB
import os

if __name__ == "__main__":
    print("=== 开始测试app文件夹下的实际功能 ===")
    
    # 创建真实的文档解析器和向量数据库
    document_parser = DocumentParser()
    vector_db = FAISSDB()
    
    # 解析示例文档并添加到向量数据库
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
                doc_content = document_parser.parse(doc_path)
                print(f"文档长度: {len(doc_content)} 字符")
                
                # 添加到向量数据库
                doc_id = vector_db.add_document(doc_content)
                print(f"添加到向量数据库，文档ID: {doc_id}")
            except Exception as e:
                print(f"处理文档失败: {str(e)}")
        else:
            print(f"文档不存在: {doc_path}")
    
    # 创建RAG agent
    print("\n2. 创建RAG agent")
    rag_agent = RAGAgent(document_parser=document_parser, vector_db=vector_db)
    
    # 测试查询处理（限制测试次数，避免过度消耗API配额）
    print("\n3. 测试RAG agent查询处理")
    test_queries = [
        "什么是PPT大纲智能生成与内容补全系统？",
        "系统支持哪些文档格式？"
    ]
    
    # 测试次数限制
    max_test_count = 2
    test_count = 0
    
    for query in test_queries:
        if test_count >= max_test_count:
            print("\n测试次数已达上限，停止测试")
            break
        
        print(f"\n测试查询 {test_count + 1}: {query}")
        
        # 处理查询
        result = rag_agent.process_query(query)
        print(f"\n生成的回答: {result}")
        
        test_count += 1
    
    print("\n=== RAG agent测试完成！ ===")
