import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.analyzer import full_analysis
from app.models import (
    AnalyzeRequest,
    AnalysisResult,
    SaveSiteRequest,
    SavedSiteResponse,
    UpdateNoteRequest,
)
from app import storage

app = FastAPI(
    title="Site Analyzer",
    description="Анализатор сайтов и их протоколов",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/saved", response_class=HTMLResponse)
async def saved_page(request: Request):
    return templates.TemplateResponse("saved.html", {"request": request})


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(req: AnalyzeRequest):
    result = await full_analysis(req.url)
    return result


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# --- Saved sites API ---

@app.get("/api/saved", response_model=list[SavedSiteResponse])
async def get_saved():
    return storage.get_all_saved()


@app.post("/api/saved", response_model=SavedSiteResponse)
async def save_site(req: SaveSiteRequest):
    entry = storage.save_site(req.url, req.analysis, req.note)
    return entry


@app.delete("/api/saved/{site_id}")
async def delete_saved(site_id: str):
    if not storage.delete_saved(site_id):
        raise HTTPException(status_code=404, detail="Сайт не найден")
    return {"status": "deleted"}


@app.patch("/api/saved/{site_id}/note")
async def update_note(site_id: str, req: UpdateNoteRequest):
    if not storage.update_note(site_id, req.note):
        raise HTTPException(status_code=404, detail="Сайт не найден")
    return {"status": "updated"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
