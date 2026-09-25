/**
 * 与本地 Python 服务通信的 API 客户端。
 * 后端未就绪时返回友好错误，UI 仍可浏览会话。
 */

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  async getConfig() {
    return request("/api/config");
  },

  async saveConfig(config) {
    return request("/api/config", {
      method: "PUT",
      body: JSON.stringify(config),
    });
  },

  async resetConfig() {
    return request("/api/config/reset", { method: "POST" });
  },

  /**
   * 流式发送消息。
   * onDelta(text), onDone(payload), onReasoning(text)
   */
  async streamChat({ messages, docType, thinkingEnabled, thinkingEffort, toolsEnabled, signal, onDelta, onReasoning, onDone }) {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages,
        doc_type: docType,
        thinking_enabled: thinkingEnabled,
        thinking_effort: thinkingEffort,
        tools_enabled: toolsEnabled,
      }),
      signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `HTTP ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const line = part
          .split("\n")
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trim())
          .join("");
        if (!line) continue;
        let evt;
        try {
          evt = JSON.parse(line);
        } catch {
          continue;
        }
        if (evt.type === "delta" && onDelta) onDelta(evt.text || "");
        else if (evt.type === "reasoning" && onReasoning) onReasoning(evt.text || "");
        else if (evt.type === "done" && onDone) onDone(evt);
        else if (evt.type === "error") throw new Error(evt.message || "stream error");
      }
    }
  },

  async exportPdf(payload) {
    return request("/api/export/pdf", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
