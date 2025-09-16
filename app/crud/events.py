import atexit
import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from threading import Lock, Timer
from typing import Dict, List, Optional

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

from app.models.event import Event


logger = logging.getLogger(__name__)

_FLUSH_INTERVAL_SECONDS = 30

_buffer_lock = Lock()
_event_buffer: Dict[str, List[bytes]] = {}
_flush_timer: Optional[Timer] = None


@lru_cache(maxsize=1)
def _container_client():
    load_dotenv()
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "")
    if not account_name:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME is required")
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY", "")
    if not account_key:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_KEY is required")
    container = os.getenv("AZURE_CONTAINER", "vast")
    account_url = f"https://{account_name}.blob.core.windows.net"
    service = BlobServiceClient(account_url=account_url, credential=account_key)
    client = service.get_container_client(container)
    try:
        client.create_container()
    except Exception:
        pass
    return client


def _blob_path(now: datetime) -> str:
    prefix = os.getenv("AZURE_BLOB_PREFIX", "events")
    return f"{prefix}/{now:%Y/%m/%d}/{now:%H}.jsonl"


def _blob_url(blob_name: str) -> str:
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
    container = os.getenv("AZURE_CONTAINER", "vast")
    if account_name:
        return f"https://{account_name}.blob.core.windows.net/{container}/{blob_name}"
    return f"{container}/{blob_name}"


def _schedule_flush_locked() -> None:
    global _flush_timer
    if _flush_timer is not None:
        return
    timer = Timer(_FLUSH_INTERVAL_SECONDS, _flush_from_timer)
    timer.daemon = True
    _flush_timer = timer
    timer.start()


def _flush_from_timer() -> None:
    pending = _drain_buffer(cancel_timer=False)
    _write_pending(pending)


def _drain_buffer(cancel_timer: bool) -> Dict[str, List[bytes]]:
    global _event_buffer, _flush_timer
    with _buffer_lock:
        pending = _event_buffer
        _event_buffer = {}
        timer = _flush_timer
        _flush_timer = None
    if cancel_timer and timer is not None:
        timer.cancel()
    return pending


def _return_to_buffer(pending: Dict[str, List[bytes]]) -> None:
    if not pending:
        return
    with _buffer_lock:
        for blob_name, payloads in pending.items():
            if not payloads:
                continue
            _event_buffer.setdefault(blob_name, []).extend(payloads)
        _schedule_flush_locked()


def _write_pending(pending: Dict[str, List[bytes]]) -> None:
    if not pending:
        return
    if not any(payloads for payloads in pending.values()):
        return
    try:
        client = _container_client()
    except Exception:  # pragma: no cover - unexpected configuration errors
        logger.exception("Unable to create Azure container client")
        _return_to_buffer(pending)
        return
    for blob_name, payloads in pending.items():
        if not payloads:
            continue
        data = b"".join(payloads)
        if not data:
            continue
        blob_client = client.get_blob_client(blob_name)
        try:
            blob_client.create_append_blob(
                content_settings=ContentSettings(content_type="application/json")
            )
        except ResourceExistsError:
            pass
        except Exception:
            logger.exception("Failed to create append blob %s", blob_name)
            _return_to_buffer({blob_name: payloads})
            continue
        try:
            blob_client.append_block(data)
        except Exception:
            logger.exception("Failed to append events to blob %s", blob_name)
            _return_to_buffer({blob_name: payloads})


def flush_events() -> None:
    pending = _drain_buffer(cancel_timer=True)
    _write_pending(pending)


def append_event(event: Event) -> None:
    now = datetime.now(timezone.utc)
    blob_name = _blob_path(now)
    data = (
        json.dumps(event.__dict__, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    with _buffer_lock:
        _event_buffer.setdefault(blob_name, []).append(data)
        _schedule_flush_locked()


def download_events_blob(blob_time: datetime) -> Optional[bytes]:
    """Download the blob that stores VAST events for the provided time slot.

    Returns the blob content as bytes when the download succeeds or ``None``
    when the blob cannot be retrieved.
    """

    blob_name = _blob_path(blob_time)
    try:
        client = _container_client()
    except Exception:
        logger.exception("Unable to create Azure container client for download")
        return None

    blob_client = client.get_blob_client(blob_name)
    blob_url = getattr(blob_client, "url", _blob_url(blob_name))
    logger.debug("Downloading VAST events from %s", blob_url)

    try:
        downloader = blob_client.download_blob()
        return downloader.readall()
    except Exception:
        logger.exception("Failed to download events blob %s", blob_url)
        return None


atexit.register(flush_events)
