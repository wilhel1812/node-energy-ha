class NodeEnergyCard extends HTMLElement {
  static getStubConfig(hass) {
    const sensorIds = Object.keys((hass && hass.states) || {}).filter((eid) =>
      eid.startsWith("sensor.")
    );
    const preferred =
      sensorIds.find((eid) => eid.includes("node_energy")) ||
      sensorIds.find((eid) => eid.includes("wam")) ||
      sensorIds[0] ||
      "";
    return {
      entity: preferred,
      cells: 2,
      days: 7,
    };
  }

  static getConfigElement() {
    return document.createElement("node-energy-card-editor");
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("You need to define entity");
    }
    this._config = {
      cells: 2,
      days: 7,
      ...config,
    };
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 8;
  }

  _seriesToPoints(series, xMin, xMax, yMin, yMax, w, h, pad) {
    const points = [];
    const xSpan = Math.max(1, xMax - xMin);
    const ySpan = Math.max(1e-6, yMax - yMin);
    for (const p of series) {
      const x = pad + ((p.x - xMin) / xSpan) * (w - pad * 2);
      const y = h - pad - ((p.y - yMin) / ySpan) * (h - pad * 2);
      points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return points.join(" ");
  }

  _render() {
    if (!this._config || !this._hass) return;

    const st = this._hass.states[this._config.entity];
    if (!st) {
      this.innerHTML = `<ha-card header="Node Energy"><div class="card-content">Entity not found: ${this._config.entity}</div></ha-card>`;
      return;
    }

    const attrs = st.attributes || {};
    const hist = attrs.history_soc || [];
    const intervals = attrs.intervals || [];
    const forecast = attrs.forecast || {};
    const model = attrs.model || {};

    const cells = Number(this._config.cells || 2);
    const days = Number(this._config.days || 7);

    const ft = (forecast.times || []).map((t) => new Date(t).getTime());
    const wf = forecast.weather_factor || [];
    const sp = forecast.solar_proxy || [];
    const latestSoc = Number(forecast.latest_soc ?? st.state ?? 0);
    const fSolarElev = forecast.solar_elev || [];

    const cellMah = Number(this._config.cell_mah || attrs.meta?.cell_mah || 3500);
    const cellV = Number(this._config.cell_v || attrs.meta?.cell_v || 3.7);
    const cellWh = (cellMah / 1000) * cellV;
    const loadW = Number(model.load_w || 0);
    const solarPeakW = Number(model.solar_peak_w || 0);

    const n = Math.max(2, Math.min(ft.length - 1, Math.floor(days * 24 * 6)));
    const stepH = 10 / 60;

    const projWeather = [{ x: ft[0], y: latestSoc }];
    const projClear = [{ x: ft[0], y: latestSoc }];

    let sw = latestSoc;
    let sc = latestSoc;
    for (let i = 1; i <= n; i++) {
      const prodW = solarPeakW * Number(sp[i] || 0) * Number(wf[i] || 1);
      const prodC = solarPeakW * Number(sp[i] || 0);
      sw += ((-loadW + prodW) * stepH / (cells * cellWh)) * 100;
      sc += ((-loadW + prodC) * stepH / (cells * cellWh)) * 100;
      sw = Math.max(0, Math.min(100, sw));
      sc = Math.max(0, Math.min(100, sc));
      projWeather.push({ x: ft[i], y: sw });
      projClear.push({ x: ft[i], y: sc });
    }

    const histSeries = hist
      .map((p) => ({ x: new Date(p.t).getTime(), y: Number(p.v) }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));

    const all = [...histSeries, ...projWeather, ...projClear];
    if (!all.length) {
      this.innerHTML = `<ha-card header="Node Energy"><div class="card-content">No history/forecast data yet.</div></ha-card>`;
      return;
    }

    const xMin = Math.min(...all.map((p) => p.x));
    const xMax = Math.max(...all.map((p) => p.x));
    const yMin = 0;
    const yMax = 100;

    const w = 980;
    const h = 420;
    const pad = 44;

    const histPts = this._seriesToPoints(histSeries, xMin, xMax, yMin, yMax, w, h, pad);
    const projWPts = this._seriesToPoints(projWeather, xMin, xMax, yMin, yMax, w, h, pad);
    const projCPts = this._seriesToPoints(projClear, xMin, xMax, yMin, yMax, w, h, pad);

    const histSunSeries = intervals
      .map((p) => ({ x: new Date(p.tm).getTime(), y: Number(p.sun_elev_deg) }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    const fcSunSeries = ft.slice(0, n + 1).map((x, i) => ({ x, y: Number(fSolarElev[i] || 0) }));
    const allSun = [...histSunSeries, ...fcSunSeries];
    const sunYMin = allSun.length ? Math.min(-10, ...allSun.map((p) => p.y)) : -10;
    const sunYMax = allSun.length ? Math.max(30, ...allSun.map((p) => p.y)) : 30;
    const histSunPts = this._seriesToPoints(histSunSeries, xMin, xMax, sunYMin, sunYMax, w, h, pad);
    const fcSunPts = this._seriesToPoints(fcSunSeries, xMin, xMax, sunYMin, sunYMax, w, h, pad);

    const nowX = histSeries.length ? histSeries[histSeries.length - 1].x : projWeather[0].x;
    const nowSvgX = pad + ((nowX - xMin) / Math.max(1, xMax - xMin)) * (w - pad * 2);

    this.innerHTML = `
      <ha-card header="Node Energy">
        <div class="card-content">
          <div class="meta">
            <span>Latest: <b>${latestSoc.toFixed(1)}%</b></span>
            <span>Load: <b>${loadW.toFixed(2)}W</b></span>
            <span>Solar peak: <b>${solarPeakW.toFixed(2)}W</b></span>
            <span>Cells: <b>${cells}</b></span>
          </div>
          <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" class="chart">
            <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" class="axis"></line>
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h - pad}" class="axis"></line>
            <polyline points="${histPts}" class="hist"></polyline>
            <polyline points="${projWPts}" class="projw"></polyline>
            <polyline points="${projCPts}" class="projc"></polyline>
            <line x1="${nowSvgX.toFixed(1)}" y1="${pad}" x2="${nowSvgX.toFixed(1)}" y2="${h - pad}" class="now"></line>
            <text x="${(nowSvgX + 4).toFixed(1)}" y="${(pad + 12).toFixed(1)}" class="txt">Now</text>
            <text x="8" y="${pad + 2}" class="txt">100%</text>
            <text x="8" y="${h - pad + 4}" class="txt">0%</text>
          </svg>
          <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" class="chart sun">
            <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" class="axis"></line>
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h - pad}" class="axis"></line>
            <polyline points="${histSunPts}" class="sunh"></polyline>
            <polyline points="${fcSunPts}" class="sunf"></polyline>
            <line x1="${nowSvgX.toFixed(1)}" y1="${pad}" x2="${nowSvgX.toFixed(1)}" y2="${h - pad}" class="now"></line>
            <text x="${(nowSvgX + 4).toFixed(1)}" y="${(pad + 12).toFixed(1)}" class="txt">Now</text>
            <text x="8" y="${pad + 2}" class="txt">${sunYMax.toFixed(0)}°</text>
            <text x="8" y="${h - pad + 4}" class="txt">${sunYMin.toFixed(0)}°</text>
          </svg>
          <div class="legend">
            <span><i class="dot hist"></i> History</span>
            <span><i class="dot projw"></i> Projection (weather)</span>
            <span><i class="dot projc"></i> Projection (clear)</span>
            <span><i class="dot sunh"></i> Sun elevation (history)</span>
            <span><i class="dot sunf"></i> Sun elevation (forecast)</span>
          </div>
        </div>
      </ha-card>
      <style>
        .card-content { padding: 12px; }
        .meta { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 8px; font-size: 13px; }
        .chart { width: 100%; height: 420px; background: #fff; border: 1px solid rgba(0,0,0,.08); border-radius: 10px; }
        .chart.sun { margin-top: 10px; height: 220px; }
        .axis { stroke: #cbd5e1; stroke-width: 1; }
        .hist { fill: none; stroke: #111827; stroke-width: 2.6; }
        .projw { fill: none; stroke: #0f766e; stroke-width: 2.8; }
        .projc { fill: none; stroke: #0f766e; stroke-width: 1.6; stroke-dasharray: 5 4; }
        .sunh { fill: none; stroke: #b45309; stroke-width: 2.2; }
        .sunf { fill: none; stroke: #f59e0b; stroke-width: 1.8; stroke-dasharray: 5 4; }
        .now { stroke: #6b7280; stroke-width: 1.2; stroke-dasharray: 4 4; }
        .txt { font-size: 11px; fill: #64748b; }
        .legend { display: flex; gap: 12px; margin-top: 8px; font-size: 12px; color: #475569; flex-wrap: wrap; }
        .dot { display: inline-block; width: 10px; height: 10px; border-radius: 999px; margin-right: 6px; vertical-align: -1px; }
        .dot.hist { background: #111827; }
        .dot.projw { background: #0f766e; }
        .dot.projc { background: #0f766e; border: 1px dashed #0f766e; background: transparent; }
        .dot.sunh { background: #b45309; }
        .dot.sunf { background: #f59e0b; border: 1px dashed #f59e0b; background: transparent; }
      </style>
    `;
  }
}

class NodeEnergyCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = {
      entity: "",
      cells: 2,
      days: 7,
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _emitChanged() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    if (!this._hass || !this._config) return;
    const sensors = Object.keys(this._hass.states || {})
      .filter((eid) => eid.startsWith("sensor."))
      .sort();

    this.innerHTML = `
      <style>
        .wrap { display: grid; gap: 10px; }
        .row { display: grid; gap: 4px; }
        label { font-size: 12px; color: var(--secondary-text-color); }
        input { padding: 8px; border: 1px solid var(--divider-color); border-radius: 6px; background: var(--card-background-color); color: var(--primary-text-color); }
      </style>
      <div class="wrap">
        <div class="row">
          <label>Entity</label>
          <input id="entity" list="node-energy-sensors" value="${this._config.entity || ""}" placeholder="sensor.node_energy..." />
          <datalist id="node-energy-sensors">
            ${sensors.map((s) => `<option value="${s}"></option>`).join("")}
          </datalist>
        </div>
        <div class="row">
          <label>Cells</label>
          <input id="cells" type="number" min="1" max="12" step="1" value="${Number(this._config.cells || 2)}" />
        </div>
        <div class="row">
          <label>Days</label>
          <input id="days" type="number" min="1" max="14" step="1" value="${Number(this._config.days || 7)}" />
        </div>
      </div>
    `;

    this.querySelector("#entity")?.addEventListener("change", (ev) => {
      this._config = { ...this._config, entity: ev.target.value.trim() };
      this._emitChanged();
    });
    this.querySelector("#cells")?.addEventListener("change", (ev) => {
      const v = Math.max(1, Math.min(12, Number(ev.target.value || 2)));
      this._config = { ...this._config, cells: v };
      this._emitChanged();
    });
    this.querySelector("#days")?.addEventListener("change", (ev) => {
      const v = Math.max(1, Math.min(14, Number(ev.target.value || 7)));
      this._config = { ...this._config, days: v };
      this._emitChanged();
    });
  }
}

if (!customElements.get("node-energy-card")) {
  customElements.define("node-energy-card", NodeEnergyCard);
}
if (!customElements.get("node-energy-card-editor")) {
  customElements.define("node-energy-card-editor", NodeEnergyCardEditor);
}
window.customCards = window.customCards || [];
window.customCards.push({
  type: "node-energy-card",
  name: "Node Energy Card",
  description: "Unified history + projection for Node Energy integration",
});
