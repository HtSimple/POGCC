from app.utils.config import Config


class WebSearchService:

    def __init__(self, config=None):
        if config is None:
            config = Config()
        self._config = config
        self.api_key = self._config.get('tavily_api_key')
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("配置文件中未设置 tavily_api_key")
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(self, query, max_results=5, search_depth="advanced"):
        client = self._get_client()
        try:
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_raw_content=False,
            )
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                })
            return results
        except Exception as e:
            print(f"[WebSearch] 搜索失败: {e}")
            return []

    def search_and_extract(self, query, max_results=3):
        client = self._get_client()
        try:
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_raw_content=True,
            )
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "raw_content": item.get("raw_content", ""),
                })
            return results
        except Exception as e:
            print(f"[WebSearch] 搜索提取失败: {e}")
            return []
