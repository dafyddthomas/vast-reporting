import json
import os
from datetime import datetime, timezone
from functools import lru_cache

from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

from app.models.event import Event


@lru_cache(maxsize=1)
def _container_client():
    load_dotenv()
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn_str:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required")
    container = os.getenv("AZURE_CONTAINER", "vast-logs")
    service = BlobServiceClient.from_connection_string(conn_str)
    client = service.get_container_client(container)
    try:
        client.create_container()
    except Exception:
        pass
    return client


def _blob_path(now: datetime) -> str:
    prefix = os.getenv("AZURE_BLOB_PREFIX", "events")
    return f"{prefix}/{now:%Y/%m/%d}/{now:%H}.jsonl"


def append_event(event: Event) -> None:
    client = _container_client()
    now = datetime.now(timezone.utc)
    blob_name = _blob_path(now)
    blob_client = client.get_blob_client(blob_name)
    data = (json.dumps(event.__dict__, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    try:
        blob_client.create_append_blob(content_settings=ContentSettings(content_type="application/json"))
    except Exception:
        pass
    blob_client.append_block(data)
