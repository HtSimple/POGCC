from app.utils.config import Config


class WebSearchService:
    """Tavily search adapter. Search usage is intentionally outside LLM cost control."""

    def __init__(self, config=None):
        self._config = config or Config()
        self.api_key = self._config.get("tavily_api_key")
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("tavily_api_key is not configured")
            from tavily import TavilyClient

            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(self, query, max_results=5, search_depth="advanced"):
        try:
            response = self._get_client().search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_raw_content=False,
            )
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                }
                for item in response.get("results", [])
            ]
        except Exception as exc:
            print(f"[WebSearch] Search failed: {exc}")
            return []

    def search_and_extract(self, query, max_results=3):
        try:
            response = self._get_client().search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_raw_content=True,
            )
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "raw_content": item.get("raw_content", ""),
                }
                for item in response.get("results", [])
            ]
        except Exception as exc:
            print(f"[WebSearch] Search and extract failed: {exc}")
            return []
