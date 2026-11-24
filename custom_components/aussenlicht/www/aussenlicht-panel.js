/* Außenlicht-Planer – Frontend-Panel (Web-Component, kein Build-Schritt) */
(() => {
  if (customElements.get("aussenlicht-panel")) return;

  const TABS = [
    ["overview", "Übersicht"],
    ["zones", "Bereiche"],
    ["seasons", "Saisons"],
    ["settings", "Einstellungen"],
  ];
  const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
    "August", "September", "Oktober", "November", "Dezember"];
  const ACTIONS = { on: "An", off: "Aus", dim: "Dimmen" };
  const ANCHORS = { sunset: "Sonnenuntergang", sunrise: "Sonnenaufgang", time: "Uhrzeit" };

  const esc = (v) => String(v === null || v === undefined ? "" : v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const rid = () => Math.random().toString(36).slice(2, 8);
  const pad2 = (n) => String(n).padStart(2, "0");
  const errText = (e) => (e && e.message) ? e.message : (typeof e === "string" ? e : JSON.stringify(e));

  const validDate = (iso) => { const d = new Date(iso); return iso && !isNaN(d.getTime()) ? d : null; };
  const fmtTime = (iso) => { const d = validDate(iso); return d ? d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "–"; };
  const fmtDate = (iso) => { const d = validDate(iso); return d ? d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) : "–"; };

  const actionText = (action, pct) => (action === "dim" ? `Gedimmt ${pct === null || pct === undefined ? "?" : pct} %` : (ACTIONS[action] || action || "–"));
  const stepActionText = (action, pct) => (action === "dim" ? `Dimmen ${pct === null || pct === undefined ? "?" : pct} %` : (ACTIONS[action] || action || "–"));
  const stepLabel = (st) => {
    let a;
    if (st.anchor === "time") a = `Uhrzeit ${st.time || "--:--"}`;
    else {
      const o = Number(st.offset_min) || 0;
      a = `${ANCHORS[st.anchor] || st.anchor} ${o >= 0 ? "+" : "-"}${Math.abs(o)} min`;
    }
    return `${a} – ${stepActionText(st.action, st.brightness_pct)}`;
  };

  const normalize = (cfg) => {
    const c = clone(cfg || {});
    c.zones = c.zones || {};
    c.seasons = c.seasons || {};
    c.settings = Object.assign({ dry_run: true, notify_service: "", notify_level: "errors", wled_delay_s: 10 }, c.settings || {});
    Object.values(c.zones).forEach((z) => {
      z.entities = z.entities || [];
      z.wled_presets = z.wled_presets || [];
      z.steps = z.steps || [];
      if (z.default_preset === null || z.default_preset === undefined) z.default_preset = "";
      if (z.enabled === undefined) z.enabled = true;
    });
    Object.values(c.seasons).forEach((s) => {
      s.steps = s.steps || [];
      if (s.preset === null || s.preset === undefined) s.preset = "";
      if (s.enabled === undefined) s.enabled = true;
    });
    return c;
  };

  const STYLE = `
    :host { display:block; height:100%; overflow:auto; box-sizing:border-box;
      background:var(--primary-background-color); color:var(--primary-text-color);
      font-family:var(--paper-font-body1_-_font-family, var(--ha-font-family-body, inherit)); }
    * { box-sizing:border-box; }
    header { position:sticky; top:0; z-index:5; background:var(--app-header-background-color, var(--card-background-color));
      color:var(--app-header-text-color, var(--primary-text-color)); border-bottom:1px solid var(--divider-color); }
    .bar { display:flex; align-items:center; gap:8px; padding:8px 16px; flex-wrap:wrap; }
    h1 { font-size:20px; font-weight:500; margin:0; }
    .spacer { flex:1 1 auto; }
    #menu { display:none; }
    :host([narrow]) #menu { display:inline-flex; }
    .savebox { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .savebox.hidden { display:none; }
    #dirtyhint { color:var(--warning-color, #f59e0b); font-size:13px; font-weight:500; }
    nav { display:flex; overflow-x:auto; padding:0 8px; }
    nav button { background:none; border:none; border-bottom:3px solid transparent; border-radius:0;
      padding:10px 14px; font-size:14px; color:var(--secondary-text-color); white-space:nowrap; cursor:pointer; font-family:inherit; }
    nav button.active { color:var(--primary-color); border-bottom-color:var(--primary-color); font-weight:500; }
    #msg { display:none; padding:10px 16px; font-size:14px; font-weight:500; white-space:pre-wrap; }
    #msg.error { display:block; background:var(--error-color, #db4437); color:#fff; }
    #msg.ok { display:block; background:var(--success-color, #43a047); color:#fff; }
    main { padding:16px; max-width:1300px; margin:0 auto; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 380px), 1fr)); gap:16px; align-items:start; }
    .stack { display:flex; flex-direction:column; gap:16px; }
    .card { background:var(--card-background-color); border:1px solid var(--divider-color);
      border-radius:var(--ha-card-border-radius, 12px); box-shadow:var(--ha-card-box-shadow, none); padding:16px; min-width:0; }
    .card + .card { }
    .card-h { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:8px; }
    h2 { font-size:17px; font-weight:500; margin:0; flex:1 1 auto; }
    h3 { font-size:15px; font-weight:500; margin:0 0 8px; }
    .muted { color:var(--secondary-text-color); }
    .small { font-size:12px; color:var(--secondary-text-color); }
    .banner { background:var(--warning-color, #f59e0b); color:#000; border-radius:8px; padding:12px 16px; margin-bottom:16px; font-weight:500; }
    .suninfo { margin-bottom:16px; display:flex; gap:16px; flex-wrap:wrap; }
    .pill { display:inline-block; padding:2px 10px; border-radius:12px; font-size:13px; font-weight:500; color:#fff; background:var(--secondary-text-color); }
    .pill.on { background:var(--success-color, #43a047); }
    .pill.dim { background:var(--primary-color); }
    .badge { display:inline-block; padding:1px 8px; border-radius:10px; font-size:11px; border:1px solid var(--divider-color); color:var(--secondary-text-color); }
    .badge.test { border-color:var(--warning-color, #f59e0b); color:var(--warning-color, #f59e0b); }
    .badge.err { border-color:var(--error-color, #db4437); color:var(--error-color, #db4437); }
    .row { margin:6px 0; }
    ul.tl, ul.log { list-style:none; margin:6px 0 0; padding:0; }
    ul.tl li { display:flex; gap:10px; padding:4px 0; border-top:1px solid var(--divider-color); }
    ul.tl li.past { opacity:.55; }
    ul.tl .t { font-variant-numeric:tabular-nums; min-width:46px; font-weight:500; }
    ul.log li { display:flex; gap:10px; flex-wrap:wrap; padding:5px 0; border-top:1px solid var(--divider-color); font-size:13px; }
    ul.log li.err { color:var(--error-color, #db4437); }
    ul.log .t { color:var(--secondary-text-color); min-width:100px; font-variant-numeric:tabular-nums; }
    ul.log li.err .t { color:inherit; }
    ul.log .z { font-weight:500; min-width:70px; }
    ul.log .x { flex:1 1 140px; }
    .actions { margin-top:12px; display:flex; gap:8px; flex-wrap:wrap; }
    button { font-family:inherit; font-size:14px; border-radius:8px; padding:7px 14px; cursor:pointer;
      border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); }
    button:hover:not(:disabled) { border-color:var(--primary-color); }
    button.primary { background:var(--primary-color); border-color:var(--primary-color); color:var(--text-primary-color, #fff); }
    button.danger { color:var(--error-color, #db4437); border-color:var(--error-color, #db4437); }
    button.icon { padding:6px 10px; line-height:1; }
    button:disabled { opacity:.45; cursor:default; }
    #menu { padding:6px 10px; font-size:18px; }
    label { font-size:13px; color:var(--secondary-text-color); }
    .field { margin:14px 0; }
    .field > label.lbl { display:block; margin-bottom:4px; font-weight:500; }
    input[type=text], input[type=number], input[type=time], select, input:not([type]) {
      font-family:inherit; font-size:14px; padding:7px 9px; border-radius:6px; min-width:0;
      border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); }
    input.title { font-size:16px; font-weight:500; flex:1 1 180px; }
    input.wide { width:100%; }
    input.num { width:90px; }
    input.num-sm { width:70px; }
    label.chk { display:inline-flex; align-items:center; gap:6px; color:var(--primary-text-color); font-size:14px; cursor:pointer; }
    .chips { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:6px; }
    .chip { display:inline-flex; align-items:center; gap:4px; background:var(--secondary-background-color, rgba(127,127,127,.15));
      border-radius:16px; padding:3px 4px 3px 10px; font-size:13px; max-width:100%; }
    .chip.missing { outline:1px dashed var(--warning-color, #f59e0b); }
    .chip button { border:none; background:none; padding:0 6px; font-size:15px; line-height:1; color:var(--secondary-text-color); }
    .addrow { display:flex; gap:6px; flex-wrap:wrap; }
    .addrow input { flex:1 1 220px; }
    .step { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end; padding:10px 0; border-top:1px solid var(--divider-color); }
    .mini { display:flex; flex-direction:column; gap:3px; }
    .formgrid { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap:12px 16px; margin:12px 0; }
    .datefield { display:flex; gap:6px; }
    .checks { display:flex; flex-direction:column; gap:6px; margin:6px 0; }
    .footer { display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; margin-top:12px; }
    .err-text { color:var(--error-color, #db4437); }
  `;

  class AussenlichtPanel extends HTMLElement {
    constructor() {
      super();
      this._hass = null;
      this._started = false;
      this._tab = "overview";
      this._config = null;
      this._work = null;
      this._cfgError = null;
      this._status = null;
      this._statusErr = null;
      this._statusBusy = false;
      this._saving = false;
      this._timer = null;
      this._msgTimer = null;

      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `
        <style>${STYLE}</style>
        <header>
          <div class="bar">
            <button id="menu" title="Menü">&#9776;</button>
            <h1>Außenlicht</h1>
            <div class="spacer"></div>
            <div class="savebox hidden" id="savebox">
              <span id="dirtyhint" hidden>Ungespeicherte Änderungen</span>
              <button id="discard" disabled>Verwerfen</button>
              <button id="save" class="primary" disabled>Speichern</button>
            </div>
          </div>
          <nav id="tabs">${TABS.map(([id, label]) => `<button data-tab="${id}">${label}</button>`).join("")}</nav>
          <div id="msg"></div>
        </header>
        <main id="content"></main>`;
      this._content = root.getElementById("content");
      this._msgEl = root.getElementById("msg");

      root.getElementById("tabs").addEventListener("click", (e) => {
        const b = e.target.closest("button[data-tab]");
        if (b) this._setTab(b.dataset.tab);
      });
      root.getElementById("menu").addEventListener("click", () => {
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
      });
      root.getElementById("save").addEventListener("click", () => this._save());
      root.getElementById("discard").addEventListener("click", () => this._discard());

      this._content.addEventListener("input", (e) => this._onField(e));
      this._content.addEventListener("change", (e) => this._onField(e));
      this._content.addEventListener("click", (e) => this._onClick(e));
      this._content.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.target.dataset && e.target.dataset.f === "new-entity") {
          e.preventDefault();
          this._addFromInput(e.target, true);
        }
      });
      this._updateTabs();
    }

    connectedCallback() {
      if (!this._timer) this._timer = setInterval(() => this._tick(), 30000);
    }
    disconnectedCallback() {
      if (this._timer) { clearInterval(this._timer); this._timer = null; }
    }

    set hass(h) {
      this._hass = h;
      if (!this._started) {
        this._started = true;
        this._init();
      }
    }
    get hass() { return this._hass; }
    set narrow(v) { this.toggleAttribute("narrow", !!v); }
    set panel(_v) { /* nicht benötigt */ }

    /* ---------- Laden / Speichern ---------- */
    async _init() {
      this._renderContent();
      this._loadStatus();
      await this._loadConfig();
    }

    async _loadConfig() {
      try {
        const res = await this._hass.callWS({ type: "aussenlicht/config" });
        this._config = normalize(res.config);
        this._work = clone(this._config);
        this._cfgError = null;
      } catch (e) {
        this._cfgError = errText(e);
      }
      if (this._tab !== "overview") this._renderContent();
      this._updateBar();
    }

    async _loadStatus() {
      if (this._statusBusy || !this._hass) return;
      this._statusBusy = true;
      try {
        this._status = await this._hass.callWS({ type: "aussenlicht/status" });
        this._statusErr = null;
      } catch (e) {
        this._statusErr = errText(e);
      }
      this._statusBusy = false;
      if (this._tab === "overview") this._renderContent();
    }

    _tick() {
      if (this._started && this._tab === "overview" && !document.hidden) this._loadStatus();
    }

    _sanitized() {
      const c = clone(this._work);
      Object.values(c.zones).forEach((z) => z.steps.forEach((s) => {
        if (s.action !== "dim") s.brightness_pct = null;
        if (s.anchor !== "time") s.time = null;
        else if (!s.time) s.time = null;
      }));
      return c;
    }

    async _save() {
      if (this._saving || !this._isDirty()) return;
      this._saving = true;
      this._showMsg(null);
      this._updateBar();
      try {
        const res = await this._hass.callWS({ type: "aussenlicht/config/save", config: this._sanitized() });
        this._config = normalize(res.config);
        this._work = clone(this._config);
        this._showMsg("Gespeichert.", "ok");
        this._renderContent();
        this._loadStatus();
      } catch (e) {
        this._showMsg("Speichern fehlgeschlagen: " + errText(e), "error");
      }
      this._saving = false;
      this._updateBar();
    }

    _discard() {
      if (!this._config) return;
      this._work = clone(this._config);
      this._showMsg(null);
      this._renderContent();
      this._updateBar();
    }

    _isDirty() {
      return !!(this._work && this._config && JSON.stringify(this._work) !== JSON.stringify(this._config));
    }

    /* ---------- UI-Hilfen ---------- */
    _showMsg(text, kind) {
      clearTimeout(this._msgTimer);
      this._msgEl.className = text ? kind : "";
      this._msgEl.textContent = text || "";
      if (text && kind === "ok") this._msgTimer = setTimeout(() => this._showMsg(null), 4000);
    }

    _updateTabs() {
      this.shadowRoot.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === this._tab));
      this.shadowRoot.getElementById("savebox").classList.toggle("hidden", this._tab === "overview");
    }

    _updateBar() {
      const dirty = this._isDirty();
      const r = this.shadowRoot;
      r.getElementById("dirtyhint").hidden = !dirty;
      r.getElementById("save").disabled = !dirty || this._saving;
      r.getElementById("discard").disabled = !dirty || this._saving;
      r.getElementById("save").textContent = this._saving ? "Speichere …" : "Speichern";
    }

    _setTab(t) {
      this._tab = t;
      this._updateTabs();
      this._renderContent();
      this.scrollTop = 0;
      if (t === "overview") this._loadStatus();
    }

    _renderContent() {
      const top = this.scrollTop;
      let html;
      if (this._tab === "overview") html = this._viewOverview();
      else if (this._cfgError) {
        html = `<div class="card"><h3 class="err-text">Konfiguration konnte nicht geladen werden</h3>
          <div class="row">${esc(this._cfgError)}</div>
          <div class="actions"><button data-act="retry">Erneut versuchen</button></div></div>`;
      } else if (!this._work) html = `<div class="muted">Lade Konfiguration …</div>`;
      else if (this._tab === "zones") html = this._viewZones();
      else if (this._tab === "seasons") html = this._viewSeasons();
      else html = this._viewSettings();
      this._content.innerHTML = html;
      this.scrollTop = top;
    }

    /* ---------- Hass-Daten ---------- */
    _states() { return (this._hass && this._hass.states) || {}; }
    _friendly(eid) {
      const s = this._states()[eid];
      return (s && s.attributes && s.attributes.friendly_name) || "";
    }
    _entityCandidates() {
      return Object.keys(this._states()).filter((k) => k.startsWith("switch.") || k.startsWith("light."))
        .sort((a, b) => (this._friendly(a) || a).localeCompare(this._friendly(b) || b, "de"));
    }
    _wledCandidates() {
      const st = this._states();
      return Object.keys(st).filter((k) => k.startsWith("select.") &&
        (k.includes("wled") || (st[k].attributes && Array.isArray(st[k].attributes.options))))
        .sort((a, b) => (this._friendly(a) || a).localeCompare(this._friendly(b) || b, "de"));
    }
    _options(eid) {
      const s = this._states()[eid];
      return (s && s.attributes && Array.isArray(s.attributes.options)) ? s.attributes.options : [];
    }
    _services() {
      const svc = (this._hass && this._hass.services) || {};
      const out = [];
      ["notify", "rest_command"].forEach((d) => {
        Object.keys(svc[d] || {}).sort().forEach((s) => out.push(`${d}.${s}`));
      });
      return out;
    }

    /* ---------- Views ---------- */
    _viewOverview() {
      const s = this._status;
      let h = "";
      if (this._statusErr) h += `<div class="banner" style="background:var(--error-color,#db4437);color:#fff">Status konnte nicht geladen werden: ${esc(this._statusErr)}</div>`;
      if (!s) return h + (this._statusErr ? "" : `<div class="muted">Lade Status …</div>`);
      if (s.dry_run) h += `<div class="banner">Testmodus – es wird nichts geschaltet, nur protokolliert</div>`;
      const sun = s.sun || {};
      h += `<div class="suninfo"><span>Sonnenaufgang: <b>${fmtTime(sun.sunrise)}</b></span><span>Sonnenuntergang: <b>${fmtTime(sun.sunset)}</b></span></div>`;
      const now = validDate(s.now) || new Date();
      const zones = Object.entries(s.zones || {});
      h += `<div class="grid">`;
      if (!zones.length) h += `<div class="card muted">Keine Bereiche konfiguriert. Lege im Tab „Bereiche“ einen Bereich an.</div>`;
      zones.forEach(([zid, z]) => {
        h += `<section class="card"><div class="card-h"><h2>${esc(z.name)}</h2>${z.enabled === false ? `<span class="badge">Deaktiviert</span>` : ""}</div>`;
        const d = z.desired;
        if (d) {
          h += `<div class="row"><span class="pill ${esc(d.action)}">${esc(actionText(d.action, d.brightness_pct))}</span>`;
          if (d.preset) h += ` &nbsp;Preset: <b>${esc(String(d.preset).trim())}</b>`;
          h += ` <span class="muted">&nbsp;seit ${fmtTime(d.since)}</span></div>`;
        } else h += `<div class="row muted">Kein Sollzustand</div>`;
        if (z.season) {
          const se = z.season;
          h += `<div class="row">Saison: <b>${esc(se.name)}</b> <span class="muted">(${fmtDate(se.start)} – ${fmtDate(se.end)}${se.preset ? `, Preset ${esc(String(se.preset).trim())}` : ""})</span></div>`;
        } else h += `<div class="row muted">Keine aktive Saison</div>`;
        const tl = z.timeline || [];
        h += `<h3 style="margin-top:12px">Heute</h3>`;
        if (tl.length) {
          h += `<ul class="tl">` + tl.map((t) => {
            const past = validDate(t.time) && validDate(t.time) < now;
            return `<li class="${past ? "past" : ""}"><span class="t">${fmtTime(t.time)}</span><span>${esc(stepActionText(t.action, t.brightness_pct))}</span><span class="muted">${esc(t.label)}</span></li>`;
          }).join("") + `</ul>`;
        } else h += `<div class="muted small">Keine Schritte heute.</div>`;
        h += `<div class="actions"><button class="primary" data-act="apply" data-z="${esc(zid)}">Jetzt anwenden</button></div></section>`;
      });
      h += `</div>`;
      const log = (s.log || []).slice(0, 30);
      h += `<section class="card" style="margin-top:16px"><h2 style="margin-bottom:6px">Protokoll</h2>`;
      if (!log.length) h += `<div class="muted">Noch keine Einträge.</div>`;
      else h += `<ul class="log">` + log.map((l) => `<li class="${l.ok === false ? "err" : ""}">
        <span class="t">${fmtTime(l.time)} ${fmtDate(l.time)}</span><span class="z">${esc(l.zone)}</span><span class="x">${esc(l.text)}</span>
        ${l.dry_run ? `<span class="badge test">Test</span>` : ""}${l.ok === false ? `<span class="badge err">Fehler</span>` : ""}</li>`).join("") + `</ul>`;
      h += `</section>`;
      return h;
    }

    _a(kind, id, f, sid) {
      return `data-k="${kind}" data-id="${esc(id)}" data-f="${f}"${sid ? ` data-sid="${esc(sid)}"` : ""}`;
    }

    _opt(value, label, selected) {
      return `<option value="${esc(value)}"${selected ? " selected" : ""}>${esc(label)}</option>`;
    }

    _presetSelect(attrs, options, current) {
      let o = this._opt("", "(kein Preset)", current === "");
      options.forEach((p) => { o += this._opt(p, p, p === current); });
      if (current && !options.includes(current)) o += this._opt(current, `${current} (nicht in Liste)`, true);
      return `<select ${attrs}>${o}</select>`;
    }

    _chips(zid, list, items) {
      return `<div class="chips">` + items.map((eid, i) => {
        const fn = this._friendly(eid);
        const known = !!this._states()[eid];
        return `<span class="chip${known ? "" : " missing"}" title="${esc(eid)}${known ? "" : " (nicht gefunden)"}">${esc(fn || eid)}${fn ? ` <span class="small">${esc(eid)}</span>` : ""}
          <button data-act="rm-list" data-z="${esc(zid)}" data-list="${list}" data-i="${i}" title="Entfernen">&times;</button></span>`;
      }).join("") + `</div>`;
    }

    _viewZones() {
      const w = this._work;
      const used = new Set();
      let h = `<datalist id="dl-ent">${this._entityCandidates().map((e) => `<option value="${esc(e)}" label="${esc(this._friendly(e))}"></option>`).join("")}</datalist>
        <datalist id="dl-wled">${this._wledCandidates().map((e) => `<option value="${esc(e)}" label="${esc(this._friendly(e))}"></option>`).join("")}</datalist>`;
      h += `<div class="stack">`;
      const zones = Object.entries(w.zones);
      if (!zones.length) h += `<div class="card muted">Noch keine Bereiche vorhanden.</div>`;
      zones.forEach(([zid, z]) => {
        used.add(zid);
        const defOptions = z.wled_presets.length ? this._options(z.wled_presets[0]) : [];
        h += `<section class="card">
          <div class="card-h">
            <input type="text" class="title" ${this._a("zone", zid, "name")} value="${esc(z.name)}" placeholder="Name des Bereichs">
            <label class="chk"><input type="checkbox" ${this._a("zone", zid, "enabled")}${z.enabled ? " checked" : ""}> Aktiv</label>
          </div>
          <div class="field"><label class="lbl">Geräte (Schalter / Lichter)</label>
            ${this._chips(zid, "entities", z.entities)}
            <div class="addrow"><input type="text" list="dl-ent" data-f="new-entity" data-id="${esc(zid)}" data-list="entities" placeholder="switch.… oder light.… eingeben / wählen" autocomplete="off">
              <button data-act="add-list" data-z="${esc(zid)}" data-list="entities">Hinzufügen</button></div>
          </div>
          <div class="field"><label class="lbl">WLED-Presets (select-Entitäten)</label>
            ${this._chips(zid, "wled_presets", z.wled_presets)}
            <div class="addrow"><input type="text" list="dl-wled" data-f="new-entity" data-id="${esc(zid)}" data-list="wled_presets" placeholder="select.… eingeben / wählen" autocomplete="off">
              <button data-act="add-list" data-z="${esc(zid)}" data-list="wled_presets">Hinzufügen</button></div>
          </div>
          <div class="field"><label class="lbl">Standard-Preset</label>
            ${this._presetSelect(this._a("zone", zid, "default_preset"), defOptions, z.default_preset)}
            ${z.wled_presets.length ? "" : `<div class="small">Zuerst eine WLED-Entität hinzufügen, um Presets auszuwählen.</div>`}
          </div>
          <div class="field"><label class="lbl">Schritte</label>
            ${z.steps.length ? "" : `<div class="muted small">Noch keine Schritte.</div>`}
            ${z.steps.map((st) => this._stepRow(zid, st)).join("")}
            <div class="actions"><button data-act="add-step" data-z="${esc(zid)}">+ Schritt</button></div>
          </div>
          <div class="footer"><span></span><button class="danger" data-act="rm-zone" data-z="${esc(zid)}">Bereich löschen</button></div>
        </section>`;
      });
      h += `</div><div class="actions"><button class="primary" data-act="add-zone">+ Bereich</button></div>`;
      return h;
    }

    _stepRow(zid, st) {
      const A = (f) => this._a("step", zid, f, st.id);
      let h = `<div class="step">
        <label class="mini">Anker<select ${A("anchor")}>${Object.entries(ANCHORS).map(([k, v]) => this._opt(k, v, st.anchor === k)).join("")}</select></label>`;
      if (st.anchor === "time") {
        h += `<label class="mini">Uhrzeit<input type="time" ${A("time")} value="${esc(st.time || "")}"></label>`;
      } else {
        h += `<label class="mini">Versatz (min)<input type="number" class="num" min="-720" max="720" step="1" ${A("offset_min")} value="${esc(st.offset_min === null || st.offset_min === undefined ? 0 : st.offset_min)}"><span class="small">negativ = vorher</span></label>`;
      }
      h += `<label class="mini">Aktion<select ${A("action")}>${Object.entries(ACTIONS).map(([k, v]) => this._opt(k, v, st.action === k)).join("")}</select></label>`;
      if (st.action === "dim") {
        h += `<label class="mini">Helligkeit (%)<input type="number" class="num" min="1" max="100" step="1" ${A("brightness_pct")} value="${esc(st.brightness_pct === null || st.brightness_pct === undefined ? "" : st.brightness_pct)}"></label>`;
      }
      h += `<button class="icon danger" data-act="rm-step" data-z="${esc(zid)}" data-s="${esc(st.id)}" title="Schritt löschen">&#10005;</button></div>`;
      return h;
    }

    _viewSeasons() {
      const w = this._work;
      const seasons = Object.entries(w.seasons);
      const zones = Object.entries(w.zones);
      let h = `<div class="stack">`;
      if (!seasons.length) h += `<div class="card muted">Noch keine Saisons vorhanden.</div>`;
      seasons.forEach(([sid, s]) => {
        const zone = w.zones[s.zone_id];
        const opts = [];
        if (zone) zone.wled_presets.forEach((e) => this._options(e).forEach((p) => { if (!opts.includes(p)) opts.push(p); }));
        const dateField = (prefix, val) => {
          const [m, d] = String(val || "").split("-");
          return `<div class="datefield">
            <input type="number" class="num-sm" min="1" max="31" step="1" ${this._a("season", sid, prefix + "_d")} value="${esc(d ? Number(d) : "")}" placeholder="Tag" title="Tag">
            <select ${this._a("season", sid, prefix + "_m")} title="Monat">${MONTHS.map((n, i) => this._opt(i + 1, n, Number(m) === i + 1)).join("")}</select></div>`;
        };
        const zoneOpts = (zone ? "" : this._opt("", "– Bereich wählen –", true)) +
          zones.map(([zid, z]) => this._opt(zid, z.name, zid === s.zone_id)).join("");
        const startSteps = zone ? zone.steps.filter((st) => st.action === "on" || st.action === "dim") : [];
        h += `<section class="card">
          <div class="card-h">
            <input type="text" class="title" ${this._a("season", sid, "name")} value="${esc(s.name)}" placeholder="Name der Saison">
            <label class="chk"><input type="checkbox" ${this._a("season", sid, "enabled")}${s.enabled ? " checked" : ""}> Aktiv</label>
          </div>
          <div class="formgrid">
            <label class="mini">Bereich<select ${this._a("season", sid, "zone_id")}>${zoneOpts}</select></label>
            <div class="mini"><label>Von (Tag / Monat)</label>${dateField("start", s.start)}</div>
            <div class="mini"><label>Bis (Tag / Monat)</label>${dateField("end", s.end)}</div>
            <label class="mini">Preset${this._presetSelect(this._a("season", sid, "preset"), opts, s.preset)}</label>
            <label class="mini">Dauer (Minuten)<input type="number" class="num" min="1" step="1" ${this._a("season", sid, "duration_min")} value="${esc(s.duration_min === null || s.duration_min === undefined ? "" : s.duration_min)}"></label>
          </div>
          <div class="field"><label class="lbl">Startet bei</label>
            ${startSteps.length ? `<div class="checks">${startSteps.map((st) => `<label class="chk"><input type="checkbox" data-k="season" data-id="${esc(sid)}" data-f="steps" data-sid="${esc(st.id)}"${s.steps.includes(st.id) ? " checked" : ""}> ${esc(stepLabel(st))}</label>`).join("")}</div>`
              : `<div class="muted small">${zone ? "Der Bereich hat keine Schritte mit Aktion An oder Dimmen." : "Bitte zuerst einen Bereich wählen."}</div>`}
            <div class="small">Wenn der Bereich bei einem dieser Schritte angeht, läuft das Preset für die Dauer, danach das Standard-Preset.</div>
          </div>
          <div class="footer"><span></span><button class="danger" data-act="rm-season" data-s="${esc(sid)}">Saison löschen</button></div>
        </section>`;
      });
      h += `</div><div class="actions"><button class="primary" data-act="add-season"${zones.length ? "" : " disabled"}>+ Saison</button>${zones.length ? "" : `<span class="muted small">Lege zuerst einen Bereich an.</span>`}</div>`;
      return h;
    }

    _viewSettings() {
      const st = this._work.settings;
      const A = (f) => this._a("setting", "settings", f);
      return `<datalist id="dl-svc">${this._services().map((s) => `<option value="${esc(s)}"></option>`).join("")}</datalist>
        <section class="card" style="max-width:640px">
          <h2 style="margin-bottom:10px">Einstellungen</h2>
          <div class="field"><label class="chk"><input type="checkbox" ${A("dry_run")}${st.dry_run ? " checked" : ""}> Testmodus (es wird nichts geschaltet, nur protokolliert)</label></div>
          <div class="field"><label class="lbl" for="ns">Benachrichtigungsdienst</label>
            <input type="text" id="ns" class="wide" list="dl-svc" ${A("notify_service")} value="${esc(st.notify_service)}" placeholder="z. B. notify.mobile_app_… oder rest_command.…" autocomplete="off">
            <div class="small">Leer lassen, um keine Benachrichtigungen zu senden.</div></div>
          <div class="field"><label class="lbl" for="nl">Benachrichtigungen</label>
            <select id="nl" ${A("notify_level")}>${this._opt("off", "Aus", st.notify_level === "off")}${this._opt("errors", "Nur Fehler", st.notify_level === "errors")}${this._opt("all", "Alles", st.notify_level === "all")}</select></div>
          <div class="field"><label class="lbl" for="wd">WLED-Verzögerung nach Einschalten (Sekunden)</label>
            <input type="number" id="wd" class="num" min="0" max="120" step="1" ${A("wled_delay_s")} value="${esc(st.wled_delay_s)}"></div>
        </section>`;
    }

    /* ---------- Ereignisse ---------- */
    _findStep(zid, sid) {
      const z = this._work.zones[zid];
      return z ? z.steps.find((s) => s.id === sid) : null;
    }

    _num(v, emptyValue) {
      if (v === "" || v === null || v === undefined) return emptyValue;
      const n = Number(v);
      return isNaN(n) ? emptyValue : n;
    }

    _onField(e) {
      const t = e.target;
      const f = t.dataset && t.dataset.f;
      if (!f || !this._work) return;
      const toggle = t.type === "checkbox" || t.tagName === "SELECT";
      if (toggle && e.type === "input") return;

      if (f === "new-entity") {
        if (e.type === "input") {
          if (e.inputType && e.inputType !== "insertReplacementText") return;
          this._addFromInput(t, false);
        } else this._addFromInput(t, true);
        return;
      }

      const k = t.dataset.k;
      const id = t.dataset.id;
      const val = t.type === "checkbox" ? t.checked : t.value;
      let structural = false;

      if (k === "zone") {
        const z = this._work.zones[id];
        if (!z) return;
        z[f] = val;
      } else if (k === "step") {
        const st = this._findStep(id, t.dataset.sid);
        if (!st) return;
        if (f === "anchor") {
          st.anchor = val;
          if (val === "time") { if (!st.time) st.time = "22:00"; }
          else { st.time = null; if (st.offset_min === null || st.offset_min === undefined) st.offset_min = 0; }
          structural = true;
        } else if (f === "action") {
          st.action = val;
          st.brightness_pct = val === "dim" ? (st.brightness_pct || 50) : null;
          structural = true;
        } else if (f === "offset_min") st.offset_min = this._num(val, 0);
        else if (f === "brightness_pct") st.brightness_pct = this._num(val, null);
        else if (f === "time") st.time = val || null;
        // Saison-Beschriftungen hängen an den Schritten -> bei Änderungen des Schritts nur beim Tabwechsel neu aufgebaut
      } else if (k === "season") {
        const s = this._work.seasons[id];
        if (!s) return;
        if (f === "steps") {
          const sid = t.dataset.sid;
          s.steps = s.steps.filter((x) => x !== sid);
          if (t.checked) s.steps.push(sid);
        } else if (f === "zone_id") {
          s.zone_id = val;
          s.steps = [];
          s.preset = "";
          structural = true;
        } else if (f === "duration_min") s.duration_min = this._num(val, null);
        else if (/^(start|end)_[dm]$/.test(f)) {
          const [which, part] = f.split("_");
          const cur = String(s[which] || "01-01").split("-");
          let m = cur[0] || "01", d = cur[1] || "01";
          if (part === "m") m = pad2(Number(val) || 1);
          else {
            const n = Math.round(Number(val));
            if (!n || n < 1) return; // leeres/ungültiges Feld ignorieren
            d = pad2(Math.min(31, n));
          }
          s[which] = `${m}-${d}`;
        } else s[f] = val;
      } else if (k === "setting") {
        const st = this._work.settings;
        if (f === "wled_delay_s") st[f] = this._num(val, 0);
        else st[f] = val;
      }

      if (structural) this._renderContent();
      this._updateBar();
    }

    _resolveEntity(raw, candidates, re) {
      const v = String(raw || "").trim();
      if (!v) return null;
      if (candidates.includes(v)) return v;
      const lower = v.toLowerCase();
      const byName = candidates.find((c) => this._friendly(c).toLowerCase() === lower);
      if (byName) return byName;
      return re.test(v) ? v : null;
    }

    _addFromInput(input, report) {
      const zid = input.dataset.id;
      const list = input.dataset.list;
      const z = this._work && this._work.zones[zid];
      if (!z || !input.value.trim()) return;
      const isWled = list === "wled_presets";
      const eid = this._resolveEntity(input.value, isWled ? this._wledCandidates() : this._entityCandidates(),
        isWled ? /^select\.[a-z0-9_]+$/ : /^(switch|light)\.[a-z0-9_]+$/);
      if (!eid) {
        if (report) this._showMsg(isWled ? "Ungültige Entität – erwartet wird eine select.*-Entität." : "Ungültige Entität – erwartet wird switch.* oder light.*.", "error");
        return;
      }
      this._showMsg(null);
      if (!z[list].includes(eid)) z[list].push(eid);
      this._renderContent();
      this._updateBar();
      const again = this._content.querySelector(`input[data-f="new-entity"][data-id="${zid}"][data-list="${list}"]`);
      if (again) again.focus();
    }

    async _onClick(e) {
      const b = e.target.closest("[data-act]");
      if (!b) return;
      const act = b.dataset.act;
      const w = this._work;

      if (act === "retry") { await this._loadConfig(); return; }
      if (act === "apply") { await this._apply(b.dataset.z, b); return; }
      if (!w) return;

      if (act === "add-zone") {
        let id = rid();
        while (w.zones[id]) id = rid();
        w.zones[id] = { name: "Neuer Bereich", enabled: true, entities: [], wled_presets: [], default_preset: "", steps: [] };
      } else if (act === "rm-zone") {
        const z = w.zones[b.dataset.z];
        if (!z) return;
        const hang = Object.entries(w.seasons).filter(([, s]) => s.zone_id === b.dataset.z);
        let msg = `Bereich „${z.name}“ wirklich löschen?`;
        if (hang.length) msg += `\n\nAchtung: ${hang.length === 1 ? "Folgende Saison hängt" : "Folgende Saisons hängen"} an diesem Bereich und ${hang.length === 1 ? "wird" : "werden"} ebenfalls gelöscht:\n- ${hang.map(([, s]) => s.name).join("\n- ")}`;
        if (!confirm(msg)) return;
        hang.forEach(([sid]) => delete w.seasons[sid]);
        delete w.zones[b.dataset.z];
      } else if (act === "add-step") {
        const z = w.zones[b.dataset.z];
        if (!z) return;
        let id = rid();
        while (z.steps.some((s) => s.id === id)) id = rid();
        z.steps.push({ id, anchor: "sunset", offset_min: 0, time: null, action: "on", brightness_pct: null });
      } else if (act === "rm-step") {
        const z = w.zones[b.dataset.z];
        if (!z) return;
        z.steps = z.steps.filter((s) => s.id !== b.dataset.s);
        Object.values(w.seasons).forEach((s) => {
          if (s.zone_id === b.dataset.z) s.steps = s.steps.filter((x) => x !== b.dataset.s);
        });
      } else if (act === "add-list") {
        const input = b.parentElement.querySelector('input[data-f="new-entity"]');
        if (input) this._addFromInput(input, true);
        return;
      } else if (act === "rm-list") {
        const z = w.zones[b.dataset.z];
        if (!z) return;
        z[b.dataset.list].splice(Number(b.dataset.i), 1);
      } else if (act === "add-season") {
        const zid = Object.keys(w.zones)[0];
        if (!zid) return;
        let id = rid();
        while (w.seasons[id]) id = rid();
        w.seasons[id] = { name: "Neue Saison", enabled: true, zone_id: zid, start: "12-01", end: "01-06", preset: "", duration_min: 120, steps: [] };
      } else if (act === "rm-season") {
        const s = w.seasons[b.dataset.s];
        if (!s) return;
        if (!confirm(`Saison „${s.name}“ wirklich löschen?`)) return;
        delete w.seasons[b.dataset.s];
      } else return;

      this._renderContent();
      this._updateBar();
    }

    async _apply(zid, btn) {
      btn.disabled = true;
      try {
        await this._hass.callWS({ type: "aussenlicht/apply_now", zone_id: zid });
        this._showMsg("Sollzustand wurde angewendet.", "ok");
        await this._loadStatus();
      } catch (e) {
        this._showMsg("Anwenden fehlgeschlagen: " + errText(e), "error");
      }
      btn.disabled = false;
    }
  }

  customElements.define("aussenlicht-panel", AussenlichtPanel);
})();
