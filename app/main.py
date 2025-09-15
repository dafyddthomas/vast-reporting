import uuid
import logging
from logging.handlers import RotatingFileHandler, SysLogHandler
from datetime import datetime, timezone
from typing import Optional, Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from app.models.event import Event
from app.schemas.event import EventRecord
from app.crud.events import append_event

APP_NAME = "vast-tracker"


logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler("vast-reporting.log", maxBytes=1_000_000, backupCount=5)
file_handler.setLevel(logging.ERROR)

try:
    from systemd.journal import JournalHandler

    journal_handler = JournalHandler(SYSLOG_IDENTIFIER=APP_NAME)
except Exception:  # pragma: no cover - fallback when systemd is unavailable
    journal_handler = SysLogHandler(address="/dev/log")
journal_handler.setLevel(logging.ERROR)

formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
for handler in (file_handler, journal_handler):
    handler.setFormatter(formatter)
    logger.addHandler(handler)


app = FastAPI(title=APP_NAME)


def _client_ip(req: Request) -> str:
    xff = req.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return req.client.host if req.client else "unknown"


def _safe_headers(headers: Dict[str, str]) -> Dict[str, str]:
    allow = {
        "user-agent",
        "referer",
        "origin",
        "x-forwarded-for",
        "x-forwarded-proto",
        "x-forwarded-host",
        "cf-connecting-ip",
        "cf-ipcountry",
        "via",
    }
    return {k.lower(): v for k, v in headers.items() if k.lower() in allow}


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


@app.get("/track")
async def track(request: Request, r: Optional[str] = None, ev: Optional[str] = None) -> Response:
    try:
        record_schema = EventRecord(
            ts=datetime.now(timezone.utc).isoformat(),
            event=ev,
            request_id=str(uuid.uuid4()),
            method=request.method,
            path=str(request.url.path),
            query=dict(request.query_params),
            headers=_safe_headers(dict(request.headers)),
            ip=_client_ip(request),
            scheme=request.url.scheme,
            host=request.url.hostname,
            port=request.url.port,
            raw_url=str(request.url),
            r=r,
        )
        record = Event(**record_schema.dict())
        append_event(record)
        return Response(status_code=204)
    except Exception:
        logger.exception("error processing tracking request")
        return Response(status_code=204)
