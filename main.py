# backend/main.py

import logging
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()  # Load .env file for email config etc.

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from topview.api.router import router as topview_router
from sideview.router import router as sideview_router
from chat.router import router as chat_router
from expert.router import router as expert_router
from api.drone_router import router as drone_router
from api.farmer_router import router as farmer_router
from api.survey_router import router as survey_router
from api.history_router import router as history_router
from utils.security import RateLimiter, SecurityHeaders

# Deekshith - Survey Orchestration (Database-first with file fallback)
from Deekshith.survey.router import router as deekshith_survey_router
from Deekshith.topview_link.router import router as deekshith_topview_router
from Deekshith.sideview_link.router import router as deekshith_sideview_router
from Deekshith.dashboard.router import router as deekshith_dashboard_router
from Deekshith.map.router import router as deekshith_map_router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

# Initialize rate limiter (60 requests per minute per IP)
rate_limiter = RateLimiter(requests_per_minute=60)

app = FastAPI(
    title="Coconut Tree Analyzer Backend",
    description="FastAPI backend for drone-based tree surveying and health analysis",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    for header, value in SecurityHeaders.get_headers().items():
        response.headers[header] = value
    return response

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limit requests per IP address."""
    # Skip rate limiting for health check
    if request.url.path == "/health":
        return await call_next(request)
    
    client_ip = request.client.host if request.client else "unknown"
    
    if rate_limiter.is_rate_limited(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."}
        )
    
    return await call_next(request)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    start_time = datetime.utcnow()
    request_id = request.headers.get("X-Request-ID", "N/A")
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info(f"Request started: {request.method} {request.url.path} [ID: {request_id}] [IP: {client_ip}]")
    
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Request failed: {str(e)}", exc_info=True)
        raise
    
    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
    logger.info(f"Request completed: {request.method} {request.url.path} - {response.status_code} ({duration_ms:.2f}ms) [ID: {request_id}]")
    
    return response

# Include routers
app.include_router(topview_router)
app.include_router(sideview_router)
app.include_router(chat_router)
app.include_router(expert_router)
app.include_router(drone_router)
app.include_router(farmer_router)
app.include_router(survey_router)
app.include_router(history_router)

# Deekshith - Survey Orchestration routers (Database-first)
app.include_router(deekshith_survey_router)
app.include_router(deekshith_topview_router)
app.include_router(deekshith_sideview_router)
app.include_router(deekshith_dashboard_router)
app.include_router(deekshith_map_router)

# Mount static files for serving survey storage (images, etc.)
storage_path = Path(__file__).parent / "Deekshith" / "storage"
if storage_path.exists():
    app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancers and orchestrators.
    Returns service status, timestamp, and model availability.
    """
    try:
        topview_loaded = False
        sideview_loaded = False
        try:
            from topview.api.router import model as topview_model
            topview_loaded = topview_model is not None and hasattr(topview_model, 'model')
        except Exception:
            pass
        try:
            from sideview.model import SideViewModel
            svm = SideViewModel.get_instance()
            sideview_loaded = svm.model is not None
        except Exception:
            pass

        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "models": {
                    "topview_yolo": "loaded" if topview_loaded else "not_loaded",
                    "sideview_tensorflow": "loaded" if sideview_loaded else "not_loaded"
                }
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API documentation link."""
    return {
        "message": "Coconut Tree Analyzer Backend",
        "docs": "/docs",
        "openapi_schema": "/openapi.json",
        "health": "/health"
    }