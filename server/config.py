"""配置读写：启动时若无配置文件则以默认设置创建。"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

# 项目根目录（server/ 的上一级）
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config.json"
DATA_DIR = ROOT_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"

_lock = threading.RLock()

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "active_provider_id": "deepseek",
    "providers": [
        {
            "id": "deepseek",
            "nickname": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "api_key": "",
            "model": "deepseek-chat",
            "thinking": {
                "enabled": False,
                "effort": "medium",
            },
            "tools_enabled": False,
            "extra_headers": {},
        },
        {
            "id": "mimo",
            "nickname": "Xiaomi MiMo",
            "base_url": "https://api.xiaomimimo.com/v1",
            "api_key": "",
            "model": "mimo-v2.6-pro",
            "thinking": {
                "enabled": False,
                "effort": "medium",
            },
            "tools_enabled": False,
            "extra_headers": {},
        },
    ],
    "document": {
        "masthead": "演示单位（示例）",
        "greeting": "尊敬的阅办人：",
        "closing": "此致",
        "signature": "智能助手",
        "role_title": "",
        "doc_types": [
            "报告",
            "通知",
            "请示",
            "函",
            "意见",
            "批复",
            "通报",
            "纪要",
            "说明",
        ],
        "default_doc_type": "报告",
        "indent_paragraphs": True,
        "hierarchy_fonts": True,
    },
    "ui": {
        "theme": "light",
        "font_scale": 1.0,
        "stream": True,
        "show_token_usage": True,
    },
    "sampling": {
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 4096,
    },
}


# 新增提供商时的中性模板（不得继承某一厂商的 model/base_url）
_PROVIDER_TEMPLATE: dict[str, Any] = {
    "id": "",
    "nickname": "",
    "base_url": "",
    "api_key": "",
    "model": "",
    "thinking": {
        "enabled": False,
        "effort": "medium",
    },
    "tools_enabled": False,
    "extra_headers": {},
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """递归合并 override 到 base 的副本，override 优先。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def default_config() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    """与默认配置合并，补齐缺失字段。"""
    if not isinstance(raw, dict):
        return default_config()
    merged = _deep_merge(DEFAULT_CONFIG, raw)
    # 保证 providers 至少有一项且结构完整
    providers = merged.get("providers")
    if not isinstance(providers, list) or not providers:
        merged["providers"] = copy.deepcopy(DEFAULT_CONFIG["providers"])
    else:
        normalized_providers = []
        for item in providers:
            if not isinstance(item, dict):
                continue
            # 用中性模板补齐，避免新提供商继承 DeepSeek 的 model/base_url
            provider = _deep_merge(_PROVIDER_TEMPLATE, item)
            if not provider.get("id"):
                provider["id"] = f"provider-{len(normalized_providers) + 1}"
            if not provider.get("nickname"):
                provider["nickname"] = provider["id"]
            normalized_providers.append(provider)
        merged["providers"] = normalized_providers or copy.deepcopy(
            DEFAULT_CONFIG["providers"]
        )
    active = merged.get("active_provider_id")
    ids = {p["id"] for p in merged["providers"]}
    if active not in ids:
        merged["active_provider_id"] = merged["providers"][0]["id"]
    return merged


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """读取配置；文件不存在时创建默认配置并返回。"""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with _lock:
        if not config_path.exists():
            cfg = default_config()
            save_config(cfg, config_path)
            return cfg
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # 损坏配置：备份后写入默认，避免静默丢失 API Key 等
            try:
                backup = config_path.with_suffix(".corrupt.bak")
                config_path.replace(backup)
            except OSError:
                pass
            cfg = default_config()
            save_config(cfg, config_path)
            return cfg
        return normalize_config(raw)


def save_config(config: dict[str, Any], path: Path | str | None = None) -> None:
    """写入配置文件（原子写）。"""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    normalized = normalize_config(config)
    with _lock:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = config_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, config_path)


def get_provider(config: dict[str, Any], provider_id: str | None = None) -> dict[str, Any]:
    """按 id 或 active_provider_id 取提供商配置。"""
    providers = config.get("providers") or []
    target = provider_id or config.get("active_provider_id")
    for provider in providers:
        if provider.get("id") == target:
            return provider
    if providers:
        return providers[0]
    return copy.deepcopy(DEFAULT_CONFIG["providers"][0])


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
