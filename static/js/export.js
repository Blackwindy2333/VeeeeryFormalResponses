import { toast } from "./util.js";
import { store } from "./store.js";

/** 将当前会话同步到后端（若可用） */
export async function syncSessionToBackend(session) {
  if (!session?.id) return;
  try {
    await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session }),
    });
  } catch {
    /* 离线忽略 */
  }
}

export async function deleteSessionRemote(id) {
  try {
    await fetch(`/api/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
  } catch {
    /* ignore */
  }
}

export async function loadSessionsFromBackend() {
  try {
    const res = await fetch("/api/sessions");
    if (!res.ok) return;
    const data = await res.json();
    const list = data.sessions || [];
    if (list.length && !store.state.sessions.length) {
      store.patch({
        sessions: list,
        activeSessionId: list[0].id,
      });
    }
  } catch {
    /* ignore */
  }
}

export async function exportCurrentAsText() {
  const session = store.getActiveSession();
  const last = [...(session?.messages || [])]
    .reverse()
    .find((m) => m.role === "assistant");
  if (!last) {
    toast("没有可导出的公文");
    return;
  }
  try {
    const { api } = await import("./api.js");
    const result = await api.exportText({
      content: last.content,
      doc_type: last.docType || store.state.ui.docType,
      config: store.state.config,
      usage: last.usage,
      elapsed_ms: last.elapsedMs,
    });
    if (result?.text) {
      await navigator.clipboard.writeText(result.text);
      toast("纯文本已复制到剪贴板");
    }
  } catch {
    const { extractDocumentPlain, parseDocumentMeta } = await import("./document.js");
    const parsed = last.parsed || parseDocumentMeta(last.content || "");
    const text = extractDocumentPlain(
      parsed,
      parsed.body || last.content,
      store.state.config,
      last.docType || store.state.ui.docType
    );
    await navigator.clipboard.writeText(text).catch(() => {});
    toast("已复制（离线模式）");
  }
}

export async function exportCurrentAsDocx() {
  const session = store.getActiveSession();
  const last = [...(session?.messages || [])]
    .reverse()
    .find((m) => m.role === "assistant");
  if (!last) {
    toast("没有可导出的公文");
    return;
  }
  try {
    const res = await fetch("/api/export/docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: last.content,
        doc_type: last.docType || store.state.ui.docType,
        config: store.state.config,
        usage: last.usage,
      }),
    });
    const data = await res.json();
    if (data.ok) {
      toast(`已导出 DOCX：${data.path}`);
    } else {
      toast(data.message || "DOCX 导出不可用，已用打印替代");
      window.print();
    }
  } catch {
    toast("导出失败，请使用「导出 PDF」打印");
  }
}
