/* OpenLVI Scada Card: isometric schematic with live HA entity values.
 * Add as Lovelace JavaScript resource /local/openlvi-scada-card.js.
 * Uses no external libraries and performs no control/write operations.
 */
class OpenLVIScadaCard extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config.entities !== "object") {
      throw new Error("OpenLVI SCADA needs entities: {supply, return, outdoor, valve, fan_supply, fan_extract}");
    }
    this.config = config;
    const root = this.shadowRoot || this.attachShadow({mode: "open"});
    root.innerHTML = `
      <style>
        :host { display:block; color:var(--primary-text-color,#e5efff); }
        .panel{background:var(--card-background-color,#101923);border:1px solid #63758a4d;
          border-radius:16px;overflow:hidden;padding:16px;font-family:system-ui;min-height:300px}
        h3{margin:0 0 5px;font-size:17px;letter-spacing:.06em}
        p{font-size:11px;opacity:.75;margin:0 0 12px}
        .plant{position:relative;height:190px;overflow:hidden;background:radial-gradient(ellipse at center,#264b5b36,transparent 70%)}
        .cube{position:absolute;width:140px;height:95px;top:40px;left:calc(50% - 70px);
          background:linear-gradient(135deg,#2a687e,#112a3a);border:2px solid #73c9cf;
          transform:skewY(-9deg);box-shadow:14px 11px 0 #0a2330,15px 12px 0 #5ba4a6}
        .cube:before{content:"LVI";position:absolute;left:13px;top:12px;font-size:22px;color:#cbfaff;opacity:.9}
        .fan{position:absolute;width:52px;height:52px;border:2px solid #69c2de;border-radius:50%;top:68px;
          background:conic-gradient(#56b7e0 0 60deg,#173849 60deg 120deg,#56b7e0 120deg 180deg,#173849 180deg 240deg,#56b7e0 240deg 300deg,#173849 300deg)}
        .fan.left{left:9%}.fan.right{right:9%}
        .path{position:absolute;top:93px;height:4px;background:linear-gradient(90deg,#00c3e2,#f6b56b);
          width:19%}.path.a{left:21%}.path.b{right:21%}
        .tag{position:absolute;bottom:1px;font-size:11px;text-align:center;width:35%}
        .tag.a{left:0}.tag.b{right:0}
        .values{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
        .metric{padding:10px 5px;background:#477c8530;border-radius:9px;text-align:center}
        .metric .name{font-size:10px;opacity:.8}.metric .value{font-size:18px;font-weight:700}
        @media(max-width:460px){.metric .value{font-size:15px}.cube{width:110px;left:calc(50% - 55px)}}
      </style>
      <ha-card class="panel">
        <h3>OPENLVI // SCADA</h3><p>Isometrinen live-valvomo • vain luku</p>
        <div class="plant">
          <div class="path a"></div><div class="path b"></div><div class="cube"></div>
          <div class="fan left"></div><div class="fan right"></div>
          <div class="tag a">Tulo <b id="fan_supply">—</b></div>
          <div class="tag b">Poisto <b id="fan_extract">—</b></div>
        </div>
        <div class="values">
        ${["outdoor","supply","return","valve","power","delta_t"].map(k =>
         `<div class="metric"><div class="name">${({outdoor:"Ulko",supply:"Meno",return:"Paluu",valve:"Venttiili",power:"Teho",delta_t:"Delta T"})[k]}</div><div class="value" id="${k}">—</div></div>`).join("")}
        </div>
      </ha-card>`;
  }
  set hass(hass) {
    if (!this.config || !this.shadowRoot) return;
    for (const [key, entityId] of Object.entries(this.config.entities)) {
      const el = this.shadowRoot.getElementById(key);
      if (!el) continue;
      const state = hass.states[entityId];
      el.textContent = state && !["unknown","unavailable"].includes(state.state)
        ? state.state + (state.attributes.unit_of_measurement ? " " + state.attributes.unit_of_measurement : "")
        : "—";
    }
  }
  getCardSize() {return 5;}
}
if (!customElements.get("openlvi-scada-card")) customElements.define("openlvi-scada-card", OpenLVIScadaCard);
window.customCards = window.customCards || [];
window.customCards.push({type:"openlvi-scada-card",name:"OpenLVI SCADA",description:"Isometric live HVAC monitoring"});
