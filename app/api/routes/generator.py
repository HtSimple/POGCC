from fastapi import APIRouter
from app.schema.models import GenerateOutlineRequest, GenerateOutlineResponse, ExpandContentRequest, ExpandContentResponse
from app.core.generator.outline_maker import OutlineMaker
from app.core.generator.content_expander import ContentExpander

router = APIRouter(prefix="/api/generator", tags=["generator"])

# 创建生成器实例
outline_maker = OutlineMaker()
content_expander = ContentExpander()

@router.post("/outline", response_model=GenerateOutlineResponse)
async def generate_outline(request: GenerateOutlineRequest):
    """生成PPT大纲"""
    try:
        # 生成大纲
        outline = outline_maker.generate_outline(request.topic, request.requirements)
        
        return GenerateOutlineResponse(
            success=True,
            outline=outline,
            message="大纲生成成功"
        )
    except Exception as e:
        return GenerateOutlineResponse(
            success=False,
            outline={"title": "", "sections": []},
            message=f"大纲生成失败: {str(e)}"
        )

@router.post("/content", response_model=ExpandContentResponse)
async def expand_content(request: ExpandContentRequest):
    """补全PPT内容"""
    try:
        # 补全内容
        content = content_expander.expand_content(request.outline_node, request.context)
        
        return ExpandContentResponse(
            success=True,
            content=content,
            message="内容补全成功"
        )
    except Exception as e:
        return ExpandContentResponse(
            success=False,
            content="",
            message=f"内容补全失败: {str(e)}"
        )