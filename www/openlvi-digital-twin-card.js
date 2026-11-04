/* OpenLVI Digital Twin: CSS isometric read-only HA Lovelace card.
 * Register /local/openlvi-digital-twin-card.js as JS module. No callService.
 */
class OpenLVIDigitalTwinCard extends HTMLElement {
  constructor() { super(); this._root = this.attachShadow({mode:"open"}); this._nodes = []; }
  setConfig(config) {
    if (!config || !Array.isArray(config.zones) ||
        !config.zones.length || config.zones.length > 24 ||
        (config.plant && (!Array.isArray(config.plant) || config.plant.length > 12)))
      throw new Error("Supply 1-24 zones and up to 12 plant measurements");
    const entries = [...config.zones, ...(config.plant || [])];
    if (!entries.every(x => x && typeof x.entity === "string" &&
          /^(sensor|binary_sensor|climate|number|switch|light)\.[a-z0-9_]+$/.test(x.entity)))
      throw new Error("Each entry needs a valid read-only Home Assistant entity");
    this.config = config;
    this._render();
  }
  _render() {
    // Only STATIC code is used as HTML. Untrusted labels use textContent.
    this._root.innerHTML = `
    <style>
      :host{display:block}.panel{font-family:system-ui;padding:16px;background:var(--card-background-color,#112c3a);color:var(--primary-text-color,#e6f4f8);border-radius:16px;border:1px solid #658ba050}
      h3{font-size:17px;margin:0}.sub{opacity:.67;font-size:11px;margin:4px 0 12px}
      .scene{height:190px;perspective:650px;display:flex;align-items:center;justify-content:center;overflow:hidden;
        background:radial-gradient(ellipse at center,#1e8ca233,transparent 65%)}
      .building{display:flex;width:min(66%,320px);gap:7px;flex-direction:column-reverse;
        transform:rotateX(24deg) rotateZ(-15deg) skewX(7deg);transform-style:preserve-3d}
      .floor{height:48px;border:2px solid #7dcdda;background:linear-gradient(130deg,#277993,#103a4f);
        display:flex;justify-content:space-around;align-items:center;box-shadow:12px 10px #0b2c38,13px 11px #62b0bc}
      .window{width:16px;height:16px;border-radius:3px;background:#97d3dcad;border:1px solid #c6ffff}
      .values{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
      .cell{background:#4d879533;padding:10px;border-radius:9px;display:flex;gap:8px;justify-content:space-between;
        cursor:pointer;align-items:center;border:1px solid transparent}
      .cell:focus-visible{outline:2px solid #4aafdd}.cell.bad{border-color:#ae6565}
      .cell span{font-size:12px;overflow-wrap:anywhere}.cell b{font-size:14px;font-variant-numeric:tabular-nums;white-space:nowrap}
      .title{font-size:11px;letter-spacing:.09em;opacity:.76;margin:12px 0 6px}
      .foot{font-size:10px;opacity:.62;margin-top:12px}
      @media(max-width:440px){.values{grid-template-columns:1fr}.scene{height:145px}}
    </style>
    <ha-card class="panel"><h3>OPENLVI // DIGITAL TWIN</h3>
      <div class="sub">Isometric building overview · real-time HA values · monitor only</div>
      <div class="scene"><div class="building" id="building"></div></div>
      <div class="title">ROOMS AND ZONES</div><div class="values" id="zones"></div>
      <div class="title">PLANT AND ENERGY</div><div class="values" id="plant"></div>
      <div class="foot">Schematic 2.5D model, not a measured full 3D building model. No actuator commands.</div>
    </ha-card>`;
    const building = this._root.getElementById("building");
    const floorMap = new Map();
    for (const zone of this.config.zones) {
      const floor = Number.isInteger(zone.floor) ? Math.max(-2,Math.min(20,zone.floor)) : 0;
      floorMap.set(floor, (floorMap.get(floor) || 0)+1);
    }
    for (const [floor,count] of [...floorMap.entries()].sort((a,b)=>a[0]-b[0])) {
      const el = document.createElement("div"); el.className = "floor";
      el.setAttribute("aria-label", "Floor "+floor);
      for (let i=0;i<Math.min(count,12);i++) {
        const win=document.createElement("span");win.className="window";el.appendChild(win);
      }
      building.appendChild(el);
    }
    this._nodes = [];
    const add = (records, container) => {
      for (const item of records) {
        const node = document.createElement("div"); node.className="cell";node.tabIndex=0;
        node.setAttribute("role","button");
        const label=document.createElement("span");
        label.textContent=String(item.label || item.entity).slice(0,80);
        const value=document.createElement("b");value.textContent="—";
        node.append(label,value);
        const more=()=>this.dispatchEvent(new CustomEvent("hass-more-info",
          {detail:{entityId:item.entity},bubbles:true,composed:true}));
        node.addEventListener("click",more);
        node.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();more();}});
        container.appendChild(node);
        this._nodes.push({node,value,entity:item.entity});
      }
    };
    add(this.config.zones,this._root.getElementById("zones"));
    add(this.config.plant||[],this._root.getElementById("plant"));
    if (this._hass) this.hass=this._hass;
  }
  set hass(hass) {
    this._hass=hass;
    if (!this._nodes) return;
    for(const item of this._nodes) {
      const state=hass.states[item.entity];
      const raw=state?.state || "unavailable";
      const unavailable=raw==="unknown"||raw==="unavailable";
      const unit=state?.attributes?.unit_of_measurement || "";
      item.value.textContent=unavailable ? "—" : raw+(unit?" "+unit:"");
      item.node.classList.toggle("bad",unavailable);
    }
  }
  getCardSize(){return 6;}
}
if(!customElements.get("openlvi-digital-twin-card"))
  customElements.define("openlvi-digital-twin-card",OpenLVIDigitalTwinCard);
window.customCards=window.customCards||[];
window.customCards.push({type:"openlvi-digital-twin-card",name:"OpenLVI Digital Twin (read-only)",
  description:"Interactive isometric building monitor; does not control equipment."});
