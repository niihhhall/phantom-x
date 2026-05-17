import traceback
import uuid
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings

# Import routers
from app.api.routes.auth import router as auth_router
from app.api.routes.accounts import router as accounts_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.leads import router as leads_router
from app.api.routes.scrape import router as scrape_router
from app.api.routes.ai import router as ai_router
from app.api.routes.inbox import router as inbox_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.webhooks import router as webhooks_router

api_app = FastAPI(
    title="Phantom-X",
    description="LinkedIn Automation & AI Outreach Platform Backend",
    version="1.0.0"
)

# CORS configuration
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@api_app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@api_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = str(uuid.uuid4())
    tb = traceback.format_exc()
    print(f"[{request_id}] Internal Server Error: {exc}\n{tb}")
    
    # Slack alerting on 500
    if settings.SLACK_WEBHOOK_URL:
        try:
            payload = {
                "text": f"[PHANTOM-X] [CRITICAL] Internal Server Error (ID: {request_id})\nError: {exc}\nTraceback: {tb[-1000:]}"
            }
            httpx.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=2.0)
        except Exception as slack_err:
            print(f"Failed to send Slack alert: {slack_err}")
            
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": request_id}
    )

# Include routers
api_app.include_router(auth_router)
api_app.include_router(accounts_router)
api_app.include_router(campaigns_router)
api_app.include_router(leads_router)
api_app.include_router(scrape_router)
api_app.include_router(ai_router)
api_app.include_router(inbox_router)
api_app.include_router(analytics_router)
api_app.include_router(webhooks_router)

@api_app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
