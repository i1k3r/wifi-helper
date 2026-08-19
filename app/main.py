"""FastAPI application entrypoint for SUSESI Hotel Wi-Fi Helper."""

import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.logger import log_failure
from app.probe import check_mikrotik_health
from app.utils import get_client_ip, sanitize_room

# Base directory for templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared HTTP client lifecycle with connection pooling."""
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.PROBE_TIMEOUT_SECONDS + 1.0)
    )
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="SUSESI Hotel Wi-Fi Helper",
    version="0.1.0",
    docs_url=None,  # Disable Swagger UI to avoid exposing internal docs to guests
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """
    Lightweight healthcheck endpoint for Docker / orchestration.
    Does not expose sensitive diagnostics to guests.
    """
    return JSONResponse(status_code=200, content={"status": "ok"})


@app.get("/")
async def root(room: Optional[str] = Query(None)):
    """Convenience redirect from root to /wifi."""
    target_path = f"/wifi?room={room}" if room else "/wifi"
    return RedirectResponse(url=target_path, status_code=302)


@app.get("/wifi")
async def wifi_helper(
    request: Request,
    room: Optional[str] = Query(None),
):
    """
    Guest Wi-Fi helper endpoint triggered by QR #2.
    
    1. Extracts client IP from the direct socket (or trusted proxy if configured).
    2. Sanitizes optional room identifier.
    3. Runs an asynchronous HTTP GET probe against the MikroTik HotSpot login gateway.
    4. If healthy:
       - Returns HTTP 302 Found redirect to http://10.1.3.1/login
       - Attaches anti-caching headers so client always hits helper on subsequent connections
       - Generates NO alerts / failure logs (fast path)
    5. If unhealthy (MikroTik down, unreachable, timeout, or 5xx):
       - Emits a structured JSON failure log to stdout
       - Renders a clean, 100% self-contained multilingual error page
    """
    client_ip = get_client_ip(request, trust_proxy_headers=settings.TRUST_PROXY_HEADERS)
    sanitized_room = sanitize_room(room)
    user_agent = request.headers.get("user-agent", "unknown")

    # Retrieve shared async HTTP client
    http_client: httpx.AsyncClient = getattr(
        request.app.state, "http_client", None
    )
    
    # Fallback client if running outside lifespan (e.g. ad-hoc unit test harness)
    if http_client is None:
        async with httpx.AsyncClient() as temp_client:
            probe_result = await check_mikrotik_health(
                client=temp_client,
                probe_url=settings.MIKROTIK_PROBE_URL,
                timeout_seconds=settings.PROBE_TIMEOUT_SECONDS,
            )
    else:
        probe_result = await check_mikrotik_health(
            client=http_client,
            probe_url=settings.MIKROTIK_PROBE_URL,
            timeout_seconds=settings.PROBE_TIMEOUT_SECONDS,
        )

    # --- HEALTHY GATEWAY PATH ---
    if probe_result.is_healthy:
        # If automatic redirect is enabled, return immediate HTTP 302
        if settings.AUTO_REDIRECT:
            headers = {
                "Location": settings.MIKROTIK_LOGIN_URL,
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            }
            return Response(status_code=302, headers=headers)

        # Default / Experimental Flow:
        # Render clean landing page with user-initiated "İnternete Bağlan" button linking to http://10.1.3.1/login.
        # No automatic redirect, no JavaScript redirect, no credential proxying.
        return templates.TemplateResponse(
            request=request,
            name="connect.html",
            context={
                "room": sanitized_room,
                "mikrotik_login_url": settings.MIKROTIK_LOGIN_URL,
            },
            status_code=200,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )

    # --- UNHEALTHY GATEWAY PATH ---
    # Log structured failure event
    log_failure(
        probe_result=probe_result,
        client_ip=client_ip,
        room=sanitized_room,
        user_agent=user_agent,
    )

    # Render friendly offline error page
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "room": sanitized_room,
            "error_type": probe_result.error_type,
        },
        status_code=200,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
