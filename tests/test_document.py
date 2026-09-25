"""公文视图与导出文本测试。"""

from __future__ import annotations

from server.config import default_config
from server.document import build_document_view, document_date, to_docx_paragraphs, to_plain_text


def test_build_document_view_fields():
    raw = (
        '```json\n{"document": {"title": "关于节前安全检查的通知"}}\n```\n\n'
        "一、检查安排\n\n请各部门于节前完成自查。"
    )
    cfg = default_config()
    cfg["document"]["masthead"] = "某某公司"
    cfg["document"]["signature"] = "办公室"
    view = build_document_view(raw, cfg, doc_type="通知")
    assert view["title"] == "关于节前安全检查的通知"
    assert view["title_display"] == "关于节前安全检查的通知"
    assert view["masthead"] == "某某公司"
    assert view["signature"] == "办公室"
    assert view["doc_type"] == "通知"
    assert "一、检查安排" in view["body"]
    assert "```" not in view["body"]
    assert view["date"] == document_date()


def test_build_document_view_missing_title():
    view = build_document_view("直接正文", default_config())
    assert view["title"] is None
    assert view["title_display"] == "（未识别标题）"


def test_to_plain_text():
    raw = '```json\n{"document": {"title": "关于A的报告"}}\n```\n## 一、情况\n\n**重点**内容。'
    view = build_document_view(raw, default_config(), doc_type="报告")
    text = to_plain_text(view)
    assert "关于A的报告" in text
    assert "一、情况" in text
    assert "**" not in text
    assert "无法定效力" in text
    assert "此致" in text


def test_to_docx_paragraphs_structure():
    raw = '```json\n{"document": {"title": "关于B的函"}}\n```\n正文一段。\n\n正文二段。'
    view = build_document_view(raw, default_config(), doc_type="函")
    paras = to_docx_paragraphs(view)
    styles = [s for s, _ in paras]
    assert "Masthead" in styles
    assert "Title" in styles
    assert "Greeting" in styles
    assert "Body" in styles
    assert "Closing" in styles
    assert "Sign" in styles
