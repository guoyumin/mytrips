from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import logging
from pathlib import Path

from api.email_router import router as email_router
from api.auth_router import router as auth_router
from api.content_router import router as content_router
from api.trips_router import router as trips_router
from lib.config_manager import config_manager

# Configure logging from config
log_level = getattr(logging, config_manager.get_log_level().upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="MyTrips - Gmail Travel Analyzer",
    description="Analyze Gmail emails to extract and visualize travel information",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")

# Include API routes
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(email_router, prefix="/api/emails", tags=["Email Management"])
app.include_router(content_router, prefix="/api/content", tags=["Email Content"])
app.include_router(trips_router, prefix="/api/trips", tags=["Trip Management"])

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend application"""
    frontend_file = frontend_path / "index.html"
    if frontend_file.exists():
        return HTMLResponse(content=frontend_file.read_text(), status_code=200)
    else:
        return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)