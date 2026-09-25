"""文风 prompt 与标题解析测试。"""

from __future__ import annotations

from server.prompt import (
    DOC_TYPE_GUIDANCE,
    build_messages,
    build_system_prompt,
    parse_document_title,
    split_meta_and_body,
    transform_prompt,
)


def test_system_prompt_contains_contract_and_doc_type():
    sp = build_system_prompt("请示")
    assert "document" in sp
    assert "title" in sp
    assert "请示" in sp
    assert "妥否，请批示" in sp
    assert "不得伪造印章" in sp


def test_all_doc_types_have_guidance():
    for doc_type in DOC_TYPE_GUIDANCE:
        sp = build_system_prompt(doc_type)
        assert doc_type in sp
        assert DOC_TYPE_GUIDANCE[doc_type]["structure"][:2] in sp


def test_build_messages_injects_system_first():
    msgs = build_messages(
        [
            {"role": "user", "content": "写个通知"},
            {"role": "assistant", "content": "好的"},
            {"role": "system", "content": "补充约束"},
        ],
        doc_type="通知",
    )
    assert msgs[0]["role"] == "system"
    assert "通知" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert msgs[-1]["content"] == "补充约束"


def test_build_messages_skips_invalid():
    msgs = build_messages(
        [
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": None},
            {"nope": 1},
        ]
    )
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user"]


def test_parse_title_ok():
    text = (
        '```json\n{"document": {"title": "关于开展专项检查的通知"}}\n```\n\n正文开始。'
    )
    assert parse_document_title(text) == "关于开展专项检查的通知"


def test_parse_title_codex_compat():
    text = '```json\n{"codex_document": {"title": "关于项目进展的报告"}}\n```\n正文'
    assert parse_document_title(text) == "关于项目进展的报告"


def test_parse_title_missing():
    assert parse_document_title("没有 metadata") is None
    assert parse_document_title("```json\n{bad}\n```") is None
    assert parse_document_title("```json\n{\"document\": {\"title\": \"  \"}}\n```") is None


def test_split_meta_and_body():
    text = '```json\n{"document": {"title": "关于A的报告"}}\n```\n\n## 一、情况\n\n正文。'
    title, body = split_meta_and_body(text)
    assert title == "关于A的报告"
    assert "metadata" not in body
    assert "一、情况" in body
    assert "```" not in body


def test_transform_prompt_modes():
    formal = transform_prompt("formal", "明天开会")
    plain = transform_prompt("plain", "明天开会")
    assert "公文" in formal
    assert "白话" in plain
    assert "明天开会" in formal
