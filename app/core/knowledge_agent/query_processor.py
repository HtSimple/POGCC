class QueryProcessor:

    def process(self, query):
        cleaned_query = self._clean_query(query)
        expanded_query = self._expand_query(cleaned_query)
        return expanded_query

    def _clean_query(self, query):
        query = query.strip()
        return query

    def _expand_query(self, query):
        processed_query = f"{query} 用大概200字左右描述(这是处理查询函数加的一句话)"
        return processed_query
