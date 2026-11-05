/* Mango Control Room 0.2.0. No external frontend dependencies. */
(() => {
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const available = state => Boolean(state && !["unknown", "unavailable"].includes(state.state));
  const icon = name => `<ha-icon icon="${escape(name)}"></ha-icon>`;

  class MangoParameterCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = { title: "Mango Control Room", default_group: 14 };
      this._catalog = null;
      this._entry = null;
      this._group = 14;
      this._query = "";
      this._family = "";
      this._filter = "all";
      this._drafts = new Map();
      this._pending = new Set();
      this._messages = new Map();
      this._lastLoad = 0;
      this._busy = false;
      this._frame = null;
      this.shadowRoot.addEventListener("click", event => this._click(event));
      this.shadowRoot.addEventListener("input", event => this._input(event));
      this.shadowRoot.addEventListener("change", event => this._change(event));
      this.shadowRoot.addEventListener("keydown", event => {
        if (event.key === "Enter" && event.target.matches(".value-input")) {
          event.preventDefault();
          const p = this._parameters().find(p => p.key === event.target.dataset.key);
          if (p) this._apply(p);
        }
      });
    }

    static getStubConfig() { return { title: "Mango Control Room", default_group: 14 }; }
    static getConfigForm() {
      return { schema: [
        { name: "title", selector: { text: {} } },
        { name: "entry_id", selector: { text: {} } },
        { name: "default_group", selector: { number: { min: 0, max: 16, mode: "box" } } }
      ] };
    }
    getCardSize() { return 16; }
    getGridOptions() { return { columns: "full", min_columns: 12 }; }
    setConfig(config) {
      if (config.default_group !== undefined && (!Number.isInteger(Number(config.default_group)) || Number(config.default_group) < 0 || Number(config.default_group) > 16)) {
        throw new Error("default_group must be an integer from 0 to 16");
      }
      this._config = { title: "Mango Control Room", default_group: 14, ...config };
      this._group = Number(this._config.default_group);
      this._entry = config.entry_id || this._entry;
      this._draw();
    }
    set hass(value) {
      this._hass = value;
      if (!this._catalog || (!this._catalog.devices.length && Date.now() - this._lastLoad > 3000)) this._load();
      this._schedule();
    }
    get hass() { return this._hass; }
    connectedCallback() { this._draw(); this._load(); }
    disconnectedCallback() {
      if (this._frame !== null) cancelAnimationFrame(this._frame);
      this._frame = null;
      this._unsubscribe?.();
      this._unsubscribe = null;
    }
    _schedule() {
      if (this._frame !== null) return;
      this._frame = requestAnimationFrame(() => { this._frame = null; this._update(); });
    }
    async _load() {
      if (!this._hass || this._busy) return;
      this._busy = true;
      this._lastLoad = Date.now();
      try {
        const data = await this._hass.callWS({ type: "mango_tuya_local/dashboard" });
        if (!data || !Array.isArray(data.devices)) throw new Error("Invalid dashboard response");
        this._catalog = data;
        this._loadError = null;
        if (!this._config.entry_id && !this._entry) this._entry = data.devices[0]?.entry_id ?? null;
        if (!this._unsubscribe && this._hass.connection?.subscribeEvents) {
          const unsubscribe = await this._hass.connection.subscribeEvents(() => {
            clearTimeout(this._registryTimer);
            this._registryTimer = setTimeout(() => this._load(), 300);
          }, "entity_registry_updated");
          if (this.isConnected) this._unsubscribe = unsubscribe;
          else unsubscribe();
        }
      } catch (error) {
        this._loadError = error.message || "Dashboard data could not be loaded. Update Mango Tuya Local and restart Home Assistant.";
      } finally {
        this._busy = false;
        if (this.isConnected) this._draw();
      }
    }
    _device() { return this._catalog?.devices.find(d => d.entry_id === this._entry); }
    _parameters() { return this._device()?.groups.flatMap(g => g.parameters) || []; }
    _state(p) { return this._hass?.states[p.entity_id]; }
    _visible() {
      const device = this._device();
      if (!device) return [];
      const query = this._query.trim().toLowerCase();
      const rows = device.groups.flatMap(g => g.parameters.map(p => ({ ...p, category: g.title, group: g.group })));
      return rows.filter(p => {
        if (query) {
          if (!`${p.name} ${p.description} ${p.category} ${p.key} ${p.family}`.toLowerCase().includes(query)) return false;
        } else if (this._group !== -1 && p.group !== this._group) return false;
        if (!query && this._family && p.family !== this._family) return false;
        if (this._filter === "available" && !available(this._state(p))) return false;
        if (this._filter === "changed" && !this._drafts.has(p.key)) return false;
        return true;
      });
    }
    _valid(p, value) {
      const state = this._state(p);
      if (!available(state) || this._pending.has(p.key) || p.can_control === false) return false;
      if (p.domain === "select") return Array.isArray(state.attributes.options) && state.attributes.options.includes(value) && value !== state.state;
      if (String(value).trim() === "") return false;
      const n = Number(value), min = Number(state.attributes.min), max = Number(state.attributes.max), step = Number(state.attributes.step);
      if (![n, min, max, step].every(Number.isFinite) || step <= 0 || min === max || n < min || n > max || n === Number(state.state)) return false;
      const steps = (n - min) / step;
      return Math.abs(steps - Math.round(steps)) < 0.000001;
    }
    async _apply(p) {
      const input = [...this.shadowRoot.querySelectorAll(".value-input")].find(e => e.dataset.key === p.key);
      if (!input || !this._valid(p, input.value)) return;
      const requested = input.value;
      const entryId = this._entry;
      this._pending.add(p.key);
      this._messages.set(p.key, { kind: "wait", text: "Writing and checking device readback..." });
      this._update();
      try {
        await this._hass.callService(p.domain, p.domain === "number" ? "set_value" : "select_option", {
          entity_id: p.entity_id,
          ...(p.domain === "number" ? { value: Number(requested) } : { option: requested })
        });
        if (this._entry === entryId) {
          this._drafts.delete(p.key);
          this._messages.set(p.key, { kind: "ok", text: "The device confirmed this change." });
        }
      } catch (error) {
        if (this._entry === entryId) this._messages.set(p.key, { kind: "error", text: error.message || "The change could not be confirmed. Check the current value." });
      } finally {
        this._pending.delete(p.key);
        this._update();
      }
    }
    async _refresh() {
      const entityId = this._device()?.refresh_entity;
      const state = this._hass?.states[entityId];
      if (!entityId || !state || state.state === "unavailable") return;
      try {
        await this._hass.callService("button", "press", { entity_id: entityId });
        this._notice("A complete parameter refresh has been requested.");
      } catch (error) { this._notice(error.message || "Refresh could not start."); }
    }
    _notice(text) { const n = this.shadowRoot.querySelector(".notice"); if (n) { n.textContent = text; n.hidden = false; } }
    _click(event) {
      const button = event.target.closest("button");
      if (!button || button.disabled) return;
      if (button.dataset.group !== undefined) {
        this._group = Number(button.dataset.group); this._query = ""; this._family = "";
        const search = this.shadowRoot.querySelector(".search"); if (search) search.value = "";
        this._drawRows(); this._updateNav();
      } else if (button.dataset.family !== undefined) {
        this._family = button.dataset.family; this._drawRows();
      } else if (button.dataset.apply) {
        const p = this._parameters().find(p => p.key === button.dataset.apply); if (p) this._apply(p);
      } else if (button.dataset.info) {
        this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId: button.dataset.info } }));
      } else if (button.dataset.action === "refresh") this._refresh();
      else if (button.dataset.action === "reload") this._load();
      else if (button.dataset.action === "menu") this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    }
    _input(event) {
      if (event.target.matches(".search")) { this._query = event.target.value; this._drawRows(); this._updateNav(); }
      else if (event.target.matches(".value-input")) {
        if (this._pending.has(event.target.dataset.key)) return;
        this._drafts.set(event.target.dataset.key, event.target.value);
        this._messages.delete(event.target.dataset.key); this._update();
      }
    }
    _change(event) {
      if (event.target.matches(".device-select")) {
        if (this._pending.size) { event.target.value = this._entry; return; }
        this._entry = event.target.value; this._drafts.clear(); this._messages.clear(); this._family = ""; this._draw();
      } else if (event.target.matches(".filter")) { this._filter = event.target.value; this._drawRows(); }
      else if (event.target.matches(".value-input")) this._input(event);
    }
    _draw() {
      if (!this.shadowRoot) return;
      const device = this._device();
      const categories = device?.groups || [];
      const selector = (this._catalog?.devices.length || 0) > 1 && !this._config.entry_id
        ? `<select class="device-select" aria-label="Heat pump">${this._catalog.devices.map(d => `<option value="${escape(d.entry_id)}" ${d.entry_id === this._entry ? "selected" : ""}>${escape(d.name)}</option>`).join("")}</select>`
        : `<span class="device-name">${escape(device?.name || "Mango Energy")}</span>`;
      this.shadowRoot.innerHTML = `<style>${MangoParameterCard.styles}</style>
        <ha-card>
          <header>
            <div class="identity">${this._config.panel ? `<button class="menu icon-button" data-action="menu" aria-label="Open Home Assistant menu">${icon("mdi:menu")}</button>` : ""}<div class="brand-mark">M</div><div><div class="eyebrow">MANGO / LOCAL CONTROL</div><h1>${escape(this._config.title)}</h1><div class="subtitle">${selector}<span class="separator">/</span><span>Tuya 3.5</span></div></div></div>
            <div class="header-actions"><span class="connection" data-connection>Waiting for data</span><button class="refresh" data-action="refresh">${icon("mdi:refresh")} Refresh parameters</button></div>
          </header>
          <div class="metrics">
            <div class="metric"><span class="metric-label">CURRENT TEMPERATURE</span><strong data-metric="current_temperature">\u2014</strong><p>Reported temperature; sensor location unverified.</p></div>
            <div class="metric"><span class="metric-label">TEMPERATURE TARGET</span><strong data-metric="target_temperature">\u2014</strong><p>Active temperature target reported by the pump.</p></div>
            <div class="metric"><span class="metric-label">PARAMETERS READ</span><strong data-metric="parameters_read">\u2014</strong><p>Number of parameter records read from the pump.</p></div>
            <div class="metric"><span class="metric-label">AVAILABLE FIELDS</span><strong data-metric="available">0 <small>/ 770</small></strong><p>Fields with fresh device data.</p><div class="track"><div class="progress"></div></div></div>
          </div>
          <div class="notice" role="status" hidden></div>
          ${device ? `<div class="workspace"><aside><div class="nav-heading">PARAMETER LIBRARY</div><nav aria-label="Parameter categories"><button data-group="-1">${icon("mdi:view-grid-outline")}<span>All parameters</span><b>${this._parameters().length}</b></button>${categories.map(g => `<button data-group="${escape(g.group)}">${icon(g.icon)}<span>${escape(g.title)}</span><b>${g.parameters.length}</b></button>`).join("")}</nav><div class="nav-foot">Changes use fresh device bounds and a separate readback.</div></aside><main><div class="section-heading"><div><div class="eyebrow">DEVICE SETTINGS</div><h2></h2><p class="group-description"></p></div><span class="field-count"></span></div><div class="toolbar"><div class="search-wrap">${icon("mdi:magnify")}<input class="search" type="search" value="${escape(this._query)}" placeholder="Search all 770 parameters..." aria-label="Search all parameters"></div><select class="filter" aria-label="Parameter filter"><option value="all">All fields</option><option value="available">Available only</option><option value="changed">Edited fields</option></select><button class="icon-button" data-action="reload" aria-label="Reload entity mapping" title="Reload entity mapping">${icon("mdi:sync")}</button></div><div class="families" aria-label="Operating-condition tables"></div><div class="help-note">English help follows the device labels. <span>Inferred</span> and <span>Unverified</span> descriptions are not manufacturer-confirmed functions. Unconfirmed scales stay raw.</div><div class="grid"></div></main></div>` : `<div class="empty"><h2>${this._loadError ? "Dashboard is not ready" : this._config.entry_id ? "Configured pump is not loaded" : "Connect your Mango heat pump"}</h2><p>${escape(this._loadError || "Add the Mango Tuya Local integration to load your parameter library.")}</p><button data-action="reload">Reload dashboard data</button><a href="/config/integrations">Open integrations</a></div>`}
        </ha-card>`;
      const filter = this.shadowRoot.querySelector(".filter"); if (filter) filter.value = this._filter;
      this._drawRows(); this._updateNav(); this._update();
    }
    _updateNav() {
      for (const button of this.shadowRoot.querySelectorAll("[data-group]")) {
        const active = !this._query && Number(button.dataset.group) === this._group;
        button.classList.toggle("active", active); button.setAttribute("aria-current", String(active));
      }
    }
    _drawRows() {
      const grid = this.shadowRoot.querySelector(".grid"), device = this._device();
      if (!grid || !device) return;
      const group = device.groups.find(g => g.group === this._group);
      const heading = this._query ? "Search results" : group?.title || "All parameters";
      this.shadowRoot.querySelector("h2").textContent = heading;
      this.shadowRoot.querySelector(".group-description").textContent = this._query ? "Matching fields across every category." : group?.description || "The complete parameter library, organised by device category.";
      const families = this._query ? [] : [...new Set((group?.parameters || []).map(p => p.family).filter(Boolean))];
      this.shadowRoot.querySelector(".families").innerHTML = families.length ? [{ label: "All tables", value: "" }, ...families.map(f => ({ label: f, value: f }))].map(f => `<button data-family="${escape(f.value)}" class="${f.value === this._family ? "selected" : ""}">${escape(f.label)}</button>`).join("") : "";
      const rows = this._visible();
      this.shadowRoot.querySelector(".field-count").textContent = `${rows.length} fields`;
      grid.innerHTML = rows.length ? rows.map(p => this._row(p)).join("") : `<div class="no-results">No matching parameters. Try another name or filter.</div>`;
      this._update();
    }
    _row(p) {
      const state = this._state(p), value = this._drafts.get(p.key) ?? (available(state) ? state.state : "");
      const help = p.confidence === "verified_options" ? "Verified options" : p.confidence === "unverified" ? "Unverified" : "Inferred";
      let control;
      if (p.domain === "select") {
        control = `<select class="value-input" data-key="${escape(p.key)}" aria-label="${escape(p.name)}">${(state?.attributes.options || []).map(o => `<option value="${escape(o)}" ${o === value ? "selected" : ""}>${escape(o)}</option>`).join("")}</select>`;
      } else {
        control = `<input class="value-input" data-key="${escape(p.key)}" type="number" inputmode="decimal" aria-label="${escape(p.name)}" value="${escape(value)}">`;
      }
      return `<article class="parameter" data-key="${escape(p.key)}"><div class="param-top"><span class="param-category">${escape(p.category)}</span><button class="info icon-button" data-info="${escape(p.entity_id)}" aria-label="More information about ${escape(p.name)}">${icon("mdi:information-outline")}</button></div><h3>${escape(p.name)}</h3><div class="current"><span>Current</span><strong class="current-value"></strong><span class="scale">${p.scale_verified ? "Confirmed scale" : p.domain === "select" ? "Selection" : "Raw value"}</span></div><div class="controls">${control}<button class="apply" data-apply="${escape(p.key)}">Apply</button></div><div class="limits"></div><p class="description">${escape(p.description)}</p><div class="param-footer"><span class="confidence ${p.confidence === "verified_options" ? "verified" : ""}">${help}</span>${p.family ? `<span class="family-label">${escape(p.family)}</span>` : ""}</div><div class="result" role="status" hidden></div></article>`;
    }
    _update() {
      const device = this._device(); if (!device || !this._hass) return;
      const selector = this.shadowRoot.querySelector(".device-select"); if (selector) selector.disabled = this._pending.size > 0;
      const all = this._parameters(), count = all.filter(p => available(this._state(p))).length;
      const countElement = this.shadowRoot.querySelector('[data-metric="available"]');
      if (countElement) countElement.innerHTML = `${count} <small>/ ${all.length}</small>`;
      const progress = this.shadowRoot.querySelector(".progress"); if (progress) progress.style.width = `${all.length ? count / all.length * 100 : 0}%`;
      for (const key of ["current_temperature", "target_temperature", "parameters_read"]) {
        const element = this.shadowRoot.querySelector(`[data-metric="${key}"]`), state = this._hass.states[device.sensors[key]];
        if (element) element.textContent = available(state) ? `${state.state} ${state.attributes.unit_of_measurement || ""}`.trim() : "\u2014";
      }
      const connection = this.shadowRoot.querySelector("[data-connection]");
      const communication = this._hass.states[device.sensors.parameters_read]?.attributes.communication_state;
      if (connection) {
        connection.textContent = communication === "retrying" ? "Reconnecting / last confirmed values" : communication === "offline" ? "Device connection unavailable" : count ? "Device data available" : "Waiting for device data";
        connection.classList.toggle("online", count > 0 && communication !== "retrying" && communication !== "offline");
      }
      const refresh = this.shadowRoot.querySelector('[data-action="refresh"]');
      if (refresh) refresh.disabled = !device.refresh_entity || !this._hass.states[device.refresh_entity] || this._hass.states[device.refresh_entity].state === "unavailable";
      const byKey = new Map(all.map(p => [p.key, p]));
      for (const article of this.shadowRoot.querySelectorAll(".parameter")) {
        const p = byKey.get(article.dataset.key), state = this._state(p), ready = available(state), input = article.querySelector(".value-input");
        article.classList.toggle("unavailable", !ready);
        article.querySelector(".current-value").textContent = ready ? state.state : "Unavailable";
        if (!this._drafts.has(p.key) && this.shadowRoot.activeElement !== input) input.value = ready ? state.state : "";
        const fixed = p.domain === "number" && state?.attributes.min === state?.attributes.max;
        input.disabled = !ready || fixed || this._pending.has(p.key) || p.can_control === false;
        if (p.domain === "number" && state) {
          for (const k of ["min", "max", "step"]) input.setAttribute(k, state.attributes[k]);
        }
        const limits = article.querySelector(".limits");
        limits.textContent = !ready ? "Waiting for fresh device data" : p.can_control === false ? "Read-only access in Home Assistant" : p.domain === "select" ? "Only mapped choices are labelled; other codes remain raw." : fixed ? `Fixed device bounds: ${state.attributes.min}` : `Device bounds ${state.attributes.min} to ${state.attributes.max} / step ${state.attributes.step}`;
        const apply = article.querySelector(".apply");
        apply.disabled = !this._valid(p, input.value); apply.textContent = this._pending.has(p.key) ? "Checking..." : "Apply";
        const message = this._messages.get(p.key), result = article.querySelector(".result");
        result.hidden = !message; result.textContent = message?.text || ""; result.className = `result ${message?.kind || ""}`;
      }
    }

    static styles = `
      :host{display:block;--m-bg:#0c1319;--m-card:#121e27;--m-line:#253440;--m-text:#eff6fa;--m-muted:#a1b2c0;--m-accent:#65dcc6;color:var(--m-text);font-family:var(--paper-font-body1_-_font-family,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif)}
      :host(.panel){box-sizing:border-box;padding:24px;background:#080f15;min-height:100vh}
      *{box-sizing:border-box}ha-card{display:block;overflow:clip;border:1px solid var(--m-line);border-radius:22px;background:var(--m-bg);color:var(--m-text);box-shadow:0 12px 40px #0002}
      header{padding:30px 32px;display:flex;align-items:center;justify-content:space-between;gap:24px;background:radial-gradient(ellipse at 88% 0%,#204c4840,transparent 65%),#101b23;border-bottom:1px solid var(--m-line)}
      .identity{display:flex;align-items:center;gap:17px}.brand-mark{display:grid;place-items:center;width:50px;height:54px;flex-shrink:0;border:1px solid #65dcc660;border-radius:15px;color:var(--m-accent);background:#65dcc60c;font-size:30px;font-weight:800;letter-spacing:-3px;padding-right:3px}
      .eyebrow{font-size:10px;font-weight:700;letter-spacing:1.9px;color:var(--m-accent)}h1{font-size:26px;line-height:1.25;font-weight:650;letter-spacing:-.7px;margin:5px 0 7px}.subtitle{display:flex;gap:9px;align-items:center;font-size:12px;color:var(--m-muted)}.separator{opacity:.35}
      .header-actions{display:flex;align-items:center;gap:15px}.connection{font-size:11px;color:var(--m-muted);white-space:normal;flex:1;min-width:0}.connection::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:#9aa6b1;margin-right:7px}.connection.online::before{background:var(--m-accent);box-shadow:0 0 12px #65dcc670}
      button,input,select{font:inherit;color:inherit}button{cursor:pointer;touch-action:manipulation}button:disabled{opacity:.4;cursor:default}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--m-accent);outline-offset:3px}ha-icon{--mdc-icon-size:19px;display:inline-flex;width:19px;height:19px;flex-shrink:0;vertical-align:middle}
      .refresh{display:flex;align-items:center;gap:9px;min-height:42px;border:1px solid #65dcc650;border-radius:10px;background:#65dcc611;padding:10px 14px;color:var(--m-accent);font-size:12px;font-weight:600;white-space:nowrap}.icon-button{border:0;background:none;padding:7px;color:var(--m-muted);border-radius:8px;min-width:34px;min-height:34px;display:grid;place-items:center}.icon-button:hover{background:#ffffff09}
      .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));padding:25px 32px;gap:26px;border-bottom:1px solid var(--m-line)}.metric{position:relative;padding-right:20px;min-width:0}.metric:not(:last-child){border-right:1px solid var(--m-line)}.metric-label{font-size:10px;font-weight:600;letter-spacing:1.4px;color:var(--m-muted)}.metric strong{display:block;font-size:30px;font-weight:600;letter-spacing:-1px;margin-top:10px;line-height:1.25}.metric small{font-size:16px;letter-spacing:0;color:var(--m-muted);font-weight:400}.metric p{font-size:11px;line-height:1.55;color:var(--m-muted);margin:9px 0 0;max-width:320px}.track{height:3px;border-radius:3px;background:var(--m-line);margin-top:13px;max-width:280px}.progress{height:100%;background:var(--m-accent);transition:width .2s;border-radius:3px}
      .workspace{display:grid;grid-template-columns:233px minmax(0,1fr)}aside{position:sticky;top:20px;align-self:start;max-height:calc(100vh - 40px);overflow:auto;background:#0f1820;border-right:1px solid var(--m-line);padding:23px 12px;min-width:0}.nav-heading{font-size:9px;letter-spacing:1.5px;color:#8da2b2;font-weight:700;padding:0 12px 14px}nav{display:flex;flex-direction:column;gap:3px}nav button{display:flex;align-items:center;text-align:left;gap:10px;width:100%;border:1px solid transparent;border-radius:9px;background:transparent;padding:10px;font-size:11px;color:#afc0cb;min-height:42px}nav button:hover{background:#ffffff05}nav button.active{background:#65dcc60f;border-color:#65dcc629;color:var(--m-accent)}nav b{margin-left:auto;font-size:9px;font-weight:500;color:#7f96a8;padding:2px 0;min-width:18px;text-align:right}nav button.active b{color:var(--m-accent)}.nav-foot{font-size:10px;line-height:1.7;color:#8195a5;padding:19px 12px 0;border-top:1px solid #25344080;margin-top:18px}
      main{padding:27px 28px 30px;min-width:0}.section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}h2{font-size:23px;letter-spacing:-.55px;font-weight:600;line-height:1.3;margin:7px 0 8px}.group-description{font-size:12px;line-height:1.6;color:var(--m-muted);max-width:630px;margin:0}.field-count{white-space:nowrap;color:var(--m-accent);font-size:10px;border:1px solid #65dcc629;padding:6px 9px;border-radius:6px;margin-top:23px}
      .toolbar{display:flex;align-items:center;gap:10px;margin-top:24px}.search-wrap{display:flex;gap:10px;align-items:center;border:1px solid var(--m-line);border-radius:10px;background:#121e27;flex:1;padding-left:12px;color:var(--m-muted);min-width:0}.search{border:0;outline:none!important;box-shadow:none;background:transparent;padding:12px 8px;width:100%;min-width:0;font-size:12px}.search::placeholder{color:#7c93a5}.search-wrap:focus-within{border-color:#65dcc680}.filter,.device-select{border:1px solid var(--m-line);background:#14212b;border-radius:9px;padding:11px 12px;font-size:11px;max-width:220px}.device-select{padding:3px 8px;max-width:200px}.families{display:flex;gap:7px;flex-wrap:wrap;margin-top:15px}.families:empty{display:none}.families button{padding:7px 10px;font-size:10px;border:1px solid var(--m-line);background:none;color:var(--m-muted);border-radius:7px;min-height:32px}.families button.selected{background:#65dcc612;color:var(--m-accent);border-color:#65dcc645}
      .help-note{font-size:10px;line-height:1.7;color:#9aaebc;margin:17px 0}.help-note span{color:#c6d5dd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(265px,100%),1fr));align-items:start;gap:13px}.parameter{padding:15px 16px 16px;border:1px solid var(--m-line);border-radius:13px;background:var(--m-card);min-width:0;transition:border-color .15s}.parameter:focus-within{border-color:#65dcc650}.param-top{display:flex;align-items:center;justify-content:space-between;gap:6px;margin:-5px -7px 4px 0}.param-category{font-size:9px;letter-spacing:.4px;color:#9db3c2}.info{--mdc-icon-size:16px;opacity:.7;min-height:28px;min-width:28px}.info ha-icon{--mdc-icon-size:16px}h3{font-size:14px;line-height:1.45;font-weight:600;overflow-wrap:anywhere;margin:0 0 14px;letter-spacing:.1px}.current{display:flex;align-items:baseline;gap:8px;margin-bottom:12px;font-size:10px;color:var(--m-muted);min-height:25px}.current-value{font-size:23px;font-weight:600;letter-spacing:-.45px;color:var(--m-text)}.scale{margin-left:auto;font-size:9px;color:#8aa1b1;text-align:right}.controls{display:flex;gap:8px}.value-input{min-width:0;width:100%;border:1px solid #344651;border-radius:8px;background:#0c151d;padding:10px;font-size:13px;min-height:41px;flex:1;color:var(--m-text);color-scheme:dark}.value-input:disabled{color:#8fa2af}.apply{border:1px solid #65dcc640;background:#65dcc61a;color:var(--m-accent);font-size:11px;font-weight:650;border-radius:8px;padding:10px 13px;min-height:41px;min-width:63px}.apply:not(:disabled):hover{background:#65dcc62a}.limits{font-size:9px;line-height:1.5;color:#8ba4b5;margin-top:8px}.description{font-size:11px;line-height:1.65;color:#b2c4cf;margin:15px 0 13px;min-height:54px;overflow-wrap:anywhere}.param-footer{display:flex;align-items:center;justify-content:space-between;gap:6px}.confidence{font-size:9px;border-radius:4px;background:#ffffff06;padding:4px 6px;border:1px solid #344551;color:#9cb1bf}.confidence.verified{color:var(--m-accent);border-color:#65dcc640}.family-label{font-size:9px;color:#8fa7b7}.unavailable .current-value{font-size:15px;color:#8fa2b1}.result{font-size:10px;line-height:1.6;margin-top:13px;padding:9px 10px;background:#65dcc608;border:1px solid #65dcc620;border-radius:6px;color:var(--m-accent)}.result.error{color:#ffb2a6;border-color:#ffb2a640;background:#ffb2a608}.result.wait{color:#e2c992;border-color:#e2c99230}.notice{padding:12px 32px;font-size:12px;background:#65dcc60c;color:var(--m-accent);border-bottom:1px solid var(--m-line)}[hidden]{display:none!important}.empty{padding:45px 32px}.empty p{color:var(--m-muted);font-size:13px}.empty button{padding:11px;border:1px solid var(--m-line);background:var(--m-card);border-radius:8px;margin-right:14px}.empty a{color:var(--m-accent)}.no-results{padding:28px;color:var(--m-muted);font-size:13px;grid-column:1/-1}
      @media(min-width:1700px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
      @media(max-width:1050px){header{align-items:flex-start;flex-direction:column;gap:18px}.header-actions{width:100%;justify-content:space-between}.workspace{grid-template-columns:205px minmax(0,1fr)}main{padding:24px 20px}.metrics{gap:16px}.metric strong{font-size:26px}nav button{font-size:10px}}
      @media(max-width:720px){:host(.panel){padding:10px}ha-card{border-radius:15px}header{padding:22px 19px}h1{font-size:22px}.brand-mark{width:40px;height:46px;font-size:25px}.identity{gap:12px}.header-actions{gap:8px}.refresh{font-size:11px;padding:9px 10px}.connection{font-size:10px}.metrics{padding:19px;gap:13px;grid-template-columns:1fr 1fr}.metric{padding-right:6px}.metric:nth-child(2n){border-right:0}.metric:nth-child(n+3){border-top:1px solid var(--m-line);padding-top:16px}.metric strong{font-size:25px}.metric p{font-size:10px}.workspace{display:block}aside{position:sticky;top:0;z-index:2;max-height:none;overflow:visible;padding:16px 13px 13px;border-right:0;border-bottom:1px solid var(--m-line)}.nav-heading{padding:0 6px 10px}nav{flex-direction:row;overflow-x:auto;gap:7px;padding-bottom:5px}nav button{width:auto;min-width:max-content;padding:8px 10px;border-color:var(--m-line);min-height:39px;font-size:11px}nav b{margin-left:2px}.nav-foot{display:none}main{padding:23px 18px}.toolbar{flex-wrap:wrap;gap:8px}.search-wrap{flex-basis:100%}.filter{flex:1}.help-note{font-size:10px}.grid{grid-template-columns:repeat(auto-fit,minmax(min(265px,100%),1fr))}.description{min-height:0}.section-heading{gap:10px}h2{font-size:21px}.subtitle{font-size:11px}}
      @media(prefers-reduced-motion:reduce){*{transition:none!important}}
    `;
  }
  class MangoControlPanel extends MangoParameterCard {
    constructor() { super(); this.setConfig({ title: "Mango Control Room", default_group: 14, panel: true }); }
    connectedCallback() { this.classList.add("panel"); super.connectedCallback(); }
  }
  if (!customElements.get("mango-parameter-card")) customElements.define("mango-parameter-card", MangoParameterCard);
  if (!customElements.get("mango-control-panel")) customElements.define("mango-control-panel", MangoControlPanel);
  window.customCards = window.customCards || [];
  if (!window.customCards.some(c => c.type === "mango-parameter-card")) window.customCards.push({
    type: "mango-parameter-card", name: "Mango Control Room", preview: true,
    description: "Parameter controls with categories, English help and device readback.",
    documentationURL: "https://github.com/artepe/mango-tuya-local-home-assistant/blob/main/docs/DASHBOARD.md"
  });
})();
