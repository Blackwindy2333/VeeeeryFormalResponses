import { $, $all, toast, debounce } from "./util.js";
import { store } from "./store.js";
import { renderSessionList } from "./document.js";
import {
  renderMessages,
  sendMessage,
  stopGenerate,
  copyMessageDoc,
  regenerate,
  transformMessage,
  exportLastAsPrint,
  scrollToBottom,
  setStatus,
} from "./chat.js";
import {
  bindSettingsEvents,
  applyThemeFromConfig,
  openSettings,
} from "./settings.js";

function renderSessions() {
  const list = $("#session-list");
  if (!list) return;
  const filter = $("#session-search")?.value || "";
  list.innerHTML = renderSessionList(
    store.state.sessions,
    store.state.activeSessionId,
    filter
  );
}

function refreshDocTypeOptions() {
  const select = $("#doc-type");
  if (!select) return;
  const types =
    store.state.config?.document?.doc_types || [
      "报告",
      "通知",
      "请示",
      "函",
      "意见",
      "批复",
      "通报",
      "纪要",
      "说明",
    ];
  const current = store.state.ui.docType || store.state.config?.document?.default_doc_type || "报告";
  select.innerHTML = types
    .map((t) => `<option value="${t}" ${t === current ? "selected" : ""}>${t}</option>`)
    .join("");
}

function refreshComposerToggles() {
  const thinking = $("#toggle-thinking");
  const tools = $("#toggle-tools");
  const effort = $("#thinking-effort");
  if (thinking) thinking.checked = !!store.state.ui.thinkingEnabled;
  if (tools) tools.checked = !!store.state.ui.toolsEnabled;
  if (effort) effort.value = store.state.ui.thinkingEffort || "medium";
  const effortChip = $("#thinking-effort")?.closest(".chip");
  if (effortChip) effortChip.style.opacity = thinking?.checked ? "1" : "0.55";
}

function autoResizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
}

function bindSidebar() {
  $("#btn-new-chat")?.addEventListener("click", () => {
    store.createSession();
    renderSessions();
    renderMessages();
    $("#input-box")?.focus();
  });

  $("#btn-toggle-sidebar")?.addEventListener("click", () => {
    $("#app")?.classList.toggle("sidebar-collapsed");
  });
  $("#btn-open-sidebar")?.addEventListener("click", () => {
    $("#app")?.classList.toggle("sidebar-open");
  });

  $("#session-search")?.addEventListener(
    "input",
    debounce(() => renderSessions(), 150)
  );

  $("#session-list")?.addEventListener("click", (e) => {
    const actBtn = e.target.closest("[data-act]");
    if (actBtn) {
      e.stopPropagation();
      const id = actBtn.dataset.id;
      const act = actBtn.dataset.act;
      if (act === "delete") {
        if (confirm("删除该对话？")) {
          store.deleteSession(id);
          renderSessions();
          renderMessages();
        }
      } else if (act === "rename") {
        const s = store.state.sessions.find((x) => x.id === id);
        const title = prompt("重命名对话", s?.title || "");
        if (title != null && title.trim()) {
          store.renameSession(id, title.trim());
          renderSessions();
          renderMessages();
        }
      }
      return;
    }
    const item = e.target.closest("[data-session-id]");
    if (!item) return;
    store.patch({ activeSessionId: item.dataset.sessionId });
    renderSessions();
    renderMessages();
    scrollToBottom(false);
  });
}

function bindComposer() {
  const input = $("#input-box");
  input?.addEventListener("input", () => autoResizeTextarea(input));
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  });

  $("#btn-send")?.addEventListener("click", doSend);
  $("#btn-stop")?.addEventListener("click", () => {
    stopGenerate();
    setStatus("已停止");
  });

  $("#doc-type")?.addEventListener("change", (e) => {
    store.patchUi({ docType: e.target.value });
  });
  $("#toggle-thinking")?.addEventListener("change", (e) => {
    store.patchUi({ thinkingEnabled: e.target.checked });
    refreshComposerToggles();
  });
  $("#toggle-tools")?.addEventListener("change", (e) => {
    store.patchUi({ toolsEnabled: e.target.checked });
  });
  $("#thinking-effort")?.addEventListener("change", (e) => {
    store.patchUi({ thinkingEffort: e.target.value });
  });

  $all(".welcome-card").forEach((card) => {
    card.addEventListener("click", () => {
      const prompt = card.dataset.prompt || "";
      if (input) {
        input.value = prompt;
        autoResizeTextarea(input);
        input.focus();
      }
    });
  });
}

function bindHeader() {
  $("#btn-theme")?.addEventListener("click", () => {
    const next = store.state.ui.theme === "dark" ? "light" : "dark";
    store.patchUi({ theme: next });
    if (store.state.config) {
      store.state.config.ui = { ...store.state.config.ui, theme: next };
    }
    applyThemeFromConfig();
  });

  $("#btn-export-pdf")?.addEventListener("click", () => exportLastAsPrint());

  $("#btn-copy-last")?.addEventListener("click", async () => {
    const session = store.getActiveSession();
    const last = [...(session?.messages || [])].reverse().find((m) => m.role === "assistant");
    if (!last) {
      toast("没有可复制的公文");
      return;
    }
    await copyMessageDoc(last.id);
  });
}

function bindMessageActions() {
  $("#messages")?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    const act = btn.dataset.act;
    if (act === "copy-doc") await copyMessageDoc(id);
    else if (act === "regen") await regenerate(id);
    else if (act === "to-formal") await transformMessage(id, "formal");
    else if (act === "to-plain") await transformMessage(id, "plain");
  });
}

async function doSend() {
  const input = $("#input-box");
  const text = (input?.value || "").trim();
  if (!text) return;
  input.value = "";
  autoResizeTextarea(input);
  await sendMessage(text);
  renderSessions();
}

async function loadConfigFromBackend() {
  try {
    const { api } = await import("./api.js");
    const result = await api.getConfig();
    if (result?.config) {
      store.patch({ config: result.config });
    }
    setStatus("已连接本地服务");
  } catch {
    // 离线/未启动后端：使用默认配置缓存
    if (!store.state.config) {
      store.state.config = {
        schema_version: 1,
        document: {
          masthead: "演示单位（示例）",
          greeting: "尊敬的阅办人：",
          closing: "此致",
          signature: "智能助手",
          role_title: "",
          indent_paragraphs: true,
          hierarchy_fonts: true,
          doc_types: ["报告", "通知", "请示", "函", "意见", "批复", "通报", "纪要", "说明"],
          default_doc_type: "报告",
        },
        ui: { theme: "light", font_scale: 1, stream: true, show_token_usage: true },
        providers: [],
        sampling: { temperature: 1, top_p: 0.95, max_tokens: 4096 },
      };
    }
    setStatus("本地服务未连接（仅界面模式）");
  }
}

function bindStore() {
  store.subscribe(() => {
    // 避免全量重绘打断输入；仅在需要时刷新侧栏标题
  });
}

async function main() {
  bindSidebar();
  bindComposer();
  bindHeader();
  bindMessageActions();
  bindSettingsEvents();
  bindStore();
  await loadConfigFromBackend();
  applyThemeFromConfig();
  refreshDocTypeOptions();
  refreshComposerToggles();
  renderSessions();
  renderMessages();
  setStatus("就绪");
}

main();
