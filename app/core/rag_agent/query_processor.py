class QueryProcessor:
    """查询处理器
    
    负责处理用户查询，包括查询清洗、查询扩展等
    """
    
    def process(self, query):
        """处理查询
        
        Args:
            query (str): 原始查询文本
            
        Returns:
            str: 处理后的查询文本
        """
        # 1. 清洗查询
        cleaned_query = self._clean_query(query)
        
        # 2. 扩展查询（可选）
        expanded_query = self._expand_query(cleaned_query)
        
        return expanded_query
    
    def _clean_query(self, query):
        """清洗查询
        
        Args:
            query (str): 原始查询文本
            
        Returns:
            str: 清洗后的查询文本
        """
        # 去除首尾空格
        query = query.strip()
        
        # 其他清洗操作可以根据需要添加
        
        return query
    
    def _expand_query(self, query):
        """扩展查询
        
        Args:
            query (str): 清洗后的查询文本
            
        Returns:
            str: 扩展后的查询文本
        """
        # 简单的查询扩展，实际项目中可能需要更复杂的扩展策略
        # 例如，添加相关词汇、同义词等
        
        # 添加标识性的话，以便直观看到处理前后的区别
        processed_query = f"{query} 这是处理查询函数加的一句话"
        return processed_query