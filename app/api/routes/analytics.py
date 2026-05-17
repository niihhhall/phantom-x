from typing import Dict, Any
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.database import get_analytics_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("", response_model=Dict[str, Any])
async def api_get_analytics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get aggregated SaaS metrics for the workspace dashboard (F-14).
    Combines campaign metrics, CRM pipeline stages, and active account safety indexes.
    """
    workspace_id = current_user["workspace_id"]
    return await get_analytics_summary(workspace_id)
