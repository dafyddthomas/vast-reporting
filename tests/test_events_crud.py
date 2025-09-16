import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.crud import events
from app.models.event import Event


def _sample_event(**overrides: object) -> Event:
    data = {
        "ts": "2023-01-01T00:00:00Z",
        "event": "test",
        "request_id": "req-0",
        "method": "GET",
        "path": "/",
        "query": {},
        "headers": {"User-Agent": "pytest"},
        "ip": "127.0.0.1",
        "scheme": "https",
        "host": "example.com",
        "port": 443,
        "raw_url": "https://example.com/",
        "r": None,
    }
    data.update(overrides)
    return Event(**data)


def test_flush_events_batches_payload(monkeypatch):
    events.flush_events()
    monkeypatch.setattr(events, "_blob_path", lambda _: "events/2025/09/16/12.jsonl")

    mock_blob_client = MagicMock()
    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    monkeypatch.setattr(events, "_container_client", lambda: mock_container)

    event_one = _sample_event(request_id="req-1")
    event_two = _sample_event(request_id="req-2")

    events.append_event(event_one)
    events.append_event(event_two)

    assert mock_container.get_blob_client.call_count == 0

    events.flush_events()

    mock_container.get_blob_client.assert_called_once_with("events/2025/09/16/12.jsonl")
    expected_first = (
        json.dumps(event_one.__dict__, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    expected_second = (
        json.dumps(event_two.__dict__, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    mock_blob_client.append_block.assert_called_once_with(expected_first + expected_second)

    events.flush_events()


def test_flush_events_requeues_on_failure(monkeypatch):
    events.flush_events()
    monkeypatch.setattr(events, "_blob_path", lambda _: "events/2025/09/16/12.jsonl")

    failing_event = _sample_event()

    def _fail_container():
        raise RuntimeError("boom")

    monkeypatch.setattr(events, "_container_client", _fail_container)

    events.append_event(failing_event)
    events.flush_events()

    mock_blob_client = MagicMock()
    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    monkeypatch.setattr(events, "_container_client", lambda: mock_container)

    events.flush_events()

    mock_container.get_blob_client.assert_called_once_with("events/2025/09/16/12.jsonl")
    expected_data = (
        json.dumps(failing_event.__dict__, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    mock_blob_client.append_block.assert_called_once_with(expected_data)

    events.flush_events()


def test_download_events_blob_logs_full_path(monkeypatch, caplog):
    blob_path = "events/2025/09/16/12.jsonl"
    expected_url = (
        "https://podcastlake.blob.core.windows.net/vast/events/2025/09/16/12.jsonl"
    )

    mock_blob_client = MagicMock()
    mock_blob_client.url = expected_url

    mock_downloader = MagicMock()
    mock_downloader.readall.return_value = b"payload"
    mock_blob_client.download_blob.return_value = mock_downloader

    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client

    monkeypatch.setattr(events, "_container_client", lambda: mock_container)
    monkeypatch.setattr(events, "_blob_path", lambda _: blob_path)

    with caplog.at_level("DEBUG", logger="app.crud.events"):
        result = events.download_events_blob(datetime(2025, 9, 16, 12, tzinfo=timezone.utc))

    assert result == b"payload"
    assert any("/vast/events/" in message for message in caplog.messages)
    mock_blob_client.download_blob.assert_called_once_with()
