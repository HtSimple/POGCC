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

        if isinstance(outline_node, dict):
            node_title = str(outline_node.get("title", "") or "").strip()
            section = str(outline_node.get("section", "") or "").strip()
            goal = str(outline_node.get("goal", "") or "").strip()
            bullets_raw = outline_node.get("bullets", [])
            if isinstance(bullets_raw, list):
                bullets = "\n".join(f"- {str(b).strip()}" for b in bullets_raw if str(b).strip())
            else:
                bullets = str(bullets_raw).strip()
        else:
            node_title = str(outline_node).strip()
            section = ""
            goal = ""
            bullets = ""

        if not bullets:
            bullets = "（无）"
        if not section:
            section = "（无）"
        if not goal:
            goal = "（无）"

        prompt = prompt.replace("{node_title}", node_title or "（无）")
        prompt = prompt.replace("{section}", section)
        prompt = prompt.replace("{goal}", goal)
        prompt = prompt.replace("{bullets}", bullets)
        prompt = prompt.replace("{context}", (context or "").strip() or "（无）")

        return prompt