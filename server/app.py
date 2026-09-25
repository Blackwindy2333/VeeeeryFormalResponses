"""本地 HTTP 服务：静态资源 + 配置 API + 流式聊天。"""

from __future__ import annotations

import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from server.config import (
    DEFAULT_CONFIG_PATH,
    default_config,
    ensure_data_dirs,
    load_config,
    normalize_config,
    save_config,
)
from server.llm import LLMError, run_stream
from server.prompt import build_messages, split_meta_and_body, transform_prompt

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "VeeeeryFormal/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # 安静日志，避免刷屏
        pass

    # ---------- helpers ----------
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid json: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("json body must be object")
        return data

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        if rel == "app" or rel == "":
            rel = "index.html"
        # 防目录穿越
        target = (STATIC_DIR / rel).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())):
            self._json(403, {"error": "forbidden"})
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            self._json(404, {"error": "not found", "path": rel})
            return
        content = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in {
            "application/javascript",
            "application/json",
        }:
            ctype = f"{ctype}; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    # ---------- HTTP verbs ----------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/health":
                self._json(200, {"ok": True, "version": "0.1.0"})
            elif path == "/api/config":
                cfg = load_config()
                # 不向前端返回完整 api_key 明文可选；本工具为本机使用，返回完整配置便于编辑
                self._json(200, {"config": cfg})
            else:
                self._serve_static(path)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": str(e)})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/config/reset":
                cfg = default_config()
                save_config(cfg)
                self._json(200, {"config": cfg})
            elif path == "/api/chat/stream":
                self._handle_chat_stream()
            elif path == "/api/chat":
                self._handle_chat()
            elif path == "/api/transform":
                self._handle_transform()
            else:
                self._json(404, {"error": "not found"})
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except LLMError as e:
            self._json(502, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": str(e)})

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            try:
                body = self._read_json()
                cfg = normalize_config(body)
                save_config(cfg)
                self._json(200, {"config": load_config()})
            except ValueError as e:
                self._json(400, {"error": str(e)})
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self._json(500, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})

    # ---------- API impl ----------
    def _handle_chat(self) -> None:
        body = self._read_json()
        messages, options = self._parse_chat_body(body)
        result = self._run_non_stream(messages, options)
        title, text = split_meta_and_body(result.get("content") or "")
        self._json(
            200,
            {
                "content": result.get("content") or "",
                "title": title,
                "body": text,
                "usage": result.get("usage"),
                "reasoning": result.get("reasoning"),
            },
        )

    def _run_non_stream(self, messages: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
        from server.llm import create_completion, extract_delta_text, extract_usage

        cfg = load_config()
        provider_id = options.pop("provider_id", None)
        stream = create_completion(
            cfg,
            messages,
            provider_id=provider_id,
            stream=False,
            **options,
        )
        if isinstance(stream, dict):
            choices = stream.get("choices") or []
            content = ""
            if choices:
                msg = choices[0].get("message") or {}
                content = msg.get("content") or ""
            return {
                "content": content,
                "usage": extract_usage(stream),
                "reasoning": "",
            }
        # 兜底
        return {"content": "", "usage": None, "reasoning": ""}

    def _handle_transform(self) -> None:
        body = self._read_json()
        mode = str(body.get("mode") or "formal")
        text = str(body.get("text") or "")
        doc_type = str(body.get("doc_type") or "报告")
        if not text.strip():
            raise ValueError("text is empty")
        messages = build_messages(
            [{"role": "user", "content": transform_prompt(mode, text)}],
            doc_type=doc_type,
        )
        options = self._options_from_body(body)
        result = self._run_non_stream(messages, options)
        title, content = split_meta_and_body(result.get("content") or "")
        self._json(
            200,
            {
                "content": result.get("content") or "",
                "title": title,
                "body": content,
                "usage": result.get("usage"),
            },
        )

    def _parse_chat_body(self, body: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        history = body.get("messages")
        if not isinstance(history, list):
            raise ValueError("messages must be a list")
        doc_type = str(body.get("doc_type") or body.get("docType") or "报告")
        messages = build_messages(history, doc_type=doc_type)
        options = self._options_from_body(body)
        return messages, options

    def _options_from_body(self, body: dict[str, Any]) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if body.get("provider_id"):
            options["provider_id"] = body["provider_id"]
        if body.get("thinking_enabled") is not None:
            options["thinking_enabled"] = bool(body["thinking_enabled"])
        if body.get("thinking_effort"):
            options["thinking_effort"] = str(body["thinking_effort"])
        if body.get("tools_enabled") is not None:
            options["tools_enabled"] = bool(body["tools_enabled"])
        return options

    def _handle_chat_stream(self) -> None:
        body = self._read_json()
        messages, options = self._parse_chat_body(body)
        cfg = load_config()
        provider_id = options.pop("provider_id", None)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def send_event(payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, ensure_ascii=False)
            self.wfile.write(f"data: {raw}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            result = run_stream(
                cfg,
                messages,
                provider_id=provider_id,
                on_delta=lambda t: send_event({"type": "delta", "text": t}),
                on_reasoning=lambda t: send_event({"type": "reasoning", "text": t}),
                **options,
            )
            title, text = split_meta_and_body(result.get("content") or "")
            send_event(
                {
                    "type": "done",
                    "content": result.get("content") or "",
                    "title": title,
                    "body": text,
                    "usage": result.get("usage"),
                    "reasoning": result.get("reasoning"),
                }
            )
        except LLMError as e:
            send_event({"type": "error", "message": str(e)})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            send_event({"type": "error", "message": str(e)})


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    ensure_data_dirs()
    load_config()  # 启动时确保配置存在
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    return ThreadingHTTPServer((host, port), Handler)


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_server(host, port)
    print(f"Veeeery Formal Responses  http://{host}:{port}")
    print(f"Config: {DEFAULT_CONFIG_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
