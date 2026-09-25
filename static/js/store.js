import { uid } from "./util.js";

const LS_KEY = "veeeery_formal_state_v1";

function defaultState() {
  return {
    sessions: [],
    activeSessionId: null,
    ui: {
      theme: "light",
      fontScale: 1,
      sidebarCollapsed: false,
      docType: "报告",
      thinkingEnabled: false,
      thinkingEffort: "medium",
      toolsEnabled: false,
    },
    config: null, // 由后端加载；前端缓存
  };
}

function load() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    return { ...defaultState(), ...parsed, ui: { ...defaultState().ui, ...(parsed.ui || {}) } };
  } catch {
    return defaultState();
  }
}

function persist(state) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota */
  }
}

const listeners = new Set();

export const store = {
  state: load(),

  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },

  emit() {
    persist(this.state);
    for (const fn of listeners) fn(this.state);
  },

  patch(partial) {
    this.state = { ...this.state, ...partial };
    this.emit();
  },

  patchUi(partial) {
    this.state.ui = { ...this.state.ui, ...partial };
    this.emit();
  },

  createSession(title = "新对话") {
    const session = {
      id: uid("s"),
      title,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
      docType: this.state.ui.docType,
    };
    this.state.sessions = [session, ...this.state.sessions];
    this.state.activeSessionId = session.id;
    this.emit();
    return session;
  },

  getActiveSession() {
    return this.state.sessions.find((s) => s.id === this.state.activeSessionId) || null;
  },

  ensureActiveSession() {
    return this.getActiveSession() || this.createSession();
  },

  renameSession(id, title) {
    const s = this.state.sessions.find((x) => x.id === id);
    if (!s) return;
    s.title = title;
    s.updatedAt = Date.now();
    this.emit();
  },

  deleteSession(id) {
    this.state.sessions = this.state.sessions.filter((s) => s.id !== id);
    if (this.state.activeSessionId === id) {
      this.state.activeSessionId = this.state.sessions[0]?.id || null;
    }
    this.emit();
  },

  addMessage(sessionId, message) {
    const s = this.state.sessions.find((x) => x.id === sessionId);
    if (!s) return null;
    const msg = {
      id: uid("m"),
      createdAt: Date.now(),
      ...message,
    };
    s.messages.push(msg);
    s.updatedAt = Date.now();
    if (s.title === "新对话" && message.role === "user" && message.content) {
      s.title = String(message.content).slice(0, 24) || "新对话";
    }
    this.emit();
    return msg;
  },

  updateMessage(sessionId, messageId, partial) {
    const s = this.state.sessions.find((x) => x.id === sessionId);
    if (!s) return;
    const m = s.messages.find((x) => x.id === messageId);
    if (!m) return;
    Object.assign(m, partial);
    s.updatedAt = Date.now();
    this.emit();
  },
};
