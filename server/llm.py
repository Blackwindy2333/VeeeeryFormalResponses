"""OpenAI 兼容 Chat Completions 客户端（标准库实现，支持流式）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator

from server.config import get_provider

# 思考强度映射（各家字段不同，这里做兼容层）
EFFORT_MAP = {"low": "low", "medium": "medium", "high": "high"}


class LLMError(RuntimeError):
    pass


def _headers(provider: dict[str, Any]) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {provider.get('api_key') or ''}",
    }
    extra = provider.get("extra_headers") or {}
    if isinstance(extra, dict):
        headers.update({str(k): str(v) for k, v in extra.items()})
    return headers


def build_payload(
    provider: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    stream: bool = True,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    sampling: dict[str, Any] | None = None,
    tools_enabled: bool | None = None,
    thinking_enabled: bool | None = None,
    thinking_effort: str | None = None,
) -> dict[str, Any]:
    """组装 chat.completions 请求体。"""
    sampling = sampling or {}
    thinking = provider.get("thinking") or {}
    use_thinking = (
        thinking_enabled
        if thinking_enabled is not None
        else bool(thinking.get("enabled"))
    )
    effort = thinking_effort or thinking.get("effort") or "medium"
    effort = EFFORT_MAP.get(str(effort), "medium")
    use_tools = (
        tools_enabled
        if tools_enabled is not None
        else bool(provider.get("tools_enabled"))
    )

    payload: dict[str, Any] = {
        "model": provider.get("model") or "",
        "messages": messages,
        "stream": bool(stream),
    }

    temp = temperature if temperature is not None else sampling.get("temperature")
    if temp is not None:
        payload["temperature"] = float(temp)
    tp = top_p if top_p is not None else sampling.get("top_p")
    if tp is not None:
        payload["top_p"] = float(tp)
    mt = max_tokens if max_tokens is not None else sampling.get("max_tokens")
    if mt is not None:
        payload["max_tokens"] = int(mt)

    # 思考模式：HTTP 请求体中应是顶层 "thinking" 字段（SDK 的 extra_body 只是展开到顶层）。
    # 同时透传 reasoning_effort，供 OpenAI 系兼容接口使用。
    if use_thinking:
        payload["reasoning_effort"] = effort
        payload["thinking"] = {"type": "enabled", "effort": effort}
    else:
        payload["thinking"] = {"type": "disabled"}

    # 工具调用：仅开关。开启时 tool_choice=auto；关闭时不传 tool_choice，
    # 避免“无 tools 却带 tool_choice=none”被部分兼容端点拒绝。
    if use_tools:
        payload["tool_choice"] = "auto"

    # 流式时请求 usage，否则部分服务在流式响应中不返回 token 用量。
    if stream:
        payload["stream_options"] = {"include_usage": True}

    return payload


def chat_url(provider: dict[str, Any]) -> str:
    base = (provider.get("base_url") or "").rstrip("/")
    if not base:
        raise LLMError("base_url 为空")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def create_completion(
    config: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    provider_id: str | None = None,
    stream: bool = True,
    timeout: float = 120.0,
    **payload_overrides: Any,
) -> dict[str, Any] | Iterator[dict[str, Any]]:
    """非流式返回完整 dict；流式返回事件迭代器。"""
    provider = get_provider(config, provider_id)
    sampling = config.get("sampling") or {}
    payload = build_payload(
        provider,
        messages,
        stream=stream,
        sampling=sampling,
        **payload_overrides,
    )
    url = chat_url(provider)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(provider), method="POST")
    if not stream:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise LLMError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"网络错误: {e.reason}") from e

    return _stream_completion(req, timeout)


def _stream_completion(req: urllib.request.Request, timeout: float) -> Iterator[dict[str, Any]]:
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise LLMError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"网络错误: {e.reason}") from e

    with resp:
        buffer = b""
        while True:
            chunk = resp.read(256)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line or not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    return
                try:
                    yield json.loads(data.decode("utf-8"))
                except json.JSONDecodeError:
                    continue


def extract_delta_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content or ""


def extract_reasoning_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    for key in ("reasoning_content", "reasoning", "thinking"):
        if isinstance(delta.get(key), str):
            return delta[key]
    return ""


def extract_usage(chunk: dict[str, Any]) -> dict[str, Any] | None:
    usage = chunk.get("usage")
    return usage if isinstance(usage, dict) else None


def run_stream(
    config: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    provider_id: str | None = None,
    on_delta: Callable[[str], None] | None = None,
    on_reasoning: Callable[[str], None] | None = None,
    timeout: float = 120.0,
    **payload_overrides: Any,
) -> dict[str, Any]:
    """执行流式请求，回调增量文本，返回 {content, reasoning, usage}。"""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    usage: dict[str, Any] | None = None

    stream = create_completion(
        config,
        messages,
        provider_id=provider_id,
        stream=True,
        timeout=timeout,
        **payload_overrides,
    )
    assert not isinstance(stream, dict)
    for chunk in stream:
        text = extract_delta_text(chunk)
        if text:
            content_parts.append(text)
            if on_delta:
                on_delta(text)
        reasoning = extract_reasoning_text(chunk)
        if reasoning:
            reasoning_parts.append(reasoning)
            if on_reasoning:
                on_reasoning(reasoning)
        u = extract_usage(chunk)
        if u:
            usage = u

    return {
        "content": "".join(content_parts),
        "reasoning": "".join(reasoning_parts),
        "usage": usage,
    }
