# main.py
import os
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from azure.storage.blob import BlobServiceClient, ContentSettings

APP_NAME = "vast-tracker"

# ---- Config via env ----
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_CONTAINER = os.getenv("AZURE_CONTAINER", "vast-logs")
AZURE_BLOB_PREFIX = os.getenv("AZURE_BLOB_PREFIX", "events")  # optional prefix

if not AZURE_STORAGE_CONNECTION_STRING:
    raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required")

# ---- Azure clients ----
_blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
_container_client = _blob_service.get_container_client(AZURE_CONTAINER)
try:
    _container_client.create_container()  # idempotent
except Exception:
    pass

app = FastAPI(title=APP_NAME)

def _client_ip(req: Request) -> str:
    # Prefer X-Forwarded-For (reverse proxy / CDN); fall back to client host
    xff = req.headers.get("x-forwarded-for")
    if xff:
        # First IP in list is the original client
        return xff.split(",")[0].strip()
    return req.client.host if req.client else "unknown"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _blob_path() -> str:
    now = datetime.now(timezone.utc)
    # Partition by date/hour for cheaper listing & lifecycle management
    return f"{AZURE_BLOB_PREFIX}/{now:%Y/%m/%d/%H}/{uuid.uuid4()}.json"

def _safe_headers(headers: Dict[str, str]) -> Dict[str, str]:
    # Keep headers that are useful for analytics/debug; drop obvious secrets
    allow = {
        "user-agent", "referer", "origin", "x-forwarded-for",
        "x-forwarded-proto", "x-forwarded-host", "cf-connecting-ip",
        "cf-ipcountry", "via"
    }
    return {k.lower(): v for k, v in headers.items() if k.lower() in allow}

@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"

@app.get("/track")
async def track(request: Request, r: Optional[str] = None, ev: Optional[str] = None) -> Response:
    """
    VAST tracking endpoint.
    - Accepts any querystring (e.g., ?ev=impression&...).
    - Logs a JSON record to Azure Blob Storage (one blob per event).
    - Returns 204 No Content (good for pixel pings).
    """
    try:
        # Build log record
        record: Dict[str, Any] = {
            "ts": _now_iso(),
            "event": ev,
            "request_id": str(uuid.uuid4()),
            "method": request.method,
            "path": str(request.url.path),
            "query": dict(request.query_params),
            "headers": _safe_headers(dict(request.headers)),
            "ip": _client_ip(request),
            "scheme": request.url.scheme,
            "host": request.url.hostname,
            "port": request.url.port,
            "raw_url": str(request.url),
            # optional “r” param commonly used to carry original URL / beacon cache-buster
            "r": r,
        }

        body = (json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        blob_name = _blob_path()
        _container_client.upload_blob(
            name=blob_name,
            data=body,
            overwrite=False,
            content_settings=ContentSettings(content_type="application/json"),
        )

        # 204 plays nicely with VAST trackers/pixels
        return Response(status_code=204)

    except Exception as e:
        # Don’t break ad delivery: log nothing, still return 204.
        # If you want to observe failures, integrate real logging or App Insights.
        # For debugging during setup, temporarily return 500 instead.
        # print(f"[{APP_NAME}] error: {e}")  # optionally log to stdout
        return Response(status_code=204)
