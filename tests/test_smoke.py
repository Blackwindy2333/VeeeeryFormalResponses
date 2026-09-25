"""服务模块冒烟：导入与关键纯函数。"""

from __future__ import annotations

from server.document import build_document_view, to_plain_text
from server.llm import build_payload, chat_url
from server.prompt import build_messages, build_system_prompt


def test_modules_importable():
    import server.app
    import server.config
    import server.document
    import server.llm
    import server.prompt
    import server.sessions

    assert server.app.Handler
    assert server.config.DEFAULT_CONFIG


def test_end_to_end_payload_for_formal_reply():
    msgs = build_messages(
        [{"role": "user", "content": "写一份关于秋游的通知"}],
        doc_type="通知",
    )
    payload = build_payload(
        {
            "model": "demo",
            "thinking": {"enabled": True, "effort": "medium"},
            "tools_enabled": True,
            "api_key": "k",
            "base_url": "https://api.example.com/v1",
        },
        msgs,
    )
    assert payload["messages"][0]["role"] == "system"
    assert "通知" in payload["messages"][0]["content"]
    assert payload["tool_choice"] == "auto"
    assert payload["reasoning_effort"] == "medium"
    assert chat_url({"base_url": "https://api.example.com/v1"}).endswith(
        "/chat/completions"
    )


def test_document_view_roundtrip():
    raw = '```json\n{"document": {"title": "关于秋游的通知"}}\n```\n各部门：\n\n现定于本周五秋游。'
    view = build_document_view(raw, {"document": {"masthead": "测试单位"}}, "通知")
    text = to_plain_text(view)
    assert "关于秋游的通知" in text
    assert "测试单位" in text
    assert "本周五秋游" in text
    assert build_system_prompt("通知")
