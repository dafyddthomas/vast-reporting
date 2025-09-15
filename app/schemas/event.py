from typing import Optional, Dict, Any
from pydantic import BaseModel


class EventRecord(BaseModel):
    ts: str
    event: Optional[str]
    request_id: str
    method: str
    path: str
    query: Dict[str, Any]
    headers: Dict[str, str]
    ip: str
    scheme: Optional[str]
    host: Optional[str]
    port: Optional[int]
    raw_url: str
    r: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "ts": "2024-01-01T00:00:00+00:00",
                "event": "impression",
                "request_id": "uuid",
                "method": "GET",
                "path": "/track",
                "query": {"ev": "impression"},
                "headers": {"user-agent": "test"},
                "ip": "127.0.0.1",
                "scheme": "http",
                "host": "localhost",
                "port": 8000,
                "raw_url": "http://localhost/track?ev=impression",
            }
        }
