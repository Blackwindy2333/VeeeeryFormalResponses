"""公文回复处理器：组装 system/user 消息与文档 metadata 契约。"""

from __future__ import annotations

import json
import re
from typing import Any

# 文种 → 收束语与写作提示
DOC_TYPE_GUIDANCE: dict[str, str] = {
    "报告": {
        "closing_hint": "可酌情以“特此报告”或自然收束结尾，不得写成请示。",
        "structure": "按情况/问题/分析/打算组织，先结论后依据。",
    },
    "通知": {
        "closing_hint": "可酌情以“特此通知”收束，事项、时间、要求要清楚。",
        "structure": "写明通知缘由、具体事项、时间安排与工作要求。",
    },
    "请示": {
        "closing_hint": "一般以“妥否，请批示”征询意见，一文一事。",
        "structure": "说明请示缘由、具体事项与明确请求，不夹带报告内容。",
    },
    "函": {
        "closing_hint": "可酌情以“特此函告”“请予支持为盼”等收束。",
        "structure": "平等协商语气，说明事由、事项与希望对方如何办理。",
    },
    "意见": {
        "closing_hint": "可提出“以上意见供参考”或请求批转，视语境而定。",
        "structure": "先摆问题或形势，再分条提出意见与措施。",
    },
    "批复": {
        "closing_hint": "可用“此复”收束，态度明确。",
        "structure": "引述来文请示事项，表明同意或不同意及理由、要求。",
    },
    "通报": {
        "closing_hint": "可自然收束或提出希望要求。",
        "structure": "交代事实经过，分析性质意义，提出要求。",
    },
    "纪要": {
        "closing_hint": "可自然收束，条理化记录议定事项。",
        "structure": "概括会议情况，分条记录议定事项与责任分工。",
    },
    "说明": {
        "closing_hint": "可“特此说明”或自然收束。",
        "structure": "围绕需说明的事项，客观、准确、简明陈述。",
    },
}

_SYSTEM_TEMPLATE = """你是公文写作助手。用户将提出问题或任务，你须以正式、克制、准确的书面公文语体作答。

## 输出契约（必须严格遵守）

1. 回复的**第一个代码块**必须是 JSON metadata，且仅包含标题字段，格式：

```json
{{"document": {{"title": "关于{{事项}}的{{文种}}"}}}}
```

- title 必须是单行字符串，长度不超过 28 个汉字或 56 个字符。
- 事项须同时说明对象和核心动作/范围；文种使用用户指定或上下文合适的类型（如报告、通知、请示、函、说明等）。
- 不要输出其他 metadata 字段。

2. metadata 之后使用普通 Markdown 书写正文。代码、命令、表格、JSON、路径等保持原有格式，不要改写为仿宋语体或公文套话。

## 文风要求

- 先识别用户要解决的问题、回复目的、已知事实与约束；围绕一个中心组织回复。
- 准确、明确、可核验；数字、日期、名称口径一致；不虚构背景、依据、身份或执行结果。
- 简明、平实、庄重；先结论后依据；一句能说清的不拆成多句。
- 结构严谨：可用“一、”“（一）”“1.”“（1）”等层次序号，同层级语法粒度一致。
- 标题直接概括主题和事由，不用夸张、双关或吸引眼球式标题。
- 惯用语仅在功能需要时使用（为……/根据……/现将……说明如下/一是……二是……/因此/为此等）；没有真实依据时不得写“根据××文件”。
- 不得伪造印章、发文字号、密级、国徽、法定效力或政府授权。

## 文种指引

当前文种：{doc_type}
{doc_type_extra}

## 落款区说明

界面会在正文后自动渲染结束语、署名与日期，你**不要**在正文末尾重复书写“此致”、署名或日期。
"""


def build_system_prompt(doc_type: str = "报告", extra: str | None = None) -> str:
    guidance = DOC_TYPE_GUIDANCE.get(doc_type, DOC_TYPE_GUIDANCE["说明"])
    extra_line = f"- 结构：{guidance['structure']}\n- 收束：{guidance['closing_hint']}"
    if extra:
        extra_line += f"\n- 补充：{extra}"
    return _SYSTEM_TEMPLATE.format(doc_type=doc_type or "报告", doc_type_extra=extra_line)


def build_messages(
    history: list[dict[str, Any]],
    doc_type: str = "报告",
    system_extra: str | None = None,
) -> list[dict[str, Any]]:
    """组装 Chat Completions messages；注入公文 system prompt。"""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(doc_type, system_extra)}
    ]
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant", "system", "tool"} or content is None:
            continue
        text = str(content)
        # 跳过空消息（例如流式占位 assistant），避免污染上下文
        if role in {"user", "assistant"} and not text.strip():
            continue
        messages.append({"role": role, "content": text})
    return messages


def parse_document_title(text: str) -> str | None:
    """从模型输出解析 document.title；失败返回 None。"""
    if not text:
        return None
    for block in _iter_json_fences(text):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        title = None
        if isinstance(obj, dict):
            doc = obj.get("document") or obj.get("codex_document") or obj
            if isinstance(doc, dict):
                title = doc.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return None


def _iter_json_fences(text: str) -> list[str]:
    """取出所有 ```json / ``` 代码块内容。"""
    return re.findall(r"```(?:json)?\s*\n([\s\S]*?)```", text, flags=re.IGNORECASE)


def split_meta_and_body(text: str) -> tuple[str | None, str]:
    """拆出标题与正文（去掉 metadata 代码块）。"""
    title = parse_document_title(text)
    if not title:
        return None, text.strip()

    def _drop_meta(match: re.Match[str]) -> str:
        block = match.group(1)
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            return match.group(0)
        if isinstance(obj, dict) and (
            "document" in obj or "codex_document" in obj or "title" in obj
        ):
            return ""
        return match.group(0)

    body = re.sub(
        r"```(?:json)?\s*\n([\s\S]*?)```",
        _drop_meta,
        text,
        flags=re.IGNORECASE,
    )
    return title, body.strip()


def transform_prompt(mode: str, body: str) -> str:
    if mode == "formal":
        return (
            "请将下文改写为正式公文语体，保持事实不变，输出公文格式回复：\n\n" + body
        )
    return "请将下文改写为通俗易懂的白话说明，保持事实不变：\n\n" + body
