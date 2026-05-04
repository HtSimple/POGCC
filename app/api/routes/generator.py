from fastapi import APIRouter, Request
from app.schema.models import GenerateOutlineRequest, GenerateOutlineResponse, ExpandContentRequest, ExpandContentResponse
from app.core.generator.outline_maker import OutlineMaker
from app.core.generator.content_expander import ContentExpander

router = APIRouter(prefix="/api/generator", tags=["generator"])


def _get_outline_maker(request: Request) -> OutlineMaker:
    return OutlineMaker(llm_service=request.app.state.llm_service)


def _get_content_expander(request: Request) -> ContentExpander:
    return ContentExpander(llm_service=request.app.state.llm_service)


@router.post("/outline", response_model=GenerateOutlineResponse)
async def generate_outline(request: Request, body: GenerateOutlineRequest):
    try:
        outline_maker = _get_outline_maker(request)
        outline = outline_maker.generate_outline(body.topic, body.requirements)
        
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
async def expand_content(request: Request, body: ExpandContentRequest):
    try:
        content_expander = _get_content_expander(request)
        content = content_expander.expand_content(body.outline_node, body.context)
        
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