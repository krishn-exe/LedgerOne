import os
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response

from auth import router as auth_router, cleanup_expired_sessions
from expenses import router as expenses_router
from fetch import router as fetch_router
from routes_web import (
    router as web_router,
    AuthenticationRequired,
    ForbiddenError,
    get_optional_user,
    templates,
)

async def periodic_session_cleanup():
    """Background task running every hour to keep sessions table trimmed."""
    while True:
        try:
            cleanup_expired_sessions()
        except Exception:
            pass
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run once on server startup, then keep running hourly in background
    cleanup_task = asyncio.create_task(periodic_session_cleanup())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

# Include web HTML/HTMX router (handles HTML routes and content-type aware login/register)
app.include_router(web_router)

# Include existing API routers untouched so all endpoints remain visible in /docs
app.include_router(auth_router)
app.include_router(expenses_router)
app.include_router(fetch_router)

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Global web exception handlers
@app.exception_handler(AuthenticationRequired)
async def auth_required_handler(request: Request, exc: AuthenticationRequired):
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": "/login"})
    return RedirectResponse(url="/login", status_code=303)


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError):
    user = get_optional_user(request)
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "user": user,
            "title": "Access Denied",
            "message": exc.message,
            "status_code": 403,
        },
        status_code=403,
    )


@app.get("/")
def root():
    return {"message": "Online"}