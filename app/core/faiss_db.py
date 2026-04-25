import faiss
import numpy as np
import os

class FAISSDB:
    """FAISS向量数据库
    
    负责文档向量的存储和检索
    """
    
    def __init__(self, index_path='./faiss_index'):
        """初始化FAISS数据库
        
        Args:
            index_path (str): 索引存储路径
        """
        self.index_path = index_path
        self.index = None
        self.documents = []
        self._load_index()
    
    def _load_index(self):
        """加载索引
        """
        try:
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
            else:
                # 如果索引文件不存在，创建新索引
                self.index = faiss.IndexFlatL2(768)  # 假设使用768维向量
        except Exception as e:
            print(f"加载索引失败: {e}")
            # 创建新索引
            self.index = faiss.IndexFlatL2(768)  # 假设使用768维向量
    
    def _save_index(self):
        """保存索引
        """
        try:
            faiss.write_index(self.index, self.index_path)
        except Exception as e:
            print(f"保存索引失败: {e}")
    
    def add_document(self, doc, embedding=None):
        """添加文档
        
        Args:
            doc (str): 文档内容
            embedding (list, optional): 文档向量
            
        Returns:
            int: 文档ID
        """
        if embedding is None:
            # 如果没有提供向量，使用随机向量（实际项目中应该使用真实的嵌入模型）
            embedding = np.random.rand(768).astype(np.float32)
        else:
            embedding = np.array(embedding).astype(np.float32)
        
        # 添加到索引
        self.index.add(np.array([embedding]))
        
        # 存储文档内容
        doc_id = len(self.documents)
        self.documents.append(doc)
        
        # 保存索引
        self._save_index()
        
        return doc_id
    
    def search(self, query, top_k=3):
        """搜索相关文档
        
        Args:
            query (str): 查询文本
            top_k (int): 返回的文档数量
            
        Returns:
            list: 相关文档列表
        """
        # 实际项目中应该使用真实的嵌入模型生成查询向量
        query_embedding = np.random.rand(768).astype(np.float32)
        
        # 搜索
        distances, indices = self.index.search(np.array([query_embedding]), top_k)
        
        # 获取相关文档
        relevant_docs = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.documents):
                relevant_docs.append(self.documents[idx])
        
        return relevant_docs
    
    def get_document(self, doc_id):
        """获取文档
        
        Args:
            doc_id (int): 文档ID
            
        Returns:
            str: 文档内容
        """
        if 0 <= doc_id < len(self.documents):
            return self.documents[doc_id]
        return None