from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, Response

from app.classifier import Classifier
from app.config import get_settings
from app.observability import LATENCY, REQUESTS, get_logger, setup_logging
from app.schemas import ClassifyRequest, ClassifyResponse

log = get_logger("api")
_WEB = Path(__file__).parent / "web"
_INDEX_HTML = (
    (_WEB / "index.html")
    .read_text(encoding="utf-8")
    .replace(
        "<!-- UI_FONTS -->",
        "<style>" + (_WEB / "fonts.css").read_text(encoding="utf-8") + "</style>",
    )
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    app.state.classifier = Classifier(settings)
    log.info(
        "startup",
        service=settings.service_name,
        model=settings.primary_model,
        fake_llm=settings.llm_fake,
    )
    yield


app = FastAPI(title="Phishing Triage Service", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.clear_contextvars()
    elapsed = time.perf_counter() - start
    if request.url.path == "/v1/classify":
        LATENCY.observe(elapsed)
    response.headers["x-request-id"] = request_id
    log.info("http_request", status=response.status_code, elapsed_ms=round(elapsed * 1000, 2))
    return response


@app.get("/", response_class=HTMLResponse)
@app.get("/inspect", response_class=HTMLResponse)
async def root(request: Request) -> str:
    page = _INDEX_HTML.replace(
        "<!-- WORKSPACE_NAV -->",
        '<a href="/invoices/">Gmail &amp; invoices</a>'
        if getattr(request.app.state, "invoice_workspace", False)
        else "",
    )
    return page.replace(
        "<!-- RUNTIME_NOTICE -->",
        '<p class="hint" role="note">Local preview · Simulated classifier responses</p>'
        if get_settings().llm_fake
        else "",
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest, request: Request) -> ClassifyResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
    classifier: Classifier = request.app.state.classifier
    try:
        result = await run_in_threadpool(classifier.classify, req.text, request_id=request_id)
    except Exception as exc:  # noqa: BLE001 - surface any upstream failure as 502
        REQUESTS.labels(outcome="error").inc()
        log.exception("classify_failed", request_id=request_id)
        raise HTTPException(status_code=502, detail="upstream model error") from exc
    REQUESTS.labels(outcome=result.label).inc()
    return result
