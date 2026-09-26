"""配置模块测试。"""

from __future__ import annotations

import json
from pathlib import Path

from server.config import (
    DEFAULT_CONFIG_PATH,
    default_config,
    ensure_data_dirs,
    get_provider,
    load_config,
    normalize_config,
    save_config,
)


def test_default_config_shape():
    cfg = default_config()
    assert cfg["schema_version"] == 1
    assert "providers" in cfg and len(cfg["providers"]) >= 1
    assert "document" in cfg and "masthead" in cfg["document"]
    assert "thinking" in cfg["providers"][0]
    assert "tools_enabled" in cfg["providers"][0]


def test_load_creates_default_when_missing(tmp_path: Path):
    path = tmp_path / "config.json"
    assert not path.exists()
    cfg = load_config(path)
    assert path.exists()
    assert cfg["active_provider_id"] == cfg["providers"][0]["id"]
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == 1


def test_save_and_reload_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    cfg = default_config()
    cfg["document"]["masthead"] = "某某公司"
    cfg["providers"][0]["api_key"] = "sk-test"
    cfg["providers"][0]["thinking"]["enabled"] = True
    cfg["providers"][0]["thinking"]["effort"] = "high"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded["document"]["masthead"] == "某某公司"
    assert loaded["providers"][0]["api_key"] == "sk-test"
    assert loaded["providers"][0]["thinking"] == {"enabled": True, "effort": "high"}


def test_normalize_fills_missing_fields():
    raw = {
        "providers": [{"id": "custom", "nickname": "自定义", "api_key": "x"}],
        "document": {"masthead": "H"},
    }
    cfg = normalize_config(raw)
    assert cfg["document"]["masthead"] == "H"
    assert cfg["document"]["greeting"]  # 默认补齐
    provider = cfg["providers"][0]
    # 中性模板：不得继承 DeepSeek 的 model/base_url
    assert provider["model"] == ""
    assert provider["base_url"] == ""
    assert provider["nickname"] == "自定义"
    assert "tools_enabled" in provider
    assert provider["thinking"]["effort"] in {"low", "medium", "high"}
    assert cfg["active_provider_id"] == "custom"


def test_normalize_does_not_leak_deepseek_model():
    cfg = normalize_config(
        {
            "providers": [
                {"id": "a", "nickname": "A", "api_key": "1", "model": "m-a"},
                {"id": "b", "nickname": "B", "api_key": "2"},
            ]
        }
    )
    assert cfg["providers"][0]["model"] == "m-a"
    assert cfg["providers"][1]["model"] == ""
    assert cfg["providers"][1]["base_url"] == ""


def test_normalize_repairs_bad_active_provider():
    cfg = normalize_config(
        {
            "active_provider_id": "missing",
            "providers": [{"id": "a", "nickname": "A", "api_key": ""}],
        }
    )
    assert cfg["active_provider_id"] == "a"


def test_get_provider_by_id_and_active():
    cfg = default_config()
    p = get_provider(cfg, "mimo")
    assert p["id"] == "mimo"
    p2 = get_provider(cfg)
    assert p2["id"] == cfg["active_provider_id"]


def test_corrupt_config_rewritten(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not-json", encoding="utf-8")
    cfg = load_config(path)
    assert cfg["providers"]
    # 损坏配置应备份，而不是静默销毁
    bak = tmp_path / "config.corrupt.bak"
    assert bak.exists()
    assert "{not-json" in bak.read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))


def test_ensure_data_dirs(tmp_path: Path, monkeypatch):
    import server.config as config_mod

    monkeypatch.setattr(config_mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config_mod, "SESSIONS_DIR", tmp_path / "data" / "sessions")
    config_mod.ensure_data_dirs()
    assert (tmp_path / "data" / "sessions").is_dir()


def test_default_config_path_is_root():
    assert DEFAULT_CONFIG_PATH.name == "config.json"
    assert DEFAULT_CONFIG_PATH.parent.name == "VeeeeryFormalResponses"
