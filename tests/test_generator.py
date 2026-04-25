import pytest
from app.core.generator.outline_maker import OutlineMaker
from app.core.generator.content_expander import ContentExpander

class TestGenerator:
    """生成测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.outline_maker = OutlineMaker()
        self.content_expander = ContentExpander()
    
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