import { $, $all, escapeHtml, toast, formatTime } from "./util.js";
import { store } from "./store.js";
import {
  buildDocumentHtml,
  parseDocumentMeta,
  extractDocumentPlain,
} from "./document.js";

let abortController = null;
let generating = false;

export function isGenerating() {
  return generating;
}

export function stopGenerate() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  generating = false;
  syncSendButtons();
}

function syncSendButtons() {
  const send = $("#btn-send");
  const stop = $("#btn-stop");
  if (!send || !stop) return;
  send.hidden = generating;
  stop.hidden = !generating;
  send.disabled = generating;
}

export function setGenerating(value) {
  generating = value;
  syncSendButtons();
}

export function renderMessages() {
  const session = store.getActiveSession();
  const welcome = $("#welcome");
  const messagesEl = $("#messages");
  const header = $("#header-title");
  if (!session || !session.messages.length) {
    welcome.hidden = false;
    messagesEl.hidden = true;
    messagesEl.innerHTML = "";
    header.textContent = "新对话";
    return;
  }
  welcome.hidden = true;
  messagesEl.hidden = false;
  header.textContent = session.title || "对话";

  const config = store.state.config;
  messagesEl.innerHTML = session.messages
    .map((m) => {
      if (m.role === "user") {
        return `
          <div class="msg-row user" data-mid="${m.id}">
            <div>
              <div class="msg-bubble">${escapeHtml(m.content)}</div>
              <div class="msg-meta" style="justify-content:flex-end">
                <span>${formatTime(m.createdAt)}</span>
              </div>
            </div>
          </div>`;
      }
      const parsed = m.parsed || parseDocumentMeta(m.content || "");
      const html = buildDocumentHtml({
        meta: parsed,
        bodyText: parsed.body || m.content || "",
        config,
        streaming: !!m.streaming,
        docType: m.docType || store.state.ui.docType,
        usage: m.usage || null,
        elapsedMs: m.elapsedMs ?? null,
      });
      return `
        <div class="msg-row assistant" data-mid="${m.id}">
          <div class="doc-host">
            ${html}
            <div class="msg-actions">
              <button type="button" data-act="copy-doc" data-id="${m.id}">复制正文</button>
              <button type="button" data-act="regen" data-id="${m.id}">重新生成</button>
              <button type="button" data-act="to-formal" data-id="${m.id}">转为公文</button>
              <button type="button" data-act="to-plain" data-id="${m.id}">转为白话</button>
            </div>
          </div>
        </div>`;
    })
    .join("");
}

export function scrollToBottom(smooth = true) {
  const el = $("#chat-scroll");
  if (!el) return;
  el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
}

function messagesToApi(session) {
  // 仅将用户/助手正文送入上下文，去掉 metadata 代码块
  return session.messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => {
      if (m.role === "user") return { role: "user", content: m.content };
      const parsed = m.parsed || parseDocumentMeta(m.content || "");
      return { role: "assistant", content: parsed.body || m.content || "" };
    });
}

export async function sendMessage(text, { regenerate = false, transform = null } = {}) {
  const content = (text || "").trim();
  if (!content && !regenerate && !transform) return;
  if (generating) return;

  const session = store.ensureActiveSession();
  if (transform) {
    store.addMessage(session.id, {
      role: "user",
      content: transform.prompt,
    });
  } else if (!regenerate && content) {
    store.addMessage(session.id, { role: "user", content });
  }

  const assistant = store.addMessage(session.id, {
    role: "assistant",
    content: "",
    streaming: true,
    docType: store.state.ui.docType,
  });

  renderMessages();
  scrollToBottom(false);
  setGenerating(true);
  setStatus("正在生成公文…");

  const started = Date.now();
  abortController = new AbortController();
  let full = "";
  let reasoning = "";

  try {
    const { api } = await import("./api.js");
    await api.streamChat({
      messages: messagesToApi(store.getActiveSession()),
      docType: store.state.ui.docType,
      thinkingEnabled: store.state.ui.thinkingEnabled,
      thinkingEffort: store.state.ui.thinkingEffort,
      toolsEnabled: store.state.ui.toolsEnabled,
      signal: abortController.signal,
      onDelta: (t) => {
        full += t;
        const parsed = parseDocumentMeta(full);
        // 流式更新当前 assistant 气泡
        updateAssistantLive(assistant.id, parsed, full, true);
      },
      onReasoning: (t) => {
        reasoning += t;
        setStatus("深度思考中…");
      },
      onDone: (payload) => {
        const parsed = parseDocumentMeta(full || payload?.content || "");
        store.updateMessage(session.id, assistant.id, {
          content: full || payload?.content || "",
          parsed,
          streaming: false,
          usage: payload?.usage || null,
          elapsedMs: Date.now() - started,
          reasoning: reasoning || null,
        });
      },
    });
  } catch (err) {
    if (err?.name === "AbortError") {
      const parsed = parseDocumentMeta(full);
      store.updateMessage(session.id, assistant.id, {
        content: full || "（已停止生成）",
        parsed,
        streaming: false,
        elapsedMs: Date.now() - started,
      });
      setStatus("已停止");
    } else {
      const parsed = parseDocumentMeta(full);
      store.updateMessage(session.id, assistant.id, {
        content:
          full ||
          `生成失败：${err?.message || err}\n\n请在「设置」中检查提供商 API Key、模型名称与网络。`,
        parsed,
        streaming: false,
        error: String(err?.message || err),
      });
      setStatus("生成失败");
      toast("生成失败，请检查设置");
    }
  } finally {
    abortController = null;
    setGenerating(false);
    renderMessages();
    scrollToBottom();
  }
}

function updateAssistantLive(mid, parsed, full, streaming) {
  const row = document.querySelector(`.msg-row[data-mid="${mid}"] .doc-host`);
  if (!row) return;
  const html = buildDocumentHtml({
    meta: parsed,
    bodyText: parsed.body || full || "",
    config: store.state.config,
    streaming,
    docType: store.state.ui.docType,
  });
  const actions = row.querySelector(".msg-actions");
  row.innerHTML = html;
  if (actions) row.appendChild(actions);
  scrollToBottom(false);
}

export function setStatus(text) {
  const el = $("#status-text");
  if (el) el.textContent = text;
}

export function setUsage(text) {
  const el = $("#usage-text");
  if (el) el.textContent = text;
}

export async function copyMessageDoc(mid) {
  const session = store.getActiveSession();
  const m = session?.messages.find((x) => x.id === mid);
  if (!m) return;
  const parsed = m.parsed || parseDocumentMeta(m.content || "");
  const text = extractDocumentPlain(
    parsed,
    parsed.body || m.content,
    store.state.config,
    m.docType || store.state.ui.docType
  );
  try {
    await navigator.clipboard.writeText(text);
    toast("已复制公文正文");
  } catch {
    toast("复制失败");
  }
}

export async function regenerate(mid) {
  const session = store.getActiveSession();
  if (!session) return;
  const idx = session.messages.findIndex((x) => x.id === mid);
  if (idx < 0) return;
  // 删除该助手消息后重新请求
  session.messages = session.messages.slice(0, idx);
  store.emit();
  await sendMessage("", { regenerate: true });
}

export async function transformMessage(mid, mode) {
  const session = store.getActiveSession();
  const m = session?.messages.find((x) => x.id === mid);
  if (!m) return;
  const parsed = m.parsed || parseDocumentMeta(m.content || "");
  const body = parsed.body || m.content || "";
  const prompt =
    mode === "formal"
      ? `请将下文改写为正式公文语体，保持事实不变，输出公文格式回复：\n\n${body}`
      : `请将下文改写为通俗易懂的白话说明，保持事实不变：\n\n${body}`;
  await sendMessage("", {
    transform: { prompt, sourceId: mid },
  });
}

export function exportLastAsPrint() {
  const session = store.getActiveSession();
  if (!session?.messages?.length) {
    toast("当前没有可导出的内容");
    return;
  }
  // 仅打印助手公文：给 body 临时加 class
  document.body.classList.add("printing-docs");
  window.print();
  document.body.classList.remove("printing-docs");
}
