"""会话持久化测试。"""

from __future__ import annotations

from pathlib import Path

import server.sessions as sessions
from server.config import ensure_data_dirs


def test_save_load_delete(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "sessions")
    ensure_data_dirs()
    # ensure_data_dirs uses config.SESSIONS_DIR; patch module path used by sessions
    (tmp_path / "sessions").mkdir(parents=True, exist_ok=True)

    session = {
        "id": "s_test1",
        "title": "测试会话",
        "createdAt": 1,
        "updatedAt": 2,
        "messages": [{"id": "m1", "role": "user", "content": "你好"}],
    }
    sessions.save_session(session)
    loaded = sessions.load_session("s_test1")
    assert loaded is not None
    assert loaded["title"] == "测试会话"
    assert loaded["messages"][0]["content"] == "你好"

    items = sessions.list_sessions()
    assert any(s["id"] == "s_test1" for s in items)

    assert sessions.delete_session("s_test1") is True
    assert sessions.load_session("s_test1") is None
    assert sessions.delete_session("s_test1") is False


def test_safe_filename(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(parents=True, exist_ok=True)
    sessions.save_session({"id": "../evil/id", "title": "x"})
    # 不应写出到 sessions 目录之外
    outside = (tmp_path / "evil").exists()
    assert outside is False
    files = list((tmp_path / "sessions").glob("*.json"))
    assert len(files) == 1


def test_list_sorted_by_updated(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(parents=True, exist_ok=True)
    sessions.save_session({"id": "a", "title": "旧", "updatedAt": 1, "createdAt": 1})
    sessions.save_session({"id": "b", "title": "新", "updatedAt": 9, "createdAt": 1})
    items = sessions.list_sessions()
    assert items[0]["id"] == "b"
