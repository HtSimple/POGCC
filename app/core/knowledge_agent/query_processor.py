class QueryProcessor:
    """查询预处理器，负责在进入检索前清洗并扩展用户问题。"""

    def process(self, query):
        """执行完整预处理流程，返回可直接用于检索和生成的查询文本。"""
        cleaned_query = self._clean_query(query)
        expanded_query = self._expand_query(cleaned_query)
        return expanded_query

    def _clean_query(self, query):
        """去除用户输入首尾空白，保留原始语义不做额外改写。"""
        query = query.strip()
        return query

    def _expand_query(self, query):
        """为查询追加回答要求。"""
        processed_query = f"{query}"
        return processed_query
