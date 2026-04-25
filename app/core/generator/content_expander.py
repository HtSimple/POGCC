from app.services.llm_service import LLMService
from app.prompts.templates import CONTENT_TEMPLATE

class ContentExpander:
    """内容补全器
    
    负责基于大纲节点扩写详细内容
    """
    
    def __init__(self):
        self.llm_service = LLMService()
    
    def expand_content(self, outline_node, context=None):
        """补全节点内容
        
        Args:
            outline_node (dict): 大纲节点
            context (str, optional): 上下文信息
            
        Returns:
            str: 补全的内容
        """
        # 构建提示
        prompt = self._build_prompt(outline_node, context)
        
        # 调用LLM生成内容
        content = self.llm_service.generate(prompt)
        
        return content
    
    def _build_prompt(self, outline_node, context):
        """构建内容补全提示
        
        Args:
            outline_node (dict): 大纲节点
            context (str): 上下文信息
            
        Returns:
            str: 构建好的提示
        """
        prompt = CONTENT_TEMPLATE
        
        # 提取节点标题
        if isinstance(outline_node, dict):
            node_title = outline_node.get("title", "")
        else:
            node_title = str(outline_node)
        
        prompt = prompt.replace("{node_title}", node_title)
        
        if context:
            prompt = prompt.replace("{context}", context)
        else:
            prompt = prompt.replace("{context}", "")
        
        return prompt