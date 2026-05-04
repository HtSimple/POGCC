from fastapi import APIRouter, Request
from app.schema.models import ModelInfoResponse, SwitchModelRequest, SwitchModelResponse

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/info", response_model=ModelInfoResponse)
async def get_model_info(request: Request):
    llm_service = request.app.state.llm_service
    return ModelInfoResponse(
        current_provider=llm_service.provider_name,
        available_providers=llm_service.get_available_providers()
    )


@router.post("/switch", response_model=SwitchModelResponse)
async def switch_model(request: Request, body: SwitchModelRequest):
    llm_service = request.app.state.llm_service
    try:
        new_provider = llm_service.switch_provider(body.provider)
        return SwitchModelResponse(
            success=True,
            current_provider=new_provider,
            message=f"已切换到 {new_provider} 模型"
        )
    except ValueError as e:
        return SwitchModelResponse(
            success=False,
            current_provider=llm_service.provider_name,
            message=str(e)
        )
