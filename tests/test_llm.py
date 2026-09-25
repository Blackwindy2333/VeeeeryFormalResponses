"""LLM 请求组装测试（不发起网络请求）。"""

from __future__ import annotations

from server.config import default_config
from server.llm import (
    build_payload,
    chat_url,
    extract_delta_text,
    extract_reasoning_text,
    extract_usage,
)


def _provider(**kwargs):
    p = {
        "id": "x",
        "nickname": "X",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test",
        "model": "demo-model",
        "thinking": {"enabled": False, "effort": "medium"},
        "tools_enabled": False,
        "extra_headers": {},
    }
    p.update(kwargs)
    return p


def test_build_payload_basic():
    payload = build_payload(
        _provider(),
        [{"role": "user", "content": "hi"}],
        stream=True,
        temperature=0.7,
        top_p=0.9,
        max_tokens=1024,
    )
    assert payload["model"] == "demo-model"
    assert payload["stream"] is True
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["max_tokens"] == 1024
    assert payload["extra_body"]["thinking"]["type"] == "disabled"
    assert payload["tool_choice"] == "none"
    assert "reasoning_effort" not in payload


def test_build_payload_thinking_and_tools():
    payload = build_payload(
        _provider(thinking={"enabled": True, "effort": "high"}, tools_enabled=True),
        [{"role": "user", "content": "hi"}],
    )
    assert payload["reasoning_effort"] == "high"
    assert payload["extra_body"]["thinking"]["type"] == "enabled"
    assert payload["tool_choice"] == "auto"


def test_build_payload_overrides():
    payload = build_payload(
        _provider(),
        [{"role": "user", "content": "hi"}],
        thinking_enabled=True,
        thinking_effort="low",
        tools_enabled=True,
    )
    assert payload["reasoning_effort"] == "low"
    assert payload["tool_choice"] == "auto"


def test_build_payload_from_config_sampling():
    cfg = default_config()
    cfg["sampling"] = {"temperature": 0.2, "top_p": 0.8, "max_tokens": 256}
    payload = build_payload(
        cfg["providers"][0],
        [{"role": "user", "content": "hi"}],
        sampling=cfg["sampling"],
    )
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 256


def test_chat_url_variants():
    assert chat_url({"base_url": "https://api.deepseek.com"}) == (
        "https://api.deepseek.com/v1/chat/completions"
    )
    assert chat_url({"base_url": "https://api.xiaomimimo.com/v1"}) == (
        "https://api.xiaomimimo.com/v1/chat/completions"
    )
    assert chat_url({"base_url": "https://x/v1/chat/completions"}) == (
        "https://x/v1/chat/completions"
    )


def test_extract_helpers():
    chunk = {
        "choices": [
            {
                "delta": {
                    "content": "你好",
                    "reasoning_content": "思考",
                }
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }
    assert extract_delta_text(chunk) == "你好"
    assert extract_reasoning_text(chunk) == "思考"
    assert extract_usage(chunk)["completion_tokens"] == 2
    assert extract_delta_text({"choices": []}) == ""
    assert extract_reasoning_text({"choices": [{"delta": {}}]}) == ""
    assert extract_usage({}) is None
