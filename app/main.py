import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_letters import router as letters_router
from app.api.routes_internal import router as internal_router
from app.api.routes_search import router as search_router
from app.api.routes_stats import router as stats_router
from app.api.routes_tags import router as tags_router
from app.api.routes_correspondents import router as correspondents_router
from app.api.routes_accounts import router as accounts_router
from app.db import SessionLocal
from app.domain import DomainError

# --- Rate limiter ---

RATE_LIMIT = 60
RATE_WINDOW = 60
_rate_store: dict[str, tuple[int, float]] = {}
_rate_last_cleanup = time.monotonic()
RATE_CLEANUP_INTERVAL = 300


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global _rate_last_cleanup
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        if now - _rate_last_cleanup > RATE_CLEANUP_INTERVAL:
            stale = [ip for ip, (_, ws) in _rate_store.items() if now - ws > RATE_WINDOW]
            for ip in stale:
                del _rate_store[ip]
            _rate_last_cleanup = now

        count, window_start = _rate_store.get(client_ip, (0, now))
        if now - window_start > RATE_WINDOW:
            count, window_start = 1, now
        else:
            count += 1

        _rate_store[client_ip] = (count, window_start)

        if count > RATE_LIMIT:
            return JSONResponse(
                {"error": "Zu viele Anfragen. Bitte warte einen Moment."},
                status_code=429,
            )

        return await call_next(request)


# --- App ---

app = FastAPI(title="Briefkasten", version="0.1.0")

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8101",
        "http://127.0.0.1:8101",
        "http://localhost",
        "https://localhost",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_router)
app.include_router(letters_router)
app.include_router(tags_router)
app.include_router(search_router)
app.include_router(internal_router)
app.include_router(stats_router)
app.include_router(correspondents_router)
app.include_router(accounts_router)


@app.get("/health", tags=["health"])
def health():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=503)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=422,
        content={"error": exc.message, "details": exc.details},
    )


def resolve_spa_path(static_root: Path, path: str) -> Path | None:
    """Loest einen SPA-Anfragepfad auf eine auslieferbare Datei auf.

    Loest erst auf (frisst `..` und Symlinks) und prueft dann gegen die
    Static-Wurzel. Der vorherige `".." not in path`-Test hielt zwar den
    `..`-Vektor auf, deckte aber keine Symlinks aus dem Static-Ordner heraus ab
    und beschrieb die Absicht nur indirekt.

    Rueckgabe: die Datei, oder None wenn ausserhalb der Wurzel / nicht vorhanden.
    """
    try:
        candidate = (static_root / path).resolve()
    except OSError:
        return None
    if not candidate.is_relative_to(static_root):
        return None
    return candidate if candidate.is_file() else None


# --- SPA static files ---

_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    _assets_dir = _static_dir / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    _static_root = _static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        file_path = resolve_spa_path(_static_root, path)
        if file_path is not None:
            return FileResponse(file_path)
        return FileResponse(_static_root / "index.html")
