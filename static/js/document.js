import { escapeHtml, renderMarkdownLite, formatDateGroup } from "./util.js";

/**
 * 解析模型回复中的文档 metadata。
 * 约定：首个 JSON 代码块可含 { "document": { "title": "..." } }
 * 兼容 codex_document.title。
 */
export function parseDocumentMeta(raw) {
  const text = String(raw ?? "");
  const re = /```(?:json)?\s*\n([\s\S]*?)```/i;
  const m = text.match(re);
  if (m) {
    try {
      const obj = JSON.parse(m[1]);
      const title = obj?.document?.title || obj?.codex_document?.title || obj?.title;
      if (title && typeof title === "string") {
        return {
          title: title.trim(),
          body: text.replace(re, "").trim(),
          metaBlock: m[0],
        };
      }
    } catch {
      /* fallthrough */
    }
  }
  return { title: "", body: text.trim(), metaBlock: "" };
}

export function buildDocumentHtml({
  meta,
  bodyText,
  config,
  streaming = false,
  docType = "报告",
  usage = null,
  elapsedMs = null,
}) {
  const doc = config?.document || {};
  const masthead = escapeHtml(doc.masthead || "演示单位（示例）");
  const greeting = escapeHtml(doc.greeting || "尊敬的阅办人：");
  const closing = escapeHtml(doc.closing || "此致");
  const signature = escapeHtml(doc.signature || "智能助手");
  const roleTitle = escapeHtml(doc.roleTitle || "");
  const title = escapeHtml(meta?.title || "（未识别标题）");
  const now = new Date();
  const dateStr = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`;
  const className = [
    "doc-body",
    doc.indent_paragraphs !== false ? "indent" : "",
    doc.hierarchy_fonts !== false ? "hierarchy" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const bodyHtml = renderMarkdownLite(bodyText || "");
  const badges = [];
  badges.push(`<span class="doc-badge">文种：${escapeHtml(docType)}</span>`);
  if (streaming) badges.push(`<span class="doc-badge">生成中</span>`);
  if (usage) {
    badges.push(
      `<span class="doc-badge">tokens ${usage.prompt_tokens ?? "-"} / ${usage.completion_tokens ?? "-"}</span>`
    );
  }
  if (elapsedMs != null) {
    badges.push(`<span class="doc-badge">耗时 ${(elapsedMs / 1000).toFixed(1)}s</span>`);
  }

  return `
<article class="doc-paper${streaming ? " streaming" : ""}" data-doc-root>
  <div class="doc-badges">${badges.join("")}</div>
  <header class="doc-masthead">${masthead}</header>
  <hr class="doc-rule" />
  <div class="doc-meta-line">
    <span>文种：${escapeHtml(docType)}</span>
    <span>${dateStr}</span>
  </div>
  <h1 class="doc-title">${title}</h1>
  <p class="doc-greeting">${greeting}</p>
  <div class="${className}">${bodyHtml}</div>
  <p class="doc-closing">${closing}</p>
  <div class="doc-sign-block">
    ${roleTitle ? `<div class="role">${roleTitle}</div>` : ""}
    <div class="name">${signature}</div>
    <div class="date">${dateStr}</div>
  </div>
  <p class="doc-note">说明：本文为演示界面生成内容，不具有法定公文效力。</p>
</article>`;
}

export function renderSessionList(sessions, activeId, filter = "") {
  const keyword = filter.trim().toLowerCase();
  const filtered = sessions.filter((s) =>
    !keyword ? true : (s.title || "").toLowerCase().includes(keyword)
  );
  if (!filtered.length) {
    return `<div class="session-group">暂无对话</div>`;
  }
  const groups = new Map();
  for (const s of filtered) {
    const g = formatDateGroup(s.updatedAt || s.createdAt);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(s);
  }
  let html = "";
  for (const [group, items] of groups) {
    html += `<div class="session-group"><span>${escapeHtml(group)}</span></div>`;
    for (const s of items) {
      html += `
        <button class="session-item${s.id === activeId ? " active" : ""}" data-session-id="${s.id}" type="button">
          <span class="title">${escapeHtml(s.title || "未命名")}</span>
          <span class="ops">
            <button type="button" data-act="rename" data-id="${s.id}" title="重命名">✎</button>
            <button type="button" data-act="delete" data-id="${s.id}" title="删除">✕</button>
          </span>
        </button>`;
    }
  }
  return html;
}

export function plainTextFromMarkdown(md) {
  return String(md || "")
    .replace(/```[\s\S]*?```/g, (block) => block.replace(/```[^\n]*\n?/g, "").replace(/```$/g, ""))
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

export function extractDocumentPlain(meta, bodyText, config, docType) {
  const doc = config?.document || {};
  const now = new Date();
  const dateStr = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`;
  const lines = [
    doc.masthead || "",
    "————————————",
    meta?.title || "（未识别标题）",
    "",
    doc.greeting || "",
    "",
    plainTextFromMarkdown(bodyText),
    "",
    doc.closing || "",
    `${doc.roleTitle ? doc.roleTitle + "\n" : ""}${doc.signature || ""}`,
    dateStr,
    "",
    `（文种：${docType}；演示生成，无法定效力）`,
  ];
  return lines.join("\n");
}
