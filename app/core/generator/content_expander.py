from app.prompts.templates import CONTENT_TEMPLATE

class ContentExpander:
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
    
    def expand_content(self, outline_node, context=None, max_tokens=4096):
        prompt = self._build_prompt(outline_node, context)
        content = self.llm_service.generate(prompt, max_tokens=max_tokens)
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