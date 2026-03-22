#https://tracer-9ugr.onrender.com/

import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, Response, RedirectResponse

try:
    from app.pdf_report import generate_analysis_pdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.analyzer import full_analysis
from app import cache

BASE_DIR = Path(__file__).resolve().parent
from pydantic import BaseModel

from app.models import (
    AnalyzeRequest,
    AnalysisResult,
    SaveSiteRequest,
    SavedSiteResponse,
    UpdateNoteRequest,
)
from app import storage
from app.translations import get_translations, SUPPORTED_LANGS, DEFAULT_LANG

app = FastAPI(
    title="Site Analyzer",
    description="Анализатор сайтов и их протоколов",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False)


def get_lang(request: Request) -> str:
    """Get language from cookie, default to ru."""
    lang = request.cookies.get("lang", DEFAULT_LANG)
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def template_context(request: Request) -> dict:
    """Common context for all page templates."""
    lang = get_lang(request)
    return {"request": request, "t": get_translations(lang), "lang": lang, "t_js": get_translations(lang)}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", template_context(request))


@app.head("/")
async def index_head():
    """Render и другие прокси часто проверяют HEAD / — без этого будет 405."""
    return Response(status_code=200)


@app.get("/saved", response_class=HTMLResponse)
async def saved_page(request: Request):
    return templates.TemplateResponse("saved.html", template_context(request))


@app.head("/saved")
async def saved_head():
    return Response(status_code=200)


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", template_context(request))


@app.head("/history")
async def history_head():
    return Response(status_code=200)


@app.get("/api/set-lang")
async def set_lang(lang: str, request: Request):
    """Set language cookie and redirect back."""
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    referer = request.headers.get("referer", "/")
    response = RedirectResponse(url=referer, status_code=302)
    response.set_cookie(key="lang", value=lang, max_age=365 * 24 * 3600, path="/")
    return response


class ExportPdfRequest(BaseModel):
    analysis: dict


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(req: AnalyzeRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    allowed, remaining = cache.check_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов. Попробуйте через минуту.",
        )

    cached = cache.get_cached_analysis(req.url)
    if cached:
        cached["_cached"] = True
        return cached

    result = await full_analysis(req.url)
    err = getattr(result, "error", None) or (result.get("error") if isinstance(result, dict) else None)
    if not err:
        url = getattr(result, "url", None) or (result.get("url") if isinstance(result, dict) else "")
        ip = getattr(result, "ip_address", None) or (result.get("ip_address") if isinstance(result, dict) else "")
        storage.add_scan_to_history(url, ip or "")
        result_dict = result.model_dump() if hasattr(result, "model_dump") else result
        cache.set_cached_analysis(req.url, result_dict)
    return result


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "redis": cache.get_info(),
    }


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


# --- История сканирований API ---

@app.get("/api/history")
async def get_history(limit: int = 50):
    return storage.get_scan_history(limit=limit)


@app.delete("/api/history")
async def clear_history():
    storage.clear_history()
    return {"status": "cleared"}


@app.delete("/api/history/{index}")
async def delete_history_entry(index: int):
    if not storage.delete_history_entry(index):
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return {"status": "deleted"}


@app.post("/api/export/json")
async def export_json(req: ExportPdfRequest):
    """Возвращает результаты анализа как JSON-файл для скачивания."""
    url = req.analysis.get("url", "site")
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in url)[:50]
    filename = f"analysis_{safe_name}.json"
    content = json.dumps(req.analysis, ensure_ascii=False, indent=2)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.post("/api/export/pdf")
async def export_pdf(req: ExportPdfRequest):
    """Генерирует и возвращает PDF-отчёт по результатам анализа."""
    if not PDF_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF не доступен. Установите: pip install reportlab",
        )
    try:
        pdf_bytes = generate_analysis_pdf(req.analysis)
        url = req.analysis.get("url", "site")
        safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in url)[:50]
        filename = f"analysis_{safe_name}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации PDF: {e}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
