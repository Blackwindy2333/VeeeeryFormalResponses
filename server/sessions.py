"""会话本地持久化：data/sessions/*.json。"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from server.config import SESSIONS_DIR, ensure_data_dirs

_lock = threading.RLock()
_SAFE_NAME = re.compile(r"[^\w\-]+", re.UNICODE)


def _session_path(session_id: str) -> Path:
    safe = _SAFE_NAME.sub("_", session_id).strip("_") or "session"
    return SESSIONS_DIR / f"{safe}.json"


def list_sessions() -> list[dict[str, Any]]:
    ensure_data_dirs()
    items: list[dict[str, Any]] = []
    with _lock:
        for path in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, dict) and data.get("id"):
                items.append(data)
    items.sort(key=lambda s: s.get("updatedAt") or s.get("createdAt") or 0, reverse=True)
    return items


def load_session(session_id: str) -> dict[str, Any] | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def save_session(session: dict[str, Any]) -> None:
    if not session.get("id"):
        raise ValueError("session.id required")
    ensure_data_dirs()
    path = _session_path(str(session["id"]))
    tmp = path.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def delete_session(session_id: str) -> bool:
    path = _session_path(session_id)
    with _lock:
        if path.exists():
            path.unlink()
            return True
        return False


def save_sessions_bulk(sessions: list[dict[str, Any]]) -> int:
    count = 0
    for s in sessions:
        if isinstance(s, dict) and s.get("id"):
            save_session(s)
            count += 1
    return count
