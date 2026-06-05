from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.api_cost_service import PROVIDERS, get_api_cost_service


router = APIRouter(prefix="/api/cost", tags=["cost"])


class ApiLimitUpdate(BaseModel):
    call_limit: Optional[int] = Field(None, ge=1)
    token_limit: Optional[int] = Field(None, ge=1)
    cost_limit: Optional[float] = Field(None, gt=0)


class ApiUsageReset(BaseModel):
    provider: Optional[str] = None


@router.get("/usage")
async def get_api_usage():
    """Return persisted usage, configured limits, and recent external API calls."""
    return get_api_cost_service().get_summary()


@router.put("/limits/{provider}")
async def update_api_limits(provider: str, body: ApiLimitUpdate):
    """Replace limits for one provider. Null values mean unlimited."""
    if provider not in PROVIDERS:
        return {"success": False, "message": f"Unsupported API provider: {provider}"}
    usage = get_api_cost_service().update_limits(
        provider,
        call_limit=body.call_limit,
        token_limit=body.token_limit,
        cost_limit=body.cost_limit,
    )
    return {"success": True, "provider": provider, "usage": usage}


@router.post("/reset")
async def reset_api_usage(body: ApiUsageReset):
    """Reset counters while preserving configured limits."""
    if body.provider is not None and body.provider not in PROVIDERS:
        return {
            "success": False,
            "message": f"Unsupported API provider: {body.provider}",
        }
    get_api_cost_service().reset_usage(body.provider)
    return {"success": True, "provider": body.provider}
