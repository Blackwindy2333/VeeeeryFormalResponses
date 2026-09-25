import { $, toast, escapeHtml } from "./util.js";
import { store } from "./store.js";

function providerFormHtml(provider, index, activeId) {
  const isActive = provider.id === activeId;
  return `
  <div class="provider-card${isActive ? " active-provider" : ""}" data-provider-index="${index}">
    <div class="provider-head">
      <span class="name">${escapeHtml(provider.nickname || provider.id)}</span>
      <label class="chip"><input type="radio" name="active-provider" value="${escapeHtml(provider.id)}" ${isActive ? "checked" : ""} /> 设为当前</label>
      <button type="button" class="ghost-btn" data-act="remove-provider" data-index="${index}">删除</button>
    </div>
    <div class="form-grid">
      <div class="form-field">
        <label>模型昵称（显示用）</label>
        <input type="text" data-field="nickname" value="${escapeHtml(provider.nickname || "")}" />
      </div>
      <div class="form-field">
        <label>模型名称（API 调用）</label>
        <input type="text" data-field="model" value="${escapeHtml(provider.model || "")}" />
      </div>
      <div class="form-field">
        <label>Base URL</label>
        <input type="text" data-field="base_url" value="${escapeHtml(provider.base_url || "")}" />
      </div>
      <div class="form-field">
        <label>API Key</label>
        <input type="password" data-field="api_key" value="${escapeHtml(provider.api_key || "")}" placeholder="sk-..." />
      </div>
      <div class="switch-row">
        <span>思考开关</span>
        <input type="checkbox" data-field="thinking.enabled" ${provider.thinking?.enabled ? "checked" : ""} />
      </div>
      <div class="form-field">
        <label>思考强度</label>
        <select data-field="thinking.effort">
          <option value="low" ${provider.thinking?.effort === "low" ? "selected" : ""}>低</option>
          <option value="medium" ${provider.thinking?.effort === "medium" ? "selected" : ""}>中</option>
          <option value="high" ${provider.thinking?.effort === "high" ? "selected" : ""}>高</option>
        </select>
      </div>
      <div class="switch-row">
        <span>工具调用</span>
        <input type="checkbox" data-field="tools_enabled" ${provider.tools_enabled ? "checked" : ""} />
      </div>
    </div>
  </div>`;
}

export function renderSettings() {
  const body = $("#settings-body");
  if (!body) return;
  const config = store.state.config;
  if (!config) {
    body.innerHTML = `<p>正在加载配置…</p>`;
    return;
  }
  const providers = config.providers || [];
  const activeId = config.active_provider_id;
  body.innerHTML = `
    <section class="form-section">
      <h3>模型提供商</h3>
      <div id="provider-list">
        ${providers.map((p, i) => providerFormHtml(p, i, activeId)).join("")}
      </div>
      <button type="button" class="ghost-btn" id="btn-add-provider">+ 添加提供商</button>
    </section>

    <section class="form-section">
      <h3>公文落款与版式</h3>
      <div class="form-grid">
        <div class="form-field"><label>题头（发文机关标志）</label>
          <input type="text" data-doc="masthead" value="${escapeHtml(config.document?.masthead || "")}" /></div>
        <div class="form-field"><label>称谓</label>
          <input type="text" data-doc="greeting" value="${escapeHtml(config.document?.greeting || "")}" /></div>
        <div class="form-field"><label>结束语</label>
          <input type="text" data-doc="closing" value="${escapeHtml(config.document?.closing || "")}" /></div>
        <div class="form-field"><label>署名</label>
          <input type="text" data-doc="signature" value="${escapeHtml(config.document?.signature || "")}" /></div>
        <div class="form-field"><label>职务（可选）</label>
          <input type="text" data-doc="role_title" value="${escapeHtml(config.document?.role_title || "")}" /></div>
        <div class="switch-row"><span>正文首行缩进二字</span>
          <input type="checkbox" data-doc="indent_paragraphs" ${config.document?.indent_paragraphs !== false ? "checked" : ""} /></div>
        <div class="switch-row"><span>层次序号字体（黑/楷/仿宋）</span>
          <input type="checkbox" data-doc="hierarchy_fonts" ${config.document?.hierarchy_fonts !== false ? "checked" : ""} /></div>
      </div>
    </section>

    <section class="form-section">
      <h3>界面与生成</h3>
      <div class="form-grid">
        <div class="form-field"><label>主题</label>
          <select data-ui="theme">
            <option value="light" ${config.ui?.theme !== "dark" ? "selected" : ""}>浅色</option>
            <option value="dark" ${config.ui?.theme === "dark" ? "selected" : ""}>深色（公文纸面仍为浅色）</option>
          </select></div>
        <div class="form-field"><label>界面字号（倍率）</label>
          <div class="range-row">
            <input type="range" min="0.9" max="1.2" step="0.05" data-ui="font_scale" value="${config.ui?.font_scale ?? 1}" />
            <span id="font-scale-val">${config.ui?.font_scale ?? 1}</span>
          </div>
        </div>
        <div class="switch-row"><span>流式输出</span>
          <input type="checkbox" data-ui="stream" ${config.ui?.stream !== false ? "checked" : ""} /></div>
        <div class="switch-row"><span>显示 Token 用量</span>
          <input type="checkbox" data-ui="show_token_usage" ${config.ui?.show_token_usage !== false ? "checked" : ""} /></div>
        <div class="form-field"><label>Temperature</label>
          <input type="number" step="0.1" min="0" max="2" data-sampling="temperature" value="${config.sampling?.temperature ?? 1}" /></div>
        <div class="form-field"><label>Top P</label>
          <input type="number" step="0.05" min="0" max="1" data-sampling="top_p" value="${config.sampling?.top_p ?? 0.95}" /></div>
        <div class="form-field"><label>Max Tokens</label>
          <input type="number" min="256" max="32768" data-sampling="max_tokens" value="${config.sampling?.max_tokens ?? 4096}" /></div>
      </div>
    </section>
  `;
}

function collectSettingsFromDom() {
  const config = structuredClone(store.state.config || {});
  const body = $("#settings-body");

  // providers
  const cards = [...body.querySelectorAll(".provider-card")];
  const providers = cards.map((card) => {
    const get = (sel) => card.querySelector(sel);
    const field = (name) => card.querySelector(`[data-field="${name}"]`);
    const existing = config.providers?.[Number(card.dataset.providerIndex)] || {};
    return {
      ...existing,
      id: existing.id || `provider-${Math.random().toString(36).slice(2, 8)}`,
      nickname: field("nickname")?.value?.trim() || "未命名",
      model: field("model")?.value?.trim() || "",
      base_url: field("base_url")?.value?.trim() || "",
      api_key: field("api_key")?.value || "",
      thinking: {
        enabled: !!field("thinking.enabled")?.checked,
        effort: field("thinking.effort")?.value || "medium",
      },
      tools_enabled: !!field("tools_enabled")?.checked,
    };
  });
  config.providers = providers;
  const active = body.querySelector('input[name="active-provider"]:checked');
  config.active_provider_id = active?.value || providers[0]?.id;

  config.document = {
    ...config.document,
    masthead: body.querySelector('[data-doc="masthead"]')?.value?.trim() || "",
    greeting: body.querySelector('[data-doc="greeting"]')?.value?.trim() || "",
    closing: body.querySelector('[data-doc="closing"]')?.value?.trim() || "",
    signature: body.querySelector('[data-doc="signature"]')?.value?.trim() || "",
    role_title: body.querySelector('[data-doc="role_title"]')?.value?.trim() || "",
    indent_paragraphs: !!body.querySelector('[data-doc="indent_paragraphs"]')?.checked,
    hierarchy_fonts: !!body.querySelector('[data-doc="hierarchy_fonts"]')?.checked,
  };

  config.ui = {
    ...config.ui,
    theme: body.querySelector('[data-ui="theme"]')?.value || "light",
    font_scale: Number(body.querySelector('[data-ui="font_scale"]')?.value || 1),
    stream: !!body.querySelector('[data-ui="stream"]')?.checked,
    show_token_usage: !!body.querySelector('[data-ui="show_token_usage"]')?.checked,
  };

  config.sampling = {
    temperature: Number(body.querySelector('[data-sampling="temperature"]')?.value ?? 1),
    top_p: Number(body.querySelector('[data-sampling="top_p"]')?.value ?? 0.95),
    max_tokens: Number(body.querySelector('[data-sampling="max_tokens"]')?.value ?? 4096),
  };
  return config;
}

export async function saveSettings() {
  const config = collectSettingsFromDom();
  store.patch({ config });
  try {
    const { api } = await import("./api.js");
    const saved = await api.saveConfig(config);
    if (saved?.config) store.patch({ config: saved.config });
    toast("设置已保存");
    applyThemeFromConfig();
  } catch (err) {
    // 后端未启动时仍保存到 localStorage
    toast(`已保存到本地（后端未连接：${err?.message || err}）`);
    applyThemeFromConfig();
  }
}

export function applyThemeFromConfig() {
  const theme = store.state.config?.ui?.theme || store.state.ui.theme || "light";
  document.documentElement.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
  const scale = store.state.config?.ui?.font_scale || store.state.ui.fontScale || 1;
  document.documentElement.style.setProperty("--font-scale", String(scale));
  store.patchUi({ theme, fontScale: scale });
}

export function openSettings() {
  const root = $("#settings-root");
  renderSettings();
  root.hidden = false;
}

export function closeSettings() {
  $("#settings-root").hidden = true;
}

export function bindSettingsEvents() {
  $("#btn-settings")?.addEventListener("click", openSettings);
  $("#btn-close-settings")?.addEventListener("click", closeSettings);
  $("#settings-backdrop")?.addEventListener("click", closeSettings);
  $("#btn-settings-save")?.addEventListener("click", () => {
    saveSettings();
    closeSettings();
  });
  $("#btn-settings-reset")?.addEventListener("click", async () => {
    try {
      const { api } = await import("./api.js");
      const result = await api.resetConfig();
      store.patch({ config: result.config });
      renderSettings();
      applyThemeFromConfig();
      toast("已恢复默认设置");
    } catch {
      toast("恢复默认需要后端服务");
    }
  });

  $("#settings-body")?.addEventListener("click", (e) => {
    const add = e.target.closest("#btn-add-provider");
    if (add) {
      const config = collectSettingsFromDom();
      config.providers.push({
        id: `provider-${Math.random().toString(36).slice(2, 8)}`,
        nickname: "新提供商",
        base_url: "https://api.example.com/v1",
        api_key: "",
        model: "model-name",
        thinking: { enabled: false, effort: "medium" },
        tools_enabled: false,
        extra_headers: {},
      });
      store.patch({ config });
      renderSettings();
      return;
    }
    const remove = e.target.closest('[data-act="remove-provider"]');
    if (remove) {
      const config = collectSettingsFromDom();
      const idx = Number(remove.dataset.index);
      if (config.providers.length <= 1) {
        toast("至少保留一个提供商");
        return;
      }
      config.providers.splice(idx, 1);
      if (!config.providers.some((p) => p.id === config.active_provider_id)) {
        config.active_provider_id = config.providers[0].id;
      }
      store.patch({ config });
      renderSettings();
    }
  });

  $("#settings-body")?.addEventListener("input", (e) => {
    if (e.target.matches('[data-ui="font_scale"]')) {
      const val = e.target.value;
      const label = $("#font-scale-val");
      if (label) label.textContent = val;
    }
  });
}
