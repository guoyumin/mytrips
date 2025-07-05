from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
import uvicorn
from pathlib import Path

from api.gmail_router import router as gmail_router
from api.trips_router import router as trips_router
from api.auth_router import router as auth_router

app = FastAPI(
    title="MyTrips - Gmail Travel Analyzer",
    description="Analyze Gmail emails to extract and visualize travel information",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")
templates = Jinja2Templates(directory=str(frontend_path / "templates"))

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(gmail_router, prefix="/api/gmail", tags=["Gmail"])
app.include_router(trips_router, prefix="/api/trips", tags=["Trips"])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)