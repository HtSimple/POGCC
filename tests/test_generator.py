import pytest
from app.core.generator.outline_maker import OutlineMaker
from app.core.generator.content_expander import ContentExpander
from app.services.llm_service import LLMService

class TestGenerator:
    
    def setup_method(self):
        self.llm_service = LLMService()
        self.outline_maker = OutlineMaker(llm_service=self.llm_service)
        self.content_expander = ContentExpander(llm_service=self.llm_service)
    
    def test_generate_outline(self):
        """测试大纲生成"""
        topic = "人工智能在教育中的应用"
        result = self.outline_maker.generate_outline(topic)
        assert isinstance(result, dict)
        assert "title" in result
        assert "sections" in result
        assert len(result["sections"]) > 0
    
    def test_expand_content(self):
        """测试内容补全"""
        outline_node = {"title": "人工智能在教育中的应用现状"}
        result = self.content_expander.expand_content(outline_node)
        assert isinstance(result, str)
        assert len(result) > 0