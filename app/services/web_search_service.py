from app.utils.config import Config


class WebSearchService:
    """Tavily 网络搜索服务封装，统一返回项目内部使用的结果字段。"""

    def __init__(self, config=None):
        """读取 Tavily API Key，并延迟到首次搜索时再创建客户端。"""
        if config is None:
            config = Config()
        self._config = config
        self.api_key = self._config.get('tavily_api_key')
        self._client = None

    def _get_client(self):
        """懒加载 TavilyClient，避免服务初始化阶段就强依赖网络搜索配置。"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("配置文件中未设置 tavily_api_key")
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(self, query, max_results=5, search_depth="advanced"):
        """执行普通网络搜索，返回标题、URL 和摘要内容列表。"""
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
        """执行带原文抽取的搜索，在普通字段外额外返回 raw_content。"""
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
