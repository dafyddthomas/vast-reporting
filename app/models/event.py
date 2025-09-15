from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Event:
    """Domain model for a tracking event."""

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
